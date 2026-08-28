"""Scraper execution, control, status, and logging endpoints."""

import os
import tempfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from boun_scrape.api.auth import get_current_user
from boun_scrape.api.deps import (
    get_course_repo_dep,
    get_log_buffer_dep,
    get_scrape_scheduler_dep,
    get_scraper_client_dep,
    get_settings_dep,
)
from boun_scrape.scraper.client import BounScraperClient, parse_curl_command
from boun_scrape.storage.repository import CourseRepository
from boun_scrape.api.logging_buffer import LogBuffer
from boun_scrape.config import Settings
from boun_scrape.domain.dto import (
    LogEntryDTO,
    ScrapeRunDTO,
    ScrapeStatusDTO,
    ScrapeTriggerRequest,
    ScheduleConfigDTO,
    ScheduleConfigRequest,
    TermCoverageSummaryDTO,
    run_to_dto,
)
from boun_scrape.scheduler.runner import (
    ScrapeAlreadyRunningError,
    ScrapeScheduler,
)

router = APIRouter(tags=["Scraper"])


class CookieUpdateRequest(BaseModel):
    cookies: str = Field(min_length=1)


@router.post(
    "/scraper/trigger",
    summary="Trigger an on-demand scraping cycle",
)
async def trigger_scrape(
    payload: ScrapeTriggerRequest,
    scheduler: Annotated[ScrapeScheduler, Depends(get_scrape_scheduler_dep)],
    current_user: str = Depends(get_current_user),
) -> Any:
    """Trigger a new scrape cycle with delta detection, persistence, exports, and webhooks."""
    if scheduler.is_scraping:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A scrape cycle is already in progress.",
        )

    if payload.all_terms:
        scheduler.run_in_background(
            scheduler.execute_all_terms_cycle(
                export=payload.export,
                dispatch_webhooks=payload.dispatch_webhooks,
                capture_quota=payload.capture_quota,
            )
        )
        return {
            "status": "triggered",
            "message": "All-terms scrape cycle started in background.",
            "all_terms": True,
        }

    if payload.background:
        scheduler.run_in_background(
            scheduler.execute_scrape_cycle(
                term=payload.term,
                export=payload.export,
                dispatch_webhooks=payload.dispatch_webhooks,
                capture_quota=payload.capture_quota,
                target_departments=payload.departments,
                skip_already_scraped=payload.skip_already_scraped,
            )
        )
        return {
            "status": "triggered",
            "message": "Scrape cycle started in background.",
            "term": payload.term,
            "departments": payload.departments,
            "skip_already_scraped": payload.skip_already_scraped,
        }

    try:
        summary = await scheduler.execute_scrape_cycle(
            term=payload.term,
            export=payload.export,
            dispatch_webhooks=payload.dispatch_webhooks,
            capture_quota=payload.capture_quota,
            target_departments=payload.departments,
            skip_already_scraped=payload.skip_already_scraped,
        )
        return run_to_dto(summary)
    except ScrapeAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/scraper/coverage",
    response_model=TermCoverageSummaryDTO,
    summary="Get department scrape coverage and status breakdown",
)
def get_scraper_coverage(
    term: str | None = Query(default=None, description="Academic term (e.g. '2026/2027-1')"),
    repo: Annotated[CourseRepository, Depends(get_course_repo_dep)] = None,
    scheduler: Annotated[ScrapeScheduler, Depends(get_scrape_scheduler_dep)] = None,
    current_user: str = Depends(get_current_user),
) -> TermCoverageSummaryDTO:
    """Retrieve per-department scrape results, course counts, and completion status."""
    target_term = term
    if not target_term:
        target_term = scheduler.default_term
    if not target_term:
        terms = repo.get_terms()
        target_term = terms[0] if terms else "unresolved"

    return repo.get_term_coverage(target_term)


@router.get(
    "/scraper/status",
    response_model=ScrapeStatusDTO,
    summary="Get current scraper operational status and metrics",
)
def get_scraper_status(
    scheduler: Annotated[ScrapeScheduler, Depends(get_scrape_scheduler_dep)],
    current_user: str = Depends(get_current_user),
) -> ScrapeStatusDTO:
    """Retrieve operational health, active run status, and scheduler metrics."""
    stat = scheduler.get_status()
    return ScrapeStatusDTO(
        is_running=stat["is_running"],
        is_scraping=stat["is_scraping"],
        interval_seconds=stat["interval_seconds"],
        cron_expression=stat["cron_expression"],
        default_term=stat.get("default_term"),
        run_count=stat["run_count"],
        last_run_time=stat["last_run_time"],
        next_run_time=stat["next_run_time"],
        last_run_summary=stat["last_run_summary"],
        current_progress=stat.get("current_progress"),
    )


@router.get(
    "/scraper/schedule",
    response_model=ScheduleConfigDTO,
    summary="Get periodic scheduler configuration and daemon state",
)
def get_schedule_config(
    scheduler: Annotated[ScrapeScheduler, Depends(get_scrape_scheduler_dep)],
    current_user: str = Depends(get_current_user),
) -> ScheduleConfigDTO:
    """Get timing, cron expression, default term, and active running state."""
    stat = scheduler.get_status()
    return ScheduleConfigDTO(
        interval_seconds=stat["interval_seconds"],
        cron_expression=stat["cron_expression"],
        default_term=stat.get("default_term"),
        is_running=stat["is_running"],
    )


