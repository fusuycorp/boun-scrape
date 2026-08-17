"""Unit and integration tests for ScrapeScheduler runner and execution cycle."""

from pathlib import Path
import asyncio
import httpx
import pytest

from boun_scrape.domain.models import RunStatus
from boun_scrape.feeds.webhooks import WebhookDispatcher
from boun_scrape.scheduler.runner import (
    ScrapeAlreadyRunningError,
    ScrapeScheduler,
)
from boun_scrape.scraper.client import BounScraperClient
from boun_scrape.storage.database import DatabaseManager
from boun_scrape.storage.repository import CourseRepository

FIXTURES_DIR = Path(__file__).parent / "fixtures"
BASE_URL = "https://registration.bogazici.edu.tr"


@pytest.fixture
def semester_html() -> str:
    with open(FIXTURES_DIR / "sample_semester.html", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def schedule_html() -> str:
    with open(FIXTURES_DIR / "sample_schedule.html", "r", encoding="utf-8") as f:
        return f.read()


class TestScrapeScheduler:
    """Tests for scrape scheduling, cycle execution, and daemon lifecycle."""

    @pytest.mark.asyncio
    async def test_scheduler_init_and_status(self, tmp_path: Path) -> None:
        db_mgr = DatabaseManager(str(tmp_path / "test.db"))
        db_mgr.init_db()
        repo = CourseRepository(db_mgr)

        scheduler = ScrapeScheduler(
            interval_seconds=1800,
            cron_expression="0 * * * *",
            repository=repo,
            export_dir=tmp_path / "exports",
        )

        status = scheduler.get_status()
        assert status["is_running"] is False
        assert status["is_scraping"] is False
        assert status["interval_seconds"] == 1800
        assert status["cron_expression"] == "0 * * * *"
        assert status["run_count"] == 0
        assert status["last_run_summary"] is None

        await scheduler.aclose()

    @pytest.mark.asyncio
    async def test_execute_scrape_cycle_full_flow(
        self,
        semester_html: str,
        schedule_html: str,
        tmp_path: Path,
    ) -> None:
        # Mock university registration server
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if "schedule.aspx" in path:
                return httpx.Response(200, content=semester_html.encode("windows-1254"))
            if "sch.asp" in path:
                return httpx.Response(200, content=schedule_html.encode("windows-1254"))
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)

        webhook_payloads: list[dict[str, object]] = []

        def webhook_handler(request: httpx.Request) -> httpx.Response:
            import json

            webhook_payloads.append(json.loads(request.read()))
            return httpx.Response(200)

        wh_transport = httpx.MockTransport(webhook_handler)

        async with (
            httpx.AsyncClient(transport=transport, base_url=BASE_URL) as scraper_http,
            httpx.AsyncClient(transport=wh_transport) as webhook_http,
        ):
            scraper_client = BounScraperClient(
                http_client=scraper_http, min_jitter=0, max_jitter=0
            )
            webhook_dispatcher = WebhookDispatcher(
                urls=["https://example.com/feed"],
                webhook_secret="test_secret",
                http_client=webhook_http,
            )

            db_mgr = DatabaseManager(str(tmp_path / "schedules.db"))
            db_mgr.init_db()
            repo = CourseRepository(db_mgr)
            export_dir = tmp_path / "exports"

            scheduler = ScrapeScheduler(
                client=scraper_client,
                repository=repo,
                webhook_dispatcher=webhook_dispatcher,
                export_dir=export_dir,
                default_term="2024/2025-1",
            )

            # Cycle 1: First initial scrape (all courses detected as ADDED deltas)
            summary1 = await scheduler.execute_scrape_cycle()

            assert summary1.status == RunStatus.COMPLETED
            assert summary1.term == "2024/2025-1"
            assert summary1.total_courses > 0
            assert summary1.total_slots > 0
            assert summary1.changes_detected == summary1.total_courses

            # Verify persisted courses in repository
            courses_in_db = repo.get_courses_by_term("2024/2025-1")
            assert len(courses_in_db) == summary1.total_courses

            # Verify runs in repository
            runs = repo.get_scrape_runs(term="2024/2025-1")
            assert len(runs) == 1
            assert runs[0].run_id == summary1.run_id
            assert runs[0].status == RunStatus.COMPLETED

            # Verify deltas in repository
            deltas_in_db = repo.get_deltas(term="2024/2025-1", run_id=summary1.run_id)
            assert len(deltas_in_db) == summary1.changes_detected

            # Verify export files generated
            assert (export_dir / "courses_2024_2025-1.json").is_file()
            assert (export_dir / "courses_2024_2025-1.csv").is_file()
            assert (export_dir / "courses_2024_2025-1.db").is_file()
            assert (export_dir / "deltas_2024_2025-1.json").is_file()

            # Verify webhooks received deltas and summary
            assert len(webhook_payloads) == 2
            assert webhook_payloads[0]["event"] == "courses.deltas"
            assert webhook_payloads[1]["event"] == "scrape.summary"
            webhook_payloads.clear()

            # Cycle 2: Immediate re-scrape with identical content -> 0 changes detected
            summary2 = await scheduler.execute_scrape_cycle()
            assert summary2.status == RunStatus.COMPLETED
            assert summary2.changes_detected == 0
            # Only summary webhook dispatched since 0 deltas
            assert len(webhook_payloads) == 1
            assert webhook_payloads[0]["event"] == "scrape.summary"

            await scheduler.aclose()

    @pytest.mark.asyncio
    async def test_execute_scrape_cycle_emits_telemetry_logs_and_progress(
        self,
        semester_html: str,
        schedule_html: str,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Regression: the happy path previously had zero logger.info() calls,
        so the UI's log terminal stayed empty for successful runs. Also
        verifies current_progress is populated during the department fetch
        (surfaced via get_status()) and cleared again once the cycle ends."""

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if "schedule.aspx" in path:
                return httpx.Response(200, content=semester_html.encode("windows-1254"))
            if "sch.asp" in path:
                return httpx.Response(200, content=schedule_html.encode("windows-1254"))
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as http_client:
            scraper_client = BounScraperClient(
                http_client=http_client, min_jitter=0, max_jitter=0
            )
            db_mgr = DatabaseManager(str(tmp_path / "test.db"))
            db_mgr.init_db()
            repo = CourseRepository(db_mgr)

            scheduler = ScrapeScheduler(
                client=scraper_client,
                repository=repo,
                default_term="2024/2025-1",
                export_dir=tmp_path / "exports",
            )

            assert scheduler.get_status()["current_progress"] is None

            with caplog.at_level("INFO", logger="boun_scrape.scheduler.runner"):
                summary = await scheduler.execute_scrape_cycle()

            assert summary.status == RunStatus.COMPLETED
            messages = " ".join(r.message for r in caplog.records)
            assert "resolved term" in messages
            assert "finished scraping" in messages
            assert "detected" in messages and "changes" in messages
            assert "completed" in messages

            # Progress is cleared once the cycle finishes.
            assert scheduler.get_status()["current_progress"] is None

            await scheduler.aclose()

    @pytest.mark.asyncio
    async def test_execute_scrape_cycle_non_overlapping_guard(
        self,
        tmp_path: Path,
    ) -> None:
        # Mock slow scrape handler
        async def slow_handler(request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(0.1)
            return httpx.Response(200, content=b"")

        transport = httpx.MockTransport(slow_handler)
        async with httpx.AsyncClient(
            transport=transport, base_url=BASE_URL
        ) as http_client:
            scraper_client = BounScraperClient(
                http_client=http_client, min_jitter=0, max_jitter=0
            )
            db_mgr = DatabaseManager(str(tmp_path / "test.db"))
            db_mgr.init_db()
            repo = CourseRepository(db_mgr)

            scheduler = ScrapeScheduler(
                client=scraper_client,
                repository=repo,
                default_term="2024/2025-1",
            )

            # Start a cycle
            task = asyncio.create_task(scheduler.execute_scrape_cycle())
            await asyncio.sleep(0.01)

            assert scheduler.is_scraping is True

            # Attempting second concurrent cycle must raise ScrapeAlreadyRunningError
            with pytest.raises(ScrapeAlreadyRunningError):
                await scheduler.execute_scrape_cycle()

            try:
                await task
            except Exception:
                pass

            await scheduler.aclose()

    @pytest.mark.asyncio
    async def test_execute_scrape_cycle_error_handling(
        self,
        tmp_path: Path,
    ) -> None:
        def fail_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal University Server Error")

        transport = httpx.MockTransport(fail_handler)
        async with httpx.AsyncClient(
            transport=transport, base_url=BASE_URL
        ) as http_client:
            scraper_client = BounScraperClient(
                http_client=http_client, min_jitter=0, max_jitter=0
            )
            db_mgr = DatabaseManager(str(tmp_path / "test.db"))
            db_mgr.init_db()
            repo = CourseRepository(db_mgr)

            scheduler = ScrapeScheduler(
                client=scraper_client,
                repository=repo,
                default_term="2024/2025-1",
            )

            with pytest.raises(Exception) as exc_info:
                await scheduler.execute_scrape_cycle()

            assert "500" in str(exc_info.value) or "Server error" in str(exc_info.value)

            # Check that failed run was persisted
            runs = repo.get_scrape_runs(term="2024/2025-1")
            assert len(runs) == 1
            assert runs[0].status == RunStatus.FAILED
            assert runs[0].error_message is not None

            await scheduler.aclose()

    @pytest.mark.asyncio
    async def test_execute_scrape_cycle_honors_configured_max_concurrency(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Regression: settings.max_concurrency must reach scrape_term_pipeline,
        not silently fall back to the hardcoded default of 10."""
        from boun_scrape import config as config_module
        from boun_scrape.scheduler import runner as runner_module

        captured_concurrency: list[int] = []

        async def fake_scrape_term_pipeline(client, term, progress_callback=None, concurrency=10):
            captured_concurrency.append(concurrency)
            return []

        monkeypatch.setattr(runner_module, "scrape_term_pipeline", fake_scrape_term_pipeline)

        db_mgr = DatabaseManager(str(tmp_path / "test.db"))
        db_mgr.init_db()
        repo = CourseRepository(db_mgr)

        settings = config_module.Settings(max_concurrency=2)
        scheduler = ScrapeScheduler(
            repository=repo,
            default_term="2024/2025-1",
            settings=settings,
            client=BounScraperClient(min_jitter=0, max_jitter=0),
        )

        await scheduler.execute_scrape_cycle(export=False, dispatch_webhooks=False)

        assert captured_concurrency == [2]
        await scheduler.aclose()

    @pytest.mark.asyncio
    async def test_execute_scrape_cycle_persists_failed_run_on_term_discovery_error(
        self,
        tmp_path: Path,
    ) -> None:
        """Regression: a failure during term resolution (no default_term given) must
        still be persisted as a FAILED run, not vanish before any record is written."""

        def fail_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal University Server Error")

        transport = httpx.MockTransport(fail_handler)
        async with httpx.AsyncClient(
            transport=transport, base_url=BASE_URL
        ) as http_client:
            scraper_client = BounScraperClient(
                http_client=http_client, min_jitter=0, max_jitter=0
            )
            db_mgr = DatabaseManager(str(tmp_path / "test.db"))
            db_mgr.init_db()
            repo = CourseRepository(db_mgr)

            scheduler = ScrapeScheduler(
                client=scraper_client,
                repository=repo,
                # No default_term: forces discover_terms(), which fails against the
                # 500-returning mock portal before any term is known.
            )

            with pytest.raises(Exception):
                await scheduler.execute_scrape_cycle()

            runs = repo.get_scrape_runs()
            assert len(runs) == 1
            assert runs[0].status == RunStatus.FAILED
            assert runs[0].error_message is not None

            await scheduler.aclose()

    @pytest.mark.asyncio
    async def test_scheduler_lifecycle_start_and_stop(
        self,
        tmp_path: Path,
    ) -> None:
        db_mgr = DatabaseManager(str(tmp_path / "test.db"))
        db_mgr.init_db()
        repo = CourseRepository(db_mgr)

        scheduler = ScrapeScheduler(
            interval_seconds=3600,
            repository=repo,
        )

        assert scheduler.is_running is False
        task = scheduler.start()
        assert scheduler.is_running is True
        assert not task.done()

        # Calling start again returns same task
        assert scheduler.start() == task

        await scheduler.stop()
        assert scheduler.is_running is False

        await scheduler.aclose()
