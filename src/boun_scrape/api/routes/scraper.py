"""Scraper execution, control, status, and logging endpoints."""

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from boun_scrape.api.auth import get_current_user
from boun_scrape.api.deps import (
    get_log_buffer_dep,
    get_scrape_scheduler_dep,
    get_settings_dep,
)
from boun_scrape.api.logging_buffer import LogBuffer
from boun_scrape.config import Settings
from boun_scrape.domain.dto import (
    LogEntryDTO,
    ScrapeRunDTO,
    ScrapeStatusDTO,
    ScrapeTriggerRequest,
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
            )
        )
        return {
            "status": "triggered",
            "message": "Scrape cycle started in background.",
            "term": payload.term,
        }

    try:
        summary = await scheduler.execute_scrape_cycle(
            term=payload.term,
            export=payload.export,
            dispatch_webhooks=payload.dispatch_webhooks,
            capture_quota=payload.capture_quota,
        )
        return run_to_dto(summary)
    except ScrapeAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


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
        run_count=stat["run_count"],
        last_run_time=stat["last_run_time"],
        next_run_time=stat["next_run_time"],
        last_run_summary=stat["last_run_summary"],
        current_progress=stat.get("current_progress"),
    )


@router.post(
    "/scraper/stop",
    summary="Stop background scraper scheduler daemon",
)
async def stop_scraper(
    scheduler: Annotated[ScrapeScheduler, Depends(get_scrape_scheduler_dep)],
    current_user: str = Depends(get_current_user),
) -> dict[str, str]:
    """Stop the background periodic scheduler loop."""
    await scheduler.stop()
    return {
        "status": "stopped",
        "message": "Scraper scheduler stopped.",
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


@router.get("/scraper/config", summary="Get scraper cookie configuration status")
def get_scraper_config(
    settings: Annotated[Settings, Depends(get_settings_dep)],
    current_user: str = Depends(get_current_user),
) -> dict[str, bool]:
    """Report whether a non-empty session cookie file is currently mounted."""
    cookie_loaded = os.path.exists(settings.cookies_path) and os.path.getsize(settings.cookies_path) > 0
    return {"cookie_loaded": cookie_loaded}


@router.post("/scraper/config", summary="Update scraper session cookies")
def update_scraper_config(
    payload: CookieUpdateRequest,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    current_user: str = Depends(get_current_user),
) -> dict[str, str]:
    """Write a new session cookie string to the scraper's cookie file."""
    with open(settings.cookies_path, "w", encoding="utf-8") as f:
        f.write(payload.cookies)
    return {"status": "ok", "message": "Cookie configuration updated."}