@router.post(
    "/scraper/schedule",
    response_model=ScheduleConfigDTO,
    summary="Update periodic scheduler configuration",
)
async def update_schedule_config(
    payload: ScheduleConfigRequest,
    scheduler: Annotated[ScrapeScheduler, Depends(get_scrape_scheduler_dep)],
    current_user: str = Depends(get_current_user),
) -> ScheduleConfigDTO:
    """Update timing, cron expression, or default term for periodic background scraping."""
    scheduler.update_config(
        interval_seconds=payload.interval_seconds,
        cron_expression=payload.cron_expression,
        default_term=payload.default_term,
    )
    stat = scheduler.get_status()
    return ScheduleConfigDTO(
        interval_seconds=stat["interval_seconds"],
        cron_expression=stat["cron_expression"],
        default_term=stat.get("default_term"),
        is_running=stat["is_running"],
    )


@router.post(
    "/scraper/start-daemon",
    summary="Start background periodic scheduler daemon",
)
async def start_scheduler_daemon(
    scheduler: Annotated[ScrapeScheduler, Depends(get_scrape_scheduler_dep)],
    current_user: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Start the periodic background daemon loop."""
    scheduler.start()
    return {
        "status": "started",
        "message": "Background periodic scraper daemon started.",
        "is_running": scheduler.is_running,
    }


@router.post(
    "/scraper/stop-daemon",
    summary="Stop background periodic scheduler daemon",
)
async def stop_scheduler_daemon(
    scheduler: Annotated[ScrapeScheduler, Depends(get_scrape_scheduler_dep)],
    current_user: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Stop the periodic background daemon loop."""
    await scheduler.stop()
    return {
        "status": "stopped",
        "message": "Background periodic scraper daemon stopped.",
        "is_running": scheduler.is_running,
    }


@router.post(
    "/scraper/stop",
    summary="Halt active scrape cycle and background daemon",
)
async def stop_scraper(
    scheduler: Annotated[ScrapeScheduler, Depends(get_scrape_scheduler_dep)],
    current_user: str = Depends(get_current_user),
) -> dict[str, str]:
    """Halt any active scrape cycle and background tasks."""
    await scheduler.stop()
    return {
        "status": "stopped",
        "message": "Scraper execution halted.",
    }


@router.get(
    "/scraper/logs",
    response_model=list[LogEntryDTO],
    summary="Get buffered application logs",
)
def get_scraper_logs(
    log_buffer: Annotated[LogBuffer, Depends(get_log_buffer_dep)],
    limit: int = Query(default=100, ge=1, le=1000, description="Max log lines to return"),
    level: str | None = Query(default=None, description="Minimum log level filter (INFO, WARNING, ERROR)"),
    clear: bool = Query(default=False, description="Clear the buffer after reading"),
    current_user: str = Depends(get_current_user),
) -> list[LogEntryDTO]:
    """Retrieve in-memory circular log records for monitoring and debugging."""
    logs = log_buffer.get_logs(limit=limit, level=level)
    if clear:
        log_buffer.clear()
    return logs


@router.get("/scraper/config", summary="Get scraper cookie and token configuration status")
def get_scraper_config(
    settings: Annotated[Settings, Depends(get_settings_dep)],
    current_user: str = Depends(get_current_user),
) -> dict[str, bool]:
    """Report whether non-empty session cookie or reCAPTCHA token files are currently mounted."""
    cookie_loaded = os.path.exists(settings.cookies_path) and os.path.getsize(settings.cookies_path) > 0
    recaptcha_loaded = os.path.exists(settings.recaptcha_token_path) and os.path.getsize(settings.recaptcha_token_path) > 0
    return {"cookie_loaded": cookie_loaded, "recaptcha_loaded": recaptcha_loaded}


@router.post("/scraper/config", summary="Update scraper session cookies or cURL command")
def update_scraper_config(
    payload: CookieUpdateRequest,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    client: Annotated[BounScraperClient, Depends(get_scraper_client_dep)],
    current_user: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Write a new session cookie string or parse a raw cURL command into cookies and reCAPTCHA token."""
    raw_input = payload.cookies.strip()
    extracted_token = False
    cookie_str = raw_input

    if raw_input.startswith("curl ") or "\ncurl " in raw_input or "curl '" in raw_input or 'curl "' in raw_input:
        extracted = parse_curl_command(raw_input)
        if extracted.get("cookies"):
            cookie_str = extracted["cookies"]
        if extracted.get("recaptcha_token"):
            recaptcha_path = Path(settings.recaptcha_token_path)
            recaptcha_path.parent.mkdir(parents=True, exist_ok=True)
            recaptcha_path.write_text(extracted["recaptcha_token"], encoding="utf-8")
            extracted_token = True

    cookie_path = Path(settings.cookies_path)
    cookie_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(cookie_path.parent), prefix="cookies_", suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(cookie_str)
        os.replace(tmp_path, cookie_path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    client.reload_cookies()
    msg = "Cookie configuration updated."
    if extracted_token:
        msg = "Cookies and reCAPTCHA token extracted from cURL command successfully."

    return {
        "status": "ok",
        "message": msg,
        "cookie_loaded": True,
        "recaptcha_loaded": extracted_token,
    }
