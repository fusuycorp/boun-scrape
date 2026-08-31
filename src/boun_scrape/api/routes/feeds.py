"""Downstream feed endpoints for change deltas, run histories, and file exports."""

import asyncio
import hashlib
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse

from boun_scrape.api.deps import get_course_repo_dep, get_settings_dep
from boun_scrape.config import Settings
from boun_scrape.domain.dto import (
    DeltaEventDTO,
    QuotaSnapshotDTO,
    ScrapeRunDTO,
    delta_to_dto,
    quota_snapshot_to_dto,
    run_to_dto,
)
from boun_scrape.pipeline.exporter import _sanitize_term, generate_all_exports
from boun_scrape.storage.repository import CourseRepository

router = APIRouter(tags=["Feeds"])

_export_async_lock = asyncio.Lock()

FORMAT_MEDIA_TYPES: dict[str, tuple[str, str]] = {
    "json": ("application/json", "json"),
    "csv": ("text/csv; charset=utf-8", "csv"),
    "sqlite": ("application/vnd.sqlite3", "db"),
    "db": ("application/vnd.sqlite3", "db"),
}


def _matches_etag(if_none_match: str | None, etag: str) -> bool:
    """Check if the provided If-None-Match header value matches the computed ETag."""
    if not if_none_match:
        return False
    candidates = [t.strip() for t in if_none_match.split(",")]
    if "*" in candidates:
        return True
    clean_etag = etag.lstrip("W/").strip('"')
    for candidate in candidates:
        if candidate == etag or candidate.lstrip("W/").strip('"') == clean_etag:
            return True
    return False


@router.get(
    "/feeds/deltas",
    response_model=list[DeltaEventDTO],
    summary="Get detected course change deltas",
)
def get_deltas(
    request: Request,
    response: Response,
    repo: Annotated[CourseRepository, Depends(get_course_repo_dep)],
    term: str | None = Query(default=None, description="Filter deltas by academic term"),
    run_id: str | None = Query(default=None, description="Filter deltas by specific scrape run ID"),
    after_timestamp: str | None = Query(default=None, description="Only return deltas created strictly after this timestamp"),
    since: str | None = Query(default=None, description="Only return deltas created on or after this timestamp"),
    until: str | None = Query(default=None, description="Only return deltas created on or before this timestamp"),
    order: str = Query(default="desc", pattern="^(asc|desc|ASC|DESC)$", description="Sort order by timestamp (asc or desc)"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max deltas to return"),
) -> Any:
    """Retrieve historical course change delta events."""
    deltas = repo.get_deltas(
        term=term,
        run_id=run_id,
        after_timestamp=after_timestamp,
        since=since,
        until=until,
        order=order,
        limit=limit,
    )
    dtos = [delta_to_dto(d) for d in deltas]

    if dtos:
        summary = f"deltas:{len(dtos)}:{dtos[0].timestamp}:{dtos[-1].timestamp}"
    else:
        summary = f"deltas:empty:{term or 'all'}"
    etag = f'W/"{hashlib.sha1(summary.encode()).hexdigest()}"'

    if _matches_etag(request.headers.get("if-none-match"), etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag, "Cache-Control": "public, max-age=5"})

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=5"
    return dtos


@router.get(
    "/feeds/runs",
    response_model=list[ScrapeRunDTO],
    summary="Get scrape execution history",
)
def get_scrape_runs(
    repo: Annotated[CourseRepository, Depends(get_course_repo_dep)],
    term: str | None = Query(default=None, description="Filter runs by academic term"),
    limit: int = Query(default=50, ge=1, le=500, description="Max runs to return"),
) -> list[ScrapeRunDTO]:
    """Retrieve scrape run execution history and summaries."""
    runs = repo.get_scrape_runs(term=term, limit=limit)
    return [run_to_dto(r) for r in runs]


