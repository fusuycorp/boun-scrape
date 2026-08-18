"""Downstream feed endpoints for change deltas, run histories, and file exports."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
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

FORMAT_MEDIA_TYPES: dict[str, tuple[str, str]] = {
    "json": ("application/json", "json"),
    "csv": ("text/csv; charset=utf-8", "csv"),
    "sqlite": ("application/vnd.sqlite3", "db"),
    "db": ("application/vnd.sqlite3", "db"),
}


@router.get(
    "/feeds/deltas",
    response_model=list[DeltaEventDTO],
    summary="Get detected course change deltas",
)
def get_deltas(
    repo: Annotated[CourseRepository, Depends(get_course_repo_dep)],
    term: str | None = Query(default=None, description="Filter deltas by academic term"),
    run_id: str | None = Query(default=None, description="Filter deltas by specific scrape run ID"),
    after_timestamp: str | None = Query(default=None, description="Only return deltas created strictly after this timestamp (same format as the timestamp field in returned entries)"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max deltas to return"),
) -> list[DeltaEventDTO]:
    """Retrieve historical course change delta events."""
    deltas = repo.get_deltas(term=term, run_id=run_id, after_timestamp=after_timestamp, limit=limit)
    return [delta_to_dto(d) for d in deltas]


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
    repo: Annotated[CourseRepository, Depends(get_course_repo_dep)],
    term: str | None = Query(default=None, description="Filter snapshots by academic term"),
    after_timestamp: str | None = Query(default=None, description="Only return snapshots captured strictly after this timestamp"),
    limit: int = Query(default=500, ge=1, le=5000, description="Max snapshots to return"),
) -> list[QuotaSnapshotDTO]:
    """Retrieve captured point-in-time quota snapshots, for incremental polling by downstream consumers."""
    snapshots = repo.get_quota_snapshots(term=term, after_timestamp=after_timestamp, limit=limit)
    return [quota_snapshot_to_dto(s) for s in snapshots]


@router.get(
    "/feeds/exports/{term}/{format}",
    summary="Download compiled course export artifact",
)
def download_export(
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
    safe_term = _sanitize_term(term)
    filename = f"courses_{safe_term}.{ext}"
    export_dir = Path(settings.export_dir)
    target_path = export_dir / filename

    if not target_path.exists():
        courses = repo.get_courses_by_term(term)
        if not courses and "_" in term:
            courses = repo.get_courses_by_term(term.replace("_", "/"))
        if not courses and "/" in term:
            courses = repo.get_courses_by_term(term.replace("/", "_"))

        if not courses:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No courses or exports available for term '{term}'.",
            )
        generate_all_exports(term=term, courses=courses, output_dir=export_dir)

    if not target_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export artifact could not be generated for term '{term}'.",
        )

    return FileResponse(
        path=str(target_path),
        media_type=media_type,
        filename=filename,
    )
