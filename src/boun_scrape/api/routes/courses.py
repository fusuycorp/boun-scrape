"""Course catalog, department, and term query endpoints."""

import hashlib
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from boun_scrape.api.deps import get_course_repo_dep
from boun_scrape.domain.dto import (
    CourseDTO,
    CourseFilterParams,
    DepartmentDTO,
    PaginatedResponse,
    StatsDTO,
    course_to_dto,
    department_to_dto,
)
from boun_scrape.domain.models import compute_course_hash
from boun_scrape.storage.repository import CourseRepository

router = APIRouter(tags=["Courses"])


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
    "/courses",
    response_model=PaginatedResponse[CourseDTO],
    summary="Query and filter courses with pagination",
)
def get_courses(
    request: Request,
    response: Response,
    repo: Annotated[CourseRepository, Depends(get_course_repo_dep)],
    term: str | None = Query(default=None, description="Academic term identifier (e.g. 2024/2025-1)"),
    department: str | None = Query(default=None, description="Department code (e.g. CMPE)"),
    course_code: str | None = Query(default=None, description="Course code filter (e.g. CMPE150 or 150)"),
    instructor: str | None = Query(default=None, description="Instructor name substring"),
    day: str | None = Query(default=None, description="Schedule day token (e.g. M, T, W, Th, F, St, Su)"),
    hour: str | None = Query(default=None, description="Class period hour substring (e.g. 1, 2, 34, 10)"),
    room: str | None = Query(default=None, description="Classroom / lecture hall filter (e.g. NH101)"),
    slot_title: str | None = Query(default=None, description="Slot title or PS/Lab indicator"),
    keyword: str | None = Query(default=None, description="Fulltext keyword search over course fields"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(default=50, ge=1, le=500, description="Items per page"),
) -> Any:
    """Retrieve paginated course catalog entries matching given filter parameters."""
    filters = CourseFilterParams(
        term=term,
        department=department,
        course_code=course_code,
        instructor=instructor,
        day=day,
        hour=hour,
        room=room,
        slot_title=slot_title,
        keyword=keyword,
        page=page,
        size=size,
    )
    courses, total = repo.get_courses(filters)
    pages = (total + size - 1) // size if total > 0 else 0
    items = [course_to_dto(c) for c in courses]

    # Compute weak ETag based on pagination parameters, total matches, and course content hashes
    item_signatures = [f"{c.id}:{compute_course_hash(c)}" for c in courses]
    etag_raw = f"{total}:{page}:{size}:{','.join(item_signatures)}"
    etag = f'W/"{hashlib.sha1(etag_raw.encode()).hexdigest()}"'

    if _matches_etag(request.headers.get("if-none-match"), etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})

    response.headers["ETag"] = etag
    return PaginatedResponse[CourseDTO](
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get(
    "/courses/{course_id}",
    response_model=CourseDTO,
    summary="Get single course by ID",
)
def get_course_by_id(
    course_id: int,
    repo: Annotated[CourseRepository, Depends(get_course_repo_dep)],
) -> CourseDTO:
    """Retrieve a single course and its session slots by database ID."""
    course = repo.get_course_by_id(course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID {course_id} not found.",
        )
    return course_to_dto(course)


@router.get(
    "/departments",
    response_model=list[DepartmentDTO],
    summary="List all academic departments",
)
def get_departments(
    request: Request,
    response: Response,
    repo: Annotated[CourseRepository, Depends(get_course_repo_dep)],
    term: str | None = Query(default=None, description="Optional term filter"),
) -> Any:
    """Retrieve academic departments offering courses."""
    depts = repo.get_departments(term=term)
    items = [department_to_dto(d) for d in depts]

    # Compute weak ETag based on term, count, and department codes
    depts_summary = f"{term or 'all'}:{len(depts)}:{','.join(d.code for d in depts)}"
    etag = f'W/"{hashlib.sha1(depts_summary.encode()).hexdigest()}"'

    if _matches_etag(request.headers.get("if-none-match"), etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})

    response.headers["ETag"] = etag
    return items


@router.get(
    "/terms",
    response_model=list[str],
    summary="List all discovered academic terms",
)
def get_terms(
    request: Request,
    response: Response,
    repo: Annotated[CourseRepository, Depends(get_course_repo_dep)],
) -> Any:
    """Retrieve list of unique academic terms present in the system."""
    terms = repo.get_terms()
    terms_summary = f"terms:{len(terms)}:{','.join(terms)}"
    etag = f'W/"{hashlib.sha1(terms_summary.encode()).hexdigest()}"'

    if _matches_etag(request.headers.get("if-none-match"), etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag, "Cache-Control": "public, max-age=60"})

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=60"
    return terms


@router.get(
    "/stats",
    response_model=StatsDTO,
    summary="Get aggregate database statistics",
)
def get_stats(repo: Annotated[CourseRepository, Depends(get_course_repo_dep)]) -> StatsDTO:
    """Retrieve aggregate course, slot, department, and term counts plus last scrape time."""
    terms = repo.get_terms()
    depts = repo.get_departments()
    latest_run = repo.get_latest_run()

    with repo.db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM courses")
        total_courses = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM course_slots")
        total_slots = cursor.fetchone()[0]

    last_cached_depts = repo.get_departments_last_cached_at()

    return StatsDTO(
        total_courses=total_courses,
        total_slots=total_slots,
        total_departments=len(depts),
        total_terms=len(terms),
        last_scraped=latest_run.completed_at if latest_run else None,
        last_cached_departments_at=last_cached_depts,
    )
