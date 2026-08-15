"""Live quota query endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from boun_scrape.api.deps import (
    get_course_repo_dep,
    get_quota_service_dep,
    get_scraper_client_dep,
)
from boun_scrape.domain.dto import (
    BatchQuotaRequest,
    QuotaDTO,
    quota_to_dto,
)
from boun_scrape.scraper.client import BounScraperClient
from boun_scrape.scraper.flow import discover_terms
from boun_scrape.scraper.quota import QuotaService
from boun_scrape.storage.repository import CourseRepository

router = APIRouter(tags=["Quota"])


async def _resolve_term(
    term: str | None,
    repo: CourseRepository,
    client: BounScraperClient,
) -> str:
    """Resolve target term, falling back to database latest or portal discovery."""
    if term and term.strip():
        return term.strip()

    db_terms = repo.get_terms()
    if db_terms:
        return db_terms[0]

    discovered = await discover_terms(client)
    if discovered:
        return discovered[0]

    return "current"


@router.get(
    "/quota",
    response_model=list[QuotaDTO],
    summary="Query live quota for a course section",
)
async def get_course_quota(
    quota_service: Annotated[QuotaService, Depends(get_quota_service_dep)],
    repo: Annotated[CourseRepository, Depends(get_course_repo_dep)],
    client: Annotated[BounScraperClient, Depends(get_scraper_client_dep)],
    abbr: str = Query(..., min_length=1, description="Department abbreviation (e.g. CMPE)"),
    code: str = Query(..., min_length=1, description="Course code (e.g. 150 or CMPE 150)"),
    section: str = Query(default="", description="Course section number (e.g. 01)"),
    term: str | None = Query(default=None, description="Academic term (defaults to active term)"),
    bypass_cache: bool = Query(default=False, description="Bypass in-memory TTL cache"),
) -> list[QuotaDTO]:
    """Fetch real-time quota allocations and remaining seats directly from registration portal."""
    target_term = await _resolve_term(term, repo, client)
    records = await quota_service.fetch_quota(
        term=target_term,
        abbr=abbr,
        code=code,
        section=section,
        bypass_cache=bypass_cache,
    )
    return [quota_to_dto(r) for r in records]


@router.post(
    "/quota/batch",
    response_model=dict[str, list[QuotaDTO]],
    summary="Batch query quota for multiple courses concurrently",
)
async def get_batch_course_quota(
    payload: BatchQuotaRequest,
    quota_service: Annotated[QuotaService, Depends(get_quota_service_dep)],
) -> dict[str, list[QuotaDTO]]:
    """Fetch live quotas for multiple course sections concurrently with rate-limiting."""
    query_items = [
        (item.term, item.abbr, item.code, item.section)
        for item in payload.items
    ]
    results = await quota_service.fetch_batch_quotas(
        items=query_items,
        concurrency=payload.concurrency,
        bypass_cache=payload.bypass_cache,
    )
    return {
        key: [quota_to_dto(r) for r in records]
        for key, records in results.items()
    }
