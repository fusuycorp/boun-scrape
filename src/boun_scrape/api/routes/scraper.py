"""Scraper execution, control, status, and logging endpoints."""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from boun_scrape.api.deps import (
    get_log_buffer_dep,
    get_scrape_scheduler_dep,
)
from boun_scrape.api.logging_buffer import LogBuffer
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


@router.post(
    "/scraper/trigger",
    summary="Trigger an on-demand scraping cycle",
)
async def trigger_scrape(
    payload: ScrapeTriggerRequest,
    scheduler: Annotated[ScrapeScheduler, Depends(get_scrape_scheduler_dep)],
) -> Any:
    """Trigger a new scrape cycle with delta detection, persistence, exports, and webhooks."""
    if scheduler.is_scraping:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A scrape cycle is already in progress.",
        )

    if payload.background:
        asyncio.create_task(
            scheduler.execute_scrape_cycle(
                term=payload.term,
                export=payload.export,
                dispatch_webhooks=payload.dispatch_webhooks,
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
    )


@router.post(
    "/scraper/stop",
    summary="Stop background scraper scheduler daemon",
)
async def stop_scraper(
    scheduler: Annotated[ScrapeScheduler, Depends(get_scrape_scheduler_dep)],
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
) -> list[LogEntryDTO]:
    """Retrieve in-memory circular log records for monitoring and debugging."""
    return log_buffer.get_logs(limit=limit, level=level)
