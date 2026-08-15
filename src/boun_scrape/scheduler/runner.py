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
from boun_scrape.domain.models import RunStatus, ScrapeRunSummary
from boun_scrape.feeds.webhooks import WebhookDispatcher
from boun_scrape.pipeline.delta import compute_deltas
from boun_scrape.pipeline.exporter import generate_all_exports
from boun_scrape.scraper.client import BounScraperClient
from boun_scrape.scraper.flow import discover_terms, scrape_term_pipeline
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
        self.cron_expression = cron_expression
        self.default_term = default_term
        self.export_dir = Path(export_dir)

        # Scraper client
        if client is not None:
            self.client = client
            self._owns_client = False
        else:
            self.client = BounScraperClient(settings=self.settings)
            self._owns_client = True

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
            "run_count": self._run_count,
            "last_run_time": (
                self._last_run_time.isoformat() if self._last_run_time else None
            ),
            "next_run_time": (
                self._next_run_time.isoformat() if self._next_run_time else None
            ),
            "last_run_summary": summary_dict,
        }

    async def execute_scrape_cycle(
        self,
        term: str | None = None,
        export: bool = True,
        dispatch_webhooks: bool = True,
    ) -> ScrapeRunSummary:
        """Execute a full scrape cycle with delta detection, persistence, exports, and feeds.

        Args:
            term: Specific academic term (e.g. '2024/2025-1'). If None, discovers the latest term.
            export: If True, generate JSON, CSV, SQLite, and delta artifacts.
            dispatch_webhooks: If True, send events to configured webhook endpoints.

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
            self.repository.save_scrape_run(summary)

            try:
                # 1. Target term resolution
                target_term = term or self.default_term
                if not target_term:
                    discovered = await discover_terms(self.client)
                    if not discovered:
                        raise ScrapeSchedulerError(
                            "No academic terms discovered from the registration portal."
                        )
                    target_term = discovered[0]
                summary.term = target_term

                # 2. Scrape latest courses and slots from portal
                current_courses = await scrape_term_pipeline(
                    self.client, term=target_term, concurrency=self.settings.max_concurrency
                )

                # 4. Fetch existing courses for term to detect deltas
                previous_courses = self.repository.get_courses_by_term(target_term)

                # 5. Compute change deltas
                deltas = compute_deltas(
                    previous_courses=previous_courses,
                    current_courses=current_courses,
                    run_id=run_id,
                    term=target_term,
                )

                # 6. Atomic persistence of courses, slots, and deltas
                self.repository.save_courses_and_slots(
                    term=target_term, courses=current_courses
                )
                if deltas:
                    self.repository.save_deltas(deltas=deltas, run_id=run_id)

                # 7. Calculate run metrics
                total_slots = sum(len(c.slots) for c in current_courses)
                completed_at = datetime.now(timezone.utc).isoformat()

                summary.status = RunStatus.COMPLETED
                summary.completed_at = completed_at
                summary.total_courses = len(current_courses)
                summary.total_slots = total_slots
                summary.changes_detected = len(deltas)
                self.repository.save_scrape_run(summary)

                # 8. Artifact exports
                if export:
                    generate_all_exports(
                        term=target_term,
                        courses=current_courses,
                        deltas=deltas,
                        output_dir=self.export_dir,
                    )

                # 9. Webhook notifications
                if dispatch_webhooks and self.webhook_dispatcher is not None:
                    if deltas:
                        await self.webhook_dispatcher.dispatch_deltas(
                            deltas, term=target_term
                        )
                    await self.webhook_dispatcher.dispatch_run_summary(summary)

                self._last_run_summary = summary
                self._last_run_time = datetime.now(timezone.utc)
                self._run_count += 1
                return summary

            except Exception as exc:
                completed_at = datetime.now(timezone.utc).isoformat()
                summary.status = RunStatus.FAILED
                summary.completed_at = completed_at
                summary.error_message = str(exc)
                self.repository.save_scrape_run(summary)

                if dispatch_webhooks and self.webhook_dispatcher is not None:
                    await self.webhook_dispatcher.dispatch_run_summary(summary)

                self._last_run_summary = summary
                self._last_run_time = datetime.now(timezone.utc)
                raise

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
            delay = self._compute_next_delay()
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

    async def aclose(self) -> None:
        """Clean up background tasks and internal scraper client."""
        await self.stop()
        if self._owns_client:
            await self.client.aclose()
        if self.webhook_dispatcher is not None:
            await self.webhook_dispatcher.aclose()