@router.get(
    "/feeds/quota-snapshots",
    response_model=list[QuotaSnapshotDTO],
    summary="Get captured quota snapshots",
)
def get_quota_snapshots(
    request: Request,
    response: Response,
    repo: Annotated[CourseRepository, Depends(get_course_repo_dep)],
    term: str | None = Query(default=None, description="Filter snapshots by academic term"),
    after_timestamp: str | None = Query(default=None, description="Only return snapshots captured strictly after this timestamp"),
    since: str | None = Query(default=None, description="Only return snapshots captured on or after this timestamp"),
    until: str | None = Query(default=None, description="Only return snapshots captured on or before this timestamp"),
    order: str = Query(default="asc", pattern="^(asc|desc|ASC|DESC)$", description="Sort order by timestamp (asc or desc)"),
    limit: int = Query(default=500, ge=1, le=5000, description="Max snapshots to return"),
) -> Any:
    """Retrieve captured point-in-time quota snapshots, for incremental polling by downstream consumers."""
    snapshots = repo.get_quota_snapshots(
        term=term,
        after_timestamp=after_timestamp,
        since=since,
        until=until,
        order=order,
        limit=limit,
    )
    dtos = [quota_snapshot_to_dto(s) for s in snapshots]

    if dtos:
        summary = f"quota:{len(dtos)}:{dtos[0].captured_at}:{dtos[-1].captured_at}"
    else:
        summary = f"quota:empty:{term or 'all'}"
    etag = f'W/"{hashlib.sha1(summary.encode()).hexdigest()}"'

    if _matches_etag(request.headers.get("if-none-match"), etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag, "Cache-Control": "public, max-age=5"})

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=5"
    return dtos


@router.get(
    "/feeds/exports/{term}/{format}",
    summary="Download compiled course export artifact",
)
async def download_export(
    term: str,
    format: str,
    repo: Annotated[CourseRepository, Depends(get_course_repo_dep)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> FileResponse:
    """Download compiled JSON, CSV, or standalone SQLite database artifact for a given term."""
    fmt = format.lower().strip()
    if fmt not in FORMAT_MEDIA_TYPES:
        supported = ", ".join(sorted(FORMAT_MEDIA_TYPES.keys()))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{format}'. Supported formats: {supported}.",
        )

    media_type, ext = FORMAT_MEDIA_TYPES[fmt]
    export_dir = Path(settings.export_dir)

    # Resolve candidate term representations (e.g. 2026/2027-1, 2026_2027-1, 2026-2027-1)
    import re
    term_candidates = [term]
    if "_" in term:
        term_candidates.append(term.replace("_", "/"))
    if "/" in term:
        term_candidates.append(term.replace("/", "_"))
    if re.match(r"^\d{4}-\d{4}-\d$", term):
        term_candidates.append(re.sub(r"^(\d{4})-(\d{4}-\d)$", r"\1/\2", term))
        term_candidates.append(re.sub(r"^(\d{4})-(\d{4}-\d)$", r"\1_\2", term))

    target_path = None
    for cand in term_candidates:
        cand_safe = _sanitize_term(cand)
        cand_path = export_dir / f"courses_{cand_safe}.{ext}"
        if cand_path.exists():
            target_path = cand_path
            break

    if target_path is None or not target_path.exists():
        async with _export_async_lock:
            for cand in term_candidates:
                cand_safe = _sanitize_term(cand)
                cand_path = export_dir / f"courses_{cand_safe}.{ext}"
                if cand_path.exists():
                    target_path = cand_path
                    break

            if target_path is None or not target_path.exists():
                courses = []
                resolved_term = term
                for cand in term_candidates:
                    courses = await asyncio.to_thread(repo.get_courses_by_term, cand)
                    if courses:
                        resolved_term = cand
                        break

                if not courses:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"No courses or exports available for term '{term}'.",
                    )
                safe_term = _sanitize_term(resolved_term)
                await asyncio.to_thread(generate_all_exports, term=resolved_term, courses=courses, output_dir=export_dir)
                target_path = export_dir / f"courses_{safe_term}.{ext}"

    if not target_path or not target_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export artifact could not be generated for term '{term}'.",
        )

    return FileResponse(
        path=str(target_path),
        media_type=media_type,
        filename=target_path.name,
    )
