"""Background scheduler for periodic scraping, delta tracking, and downstream distribution."""

import asyncio
import logging
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import uuid

import croniter

from boun_scrape.config import Settings, get_settings
from boun_scrape.domain.events import CourseDeltaEvent
from boun_scrape.domain.models import Course, QuotaRecord, RunStatus, ScrapeRunSummary
from boun_scrape.feeds.webhooks import WebhookDispatcher
from boun_scrape.pipeline.delta import compute_deltas
from boun_scrape.pipeline.exporter import generate_all_exports
from boun_scrape.scraper.client import BounScraperClient
from boun_scrape.scraper.flow import TermScrapeResult, discover_terms, scrape_term_pipeline
from boun_scrape.scraper.quota import QuotaService, format_course_key
from boun_scrape.storage.database import DatabaseManager
from boun_scrape.storage.repository import CourseRepository

logger = logging.getLogger(__name__)


class ScrapeSchedulerError(Exception):
    """Base exception for scheduler execution errors."""


class ScrapeAlreadyRunningError(ScrapeSchedulerError):
    """Raised when a scrape cycle is triggered while another is currently active."""


class ScrapeScheduler:
    """Orchestrates periodic scrape cycles, delta generation, persistence, and feeds."""

    def __init__(
        self,
        interval_seconds: int = 3600,
        cron_expression: str | None = None,
        client: BounScraperClient | None = None,
        repository: CourseRepository | None = None,
        webhook_dispatcher: WebhookDispatcher | None = None,
        export_dir: str | Path = "exports",
        default_term: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.interval_seconds = interval_seconds
        if cron_expression is not None and cron_expression.strip():
            stripped_cron = cron_expression.strip()
            if not croniter.croniter.is_valid(stripped_cron):
                raise ValueError(f"Invalid cron expression: '{stripped_cron}'")
            self.cron_expression = stripped_cron
        else:
            self.cron_expression = None
        self.default_term = default_term
        self.export_dir = Path(export_dir)

        # Scraper client
        if client is not None:
            self.client = client
            self._owns_client = False
        else:
            self.client = BounScraperClient(settings=self.settings)
            self._owns_client = True

        self.quota_service = QuotaService(client=self.client, settings=self.settings)

        # Repository
        if repository is not None:
            self.repository = repository
        else:
            db_mgr = DatabaseManager(self.settings.db_path)
            db_mgr.init_db()
            self.repository = CourseRepository(db_mgr)

        # Webhook dispatcher
        self.webhook_dispatcher = webhook_dispatcher

        # Internal state guards
        self._running: bool = False
        self._task: asyncio.Task[None] | None = None
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._cycle_lock = asyncio.Lock()
        self._last_run_summary: ScrapeRunSummary | None = None
        self._last_run_time: datetime | None = None
        self._next_run_time: datetime | None = None
        self._run_count: int = 0
        self._current_progress: dict[str, Any] | None = None

    @property
    def is_running(self) -> bool:
        """Indicate whether the periodic background scheduler loop is currently active."""
        return self._running and self._task is not None and not self._task.done()

    @property
    def is_scraping(self) -> bool:
        """Indicate whether a scrape cycle is currently executing."""
        return self._cycle_lock.locked()

    def get_status(self) -> dict[str, Any]:
        """Return the current scheduler operational status and metrics."""
        summary_dict = (
            asdict(self._last_run_summary) if self._last_run_summary else None
        )
        if summary_dict and isinstance(summary_dict.get("status"), RunStatus):
            summary_dict["status"] = summary_dict["status"].value

        return {
            "is_running": self.is_running,
            "is_scraping": self.is_scraping,
            "interval_seconds": self.interval_seconds,
            "cron_expression": self.cron_expression,
            "default_term": self.default_term,
            "run_count": self._run_count,
            "last_run_time": (
                self._last_run_time.isoformat() if self._last_run_time else None
            ),
            "next_run_time": (
                self._next_run_time.isoformat() if self._next_run_time else None
            ),
            "last_run_summary": summary_dict,
            "current_progress": self._current_progress,
        }

    def update_config(
        self,
        interval_seconds: int | None = None,
        cron_expression: str | None = None,
        default_term: str | None = None,
    ) -> None:
        """Update scheduler timing or default term, restarting loop if running."""
        if interval_seconds is not None:
            self.interval_seconds = interval_seconds
        if cron_expression is not None:
            stripped_cron = cron_expression.strip() if cron_expression.strip() else None
            if stripped_cron and not croniter.croniter.is_valid(stripped_cron):
                raise ValueError(f"Invalid cron expression: '{stripped_cron}'")
            self.cron_expression = stripped_cron
        if default_term is not None:
            self.default_term = default_term.strip() if default_term.strip() else None

        if self.is_running:
            if self._task is not None and not self._task.done():
                self._task.cancel()
            self._task = asyncio.create_task(self._schedule_loop())

    async def _resolve_target_term(self, requested_term: str | None) -> str:
        """Resolve academic term from parameter, default setting, live discovery, or cached terms."""
        target_term = requested_term or self.default_term
        if target_term:
            return target_term

        try:
            discovered = await discover_terms(self.client)
        except Exception as exc:
            logger.warning("discover_terms failed: %s. Falling back to cached terms.", exc)
            discovered = []

        if discovered:
            return discovered[0]

        cached_terms = await asyncio.to_thread(self.repository.get_terms)
        if cached_terms:
            logger.info("Using latest cached term: %s", cached_terms[0])
            return cached_terms[0]

        raise ScrapeSchedulerError(
            "No academic terms discovered from portal or cached in database."
        )

    async def _scrape_and_compute_deltas(
        self,
        target_term: str,
        target_departments: list[str] | None,
        skip_already_scraped: bool,
        run_id: str,
    ) -> tuple[TermScrapeResult, list[CourseDeltaEvent]]:
        """Run portal scraping pipeline and calculate delta events against prior successful term data."""
        self._current_progress = {"completed": 0, "total": 0, "department": None}

        def _on_department_progress(
            completed: int, total: int, dept: Any, courses: list
        ) -> None:
            self._current_progress = {
                "completed": completed,
                "total": total,
                "department": dept.code,
            }
            logger.info(
                "Scrape %s: department %s (%d/%d) — %d courses",
                run_id, dept.code, completed, total, len(courses),
            )

        cached_depts = await asyncio.to_thread(self.repository.get_departments, target_term)
        completed_codes = (
            await asyncio.to_thread(self.repository.get_completed_department_codes, target_term)
            if skip_already_scraped
            else None
        )

        result = await scrape_term_pipeline(
            self.client,
            term=target_term,
            concurrency=self.settings.max_concurrency,
            progress_callback=_on_department_progress,
            cached_departments=cached_depts,
            target_departments=target_departments,
            skip_already_scraped=skip_already_scraped,
            completed_department_codes=completed_codes,
        )

        previous_courses = await asyncio.to_thread(self.repository.get_courses_by_term, target_term)
        succeeded_set = set(result.succeeded_departments)
        filtered_previous = [c for c in previous_courses if c.department in succeeded_set]

        deltas = compute_deltas(
            previous_courses=filtered_previous,
            current_courses=result.courses,
            run_id=run_id,
            term=target_term,
        )
        return result, deltas

    async def _persist_cycle_data(
        self,
        target_term: str,
        result: TermScrapeResult,
        deltas: list[CourseDeltaEvent],
        run_id: str,
    ) -> None:
        """Persist departments, failed department statuses, courses, slots, and deltas off the event loop."""
        def _sync_persist() -> None:
            self.repository.save_departments(target_term, result.departments)
            for failed_dept in result.failed_departments:
                self.repository.update_department_scrape_status(
                    term=target_term,
                    code=failed_dept,
                    course_count=0,
                    status="FAILED",
                    error="Crawl failed during pipeline execution",
                )
            self.repository.save_courses_and_slots(
                term=target_term,
                courses=result.courses,
                scraped_departments=result.succeeded_departments,
            )
            if deltas:
                self.repository.save_deltas(deltas=deltas, run_id=run_id)

        await asyncio.to_thread(_sync_persist)

    async def _capture_live_quotas_safe(
        self,
        target_term: str,
        current_courses: list[Course],
        run_id: str,
    ) -> None:
        """Fetch live course section quotas and persist bulk snapshots without aborting cycle on failure."""
        try:
            quota_items = [
                (target_term, c.department, c.course_code, c.section)
                for c in current_courses
            ]
            logger.info(
                "Scrape %s: capturing quota snapshots for %d course sections",
                run_id, len(quota_items),
            )
            quota_results = await self.quota_service.fetch_batch_quotas(
                quota_items, concurrency=self.settings.max_concurrency
            )
            quota_rows: list[tuple[str, str, str, QuotaRecord]] = []
            for c in current_courses:
                key = format_course_key(c.department, c.course_code, c.section)
                for record in quota_results.get(key, []):
                    quota_rows.append((target_term, c.course_code, c.section, record))
            if quota_rows:
                await asyncio.to_thread(self.repository.save_quota_snapshots_bulk, quota_rows)
            logger.info("Scrape %s: captured %d quota rows", run_id, len(quota_rows))
        except Exception:
            logger.exception("Scrape %s: quota capture failed (continuing, run not affected)", run_id)

    async def _dispatch_artifacts_and_webhooks(
        self,
        target_term: str,
        summary: ScrapeRunSummary,
        courses: list[Course],
        deltas: list[CourseDeltaEvent],
        export: bool,
        dispatch_webhooks: bool,
        run_id: str,
    ) -> None:
        """Generate static export files in worker thread and trigger downstream webhook notifications."""
        if export:
            await asyncio.to_thread(
                generate_all_exports,
                term=target_term,
                courses=courses,
                deltas=deltas,
                output_dir=self.export_dir,
            )
            logger.info("Scrape %s: exported artifacts to %s", run_id, self.export_dir)

        if dispatch_webhooks and self.webhook_dispatcher is not None:
            try:
                if deltas:
                    await self.webhook_dispatcher.dispatch_deltas(deltas, term=target_term)
                await self.webhook_dispatcher.dispatch_run_summary(summary)
                logger.info("Scrape %s: webhooks dispatched", run_id)
            except Exception:
                logger.exception("Scrape %s: webhook dispatch failed (continuing, run not affected)", run_id)

    async def execute_scrape_cycle(
        self,
        term: str | None = None,
        export: bool = True,
        dispatch_webhooks: bool = True,
        capture_quota: bool = False,
        target_departments: list[str] | None = None,
        skip_already_scraped: bool = False,
    ) -> ScrapeRunSummary:
        """Execute a full scrape cycle with delta detection, persistence, exports, and feeds.

        Args:
            term: Specific academic term (e.g. '2024/2025-1'). If None, discovers the latest term.
            export: If True, generate JSON, CSV, SQLite, and delta artifacts.
            dispatch_webhooks: If True, send events to configured webhook endpoints.
            capture_quota: If True, additionally capture a live quota snapshot for every
                scraped course section (rate-limit-sensitive against the registration
                portal — opt-in, default off).
            target_departments: Optional subset of department codes to scrape.
            skip_already_scraped: If True, skip departments that are already marked COMPLETED.

        Returns:
            ScrapeRunSummary entity containing run metrics.
        """
        if self._cycle_lock.locked():
            raise ScrapeAlreadyRunningError("A scrape cycle is already in progress.")

        async with self._cycle_lock:
            now_utc = datetime.now(timezone.utc)
            run_id = f"run_{int(now_utc.timestamp())}_{uuid.uuid4().hex[:6]}"
            started_at = now_utc.isoformat()

            summary = ScrapeRunSummary(
                run_id=run_id,
                term=term or self.default_term or "unresolved",
                status=RunStatus.RUNNING,
                started_at=started_at,
            )
            await asyncio.to_thread(self.repository.save_scrape_run, summary)

            try:
                # 1. Target term resolution
                target_term = await self._resolve_target_term(term)
                summary.term = target_term
                logger.info("Scrape %s: resolved term %s", run_id, target_term)

                # 2. Scrape & compute change deltas
                result, deltas = await self._scrape_and_compute_deltas(
                    target_term=target_term,
                    target_departments=target_departments,
                    skip_already_scraped=skip_already_scraped,
                    run_id=run_id,
                )
                logger.info(
                    "Scrape %s: finished scraping %d courses, %d changes detected",
                    run_id, len(result.courses), len(deltas),
                )

                # 3. Off-event-loop persistence
                await self._persist_cycle_data(target_term, result, deltas, run_id)
                logger.info("Scrape %s: persisted courses and deltas", run_id)

                # 4. Optional quota snapshot capture
                if capture_quota:
                    await self._capture_live_quotas_safe(target_term, result.courses, run_id)

                # 5. Finalize run metrics
                total_slots = sum(len(c.slots) for c in result.courses)
                completed_at = datetime.now(timezone.utc).isoformat()

                summary.status = RunStatus.COMPLETED
                summary.completed_at = completed_at
                summary.total_courses = len(result.courses)
                summary.total_slots = total_slots
                summary.changes_detected = len(deltas)
                summary.total_departments = len(result.succeeded_departments) + len(result.failed_departments)
                summary.completed_departments = len(result.succeeded_departments)
                await asyncio.to_thread(self.repository.save_scrape_run, summary)

                # 6. Artifact exports & webhook dispatch
                await self._dispatch_artifacts_and_webhooks(
                    target_term=target_term,
                    summary=summary,
                    courses=result.courses,
                    deltas=deltas,
                    export=export,
                    dispatch_webhooks=dispatch_webhooks,
                    run_id=run_id,
                )

                logger.info(
                    "Scrape %s: completed — %d courses, %d slots, %d changes",
                    run_id, len(result.courses), total_slots, len(deltas),
                )
                self._current_progress = None
                self._last_run_summary = summary
                self._last_run_time = datetime.now(timezone.utc)
                self._run_count += 1
                return summary

            except asyncio.CancelledError:
                summary.status = RunStatus.CANCELLED
                summary.completed_at = datetime.now(timezone.utc).isoformat()
                summary.error_message = "Scrape cycle was cancelled"
                try:
                    await asyncio.to_thread(self.repository.save_scrape_run, summary)
                except Exception:
                    logger.exception("Scrape %s: failed to save cancelled run state", run_id)
                self._current_progress = None
                self._last_run_summary = summary
                self._last_run_time = datetime.now(timezone.utc)
                raise

            except Exception as exc:
                summary.status = RunStatus.FAILED
                summary.completed_at = datetime.now(timezone.utc).isoformat()
                summary.error_message = str(exc)
                await asyncio.to_thread(self.repository.save_scrape_run, summary)
                logger.exception("Scrape %s: failed", run_id)

                if dispatch_webhooks and self.webhook_dispatcher is not None:
                    try:
                        await self.webhook_dispatcher.dispatch_run_summary(summary)
                    except Exception:
                        logger.exception("Scrape %s: webhook dispatch on failure failed", run_id)

                self._current_progress = None
                self._last_run_summary = summary
                self._last_run_time = datetime.now(timezone.utc)
                raise

    async def execute_all_terms_cycle(
        self,
        export: bool = True,
        dispatch_webhooks: bool = True,
        capture_quota: bool = False,
    ) -> list[ScrapeRunSummary]:
        """Discover every term the portal currently exposes and scrape each one sequentially.

        Each term is scraped as its own independent run (own run_id, own delta
        computation, own persistence) via execute_scrape_cycle. A failure on one
        term is logged and does not abort the remaining terms -- the returned
        list only contains summaries for terms that completed (successfully or
        not); a term whose exception propagated past execute_scrape_cycle is
        skipped from the returned list but is still recorded in the scrape_runs
        table with status FAILED by execute_scrape_cycle itself.
        """
        try:
            terms = await discover_terms(self.client)
        except Exception as exc:
            logger.warning(
                "discover_terms failed in all-terms cycle: %s. Falling back to cached terms.",
                exc,
            )
            terms = []

        if not terms:
            terms = await asyncio.to_thread(self.repository.get_terms)
            if not terms:
                raise ScrapeSchedulerError(
                    "No academic terms discovered from portal or cached in database."
                )
            logger.info("Using %d cached terms for all-terms cycle: %s", len(terms), terms)

        logger.info(
            "Starting all-terms scrape cycle: %d terms discovered: %s", len(terms), terms
        )
        summaries: list[ScrapeRunSummary] = []
        for t in terms:
            try:
                summary = await self.execute_scrape_cycle(
                    term=t,
                    export=export,
                    dispatch_webhooks=dispatch_webhooks,
                    capture_quota=capture_quota,
                )
                summaries.append(summary)
            except Exception:
                logger.exception(
                    "All-terms cycle: term %s failed, continuing with remaining terms", t
                )

        logger.info(
            "All-terms scrape cycle complete: %d/%d terms succeeded",
            len(summaries),
            len(terms),
        )
        return summaries

    def _compute_next_delay(self) -> float:
        """Compute sleep seconds until the next execution timestamp."""
        now = datetime.now(timezone.utc)
        if self.cron_expression:
            cron = croniter.croniter(self.cron_expression, now)
            next_dt = cron.get_next(datetime)
            self._next_run_time = next_dt
            delay = (next_dt - now).total_seconds()
            return max(0.0, delay)

        self._next_run_time = now + timedelta(seconds=self.interval_seconds)
        return max(0.0, float(self.interval_seconds))

    async def _schedule_loop(self) -> None:
        """Continuous background execution loop."""
        while self._running:
            try:
                delay = self._compute_next_delay()
            except Exception:
                logger.exception("Failed to compute next schedule delay, falling back to %ds", self.interval_seconds)
                delay = max(0.0, float(self.interval_seconds))

            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break

            if not self._running:
                break

            try:
                await self.execute_scrape_cycle()
            except asyncio.CancelledError:
                break
            except ScrapeAlreadyRunningError:
                logger.info("Scheduled scrape cycle skipped: another cycle is already active")
            except Exception:
                # Cycle failure is already persisted as a FAILED run by
                # execute_scrape_cycle; log here so the daemon loop's
                # continued resilience doesn't hide the error entirely.
                logger.exception("Scheduled scrape cycle failed")

    def run_in_background(self, coro: Any) -> asyncio.Task[Any]:
        """Schedule a coroutine as a background task, retaining a strong reference.

        Without this, asyncio only holds a weak reference to fire-and-forget
        tasks, making them eligible for garbage collection mid-execution.
        """
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)

        def _on_done(t: asyncio.Task[Any]) -> None:
            self._background_tasks.discard(t)
            if not t.cancelled() and t.exception() is not None:
                logger.error("Background scrape task failed", exc_info=t.exception())

        task.add_done_callback(_on_done)
        return task

    def start(self) -> asyncio.Task[None]:
        """Start the background periodic scheduling daemon."""
        if self.is_running and self._task is not None:
            return self._task

        self._running = True
        self._task = asyncio.create_task(self._schedule_loop())
        return self._task

    async def stop(self) -> None:
        """Gracefully stop the background scheduling daemon."""
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._background_tasks:
            tasks = list(self._background_tasks)
            for t in tasks:
                if not t.done():
                    t.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self._background_tasks.clear()

    async def aclose(self) -> None:
        """Clean up background tasks and internal scraper client."""
        await self.stop()
        if self._background_tasks:
            tasks = list(self._background_tasks)
            for t in tasks:
                if not t.done():
                    t.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self._background_tasks.clear()
        if self._owns_client:
            await self.client.aclose()
        if self.webhook_dispatcher is not None:
            await self.webhook_dispatcher.aclose()
