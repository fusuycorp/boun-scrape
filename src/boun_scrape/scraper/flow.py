"""Asynchronous scraping workflows for Boğaziçi course schedules."""

import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import Any

from boun_scrape.domain.models import Course, Department, TermScrapeResult
from boun_scrape.scraper.client import BounScraperClient
from boun_scrape.scraper.parser import (
    extract_viewstate_and_semesters,
    parse_departments_from_html,
    parse_schedules_from_html,
)

logger = logging.getLogger(__name__)

SCHEDULE_SEMESTER_URL = "/buis/General/schedule.aspx?p=semester"
SCHEDULE_DEPT_URL = "/scripts/sch.asp"


async def discover_terms(client: BounScraperClient) -> list[str]:
    """Discover available academic terms from the schedule semester page."""
    response = await client.get(SCHEDULE_SEMESTER_URL)
    _, terms = extract_viewstate_and_semesters(response.text)
    return terms


async def fetch_departments(client: BounScraperClient, term: str) -> list[Department]:
    """Fetch the list of departments offering courses in a given term."""
    # Step 1: Initial GET to obtain ASP.NET ViewState and token fields
    init_resp = await client.get(SCHEDULE_SEMESTER_URL)
    vs_dict, _ = extract_viewstate_and_semesters(init_resp.text)

    # Step 2: Submit search form for target semester
    post_data = {
        "__VIEWSTATE": vs_dict.get("__VIEWSTATE", ""),
        "__VIEWSTATEGENERATOR": vs_dict.get("__VIEWSTATEGENERATOR", ""),
        "__EVENTVALIDATION": vs_dict.get("__EVENTVALIDATION", ""),
        "ctl00$cphMainContent$ddlSemester": term,
        "ctl00$cphMainContent$btnSearch": "Go",
        "ctl00$cphMainContent$gRecResp": client.recaptcha_token,
    }

    resp = await client.post(SCHEDULE_SEMESTER_URL, data=post_data)
    departments = parse_departments_from_html(resp.text)

    if not departments:
        logger.warning("fetch_departments: no departments found in response for term %s", term)

    return departments


async def fetch_department_schedule(
    client: BounScraperClient, term: str, dept: Department | str
) -> list[Course]:
    """Fetch and parse all courses and slots for a single department in a term."""
    if isinstance(dept, Department):
        dept_code = dept.code
        bolum = dept.bolum or dept.name
    else:
        dept_code = str(dept)
        bolum = ""

    params = {
        "donem": term,
        "kisaadi": dept_code,
        "bolum": bolum,
    }

    response = await client.get(SCHEDULE_DEPT_URL, params=params)
    return parse_schedules_from_html(
        response.text,
        term=term,
        department_code=dept_code,
    )


async def scrape_term_pipeline(
    client: BounScraperClient,
    term: str,
    progress_callback: (
        Callable[[int, int, Department, list[Course]], Any] | None
    ) = None,
    concurrency: int = 10,
) -> TermScrapeResult:
    """Execute end-to-end term scraping pipeline with concurrency rate-limiting.

    Args:
        client: The scraper client instance.
        term: Term string identifier (e.g. '2024/2025-1').
        progress_callback: Callback invoked when a department completes:
            (completed_count, total_count, department, courses).
        concurrency: Maximum number of concurrent department requests.

    Returns:
        TermScrapeResult with aggregated courses and per-department success/failure tracking.
    """
    departments = await fetch_departments(client, term)
    if not departments:
        return TermScrapeResult(
            courses=[], departments=[], succeeded_departments=[], failed_departments=[]
        )

    total_depts = len(departments)
    completed_count = 0
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(concurrency)

    async def _scrape_single_dept(dept: Department) -> list[Course]:
        nonlocal completed_count
        async with sem:
            courses = await fetch_department_schedule(client, term, dept)
            async with lock:
                completed_count += 1
                current_completed = completed_count

            if progress_callback is not None:
                cb_res = progress_callback(
                    current_completed, total_depts, dept, courses
                )
                if inspect.isawaitable(cb_res):
                    await cb_res

            return courses

    results = await asyncio.gather(
        *[_scrape_single_dept(d) for d in departments], return_exceptions=True
    )
    all_courses: list[Course] = []
    failures: list[tuple[Department, BaseException]] = []
    succeeded_departments: list[str] = []
    failed_departments: list[str] = []
    for dept, result in zip(departments, results):
        if isinstance(result, BaseException):
            failures.append((dept, result))
            failed_departments.append(dept.code)
            continue
        all_courses.extend(result)
        succeeded_departments.append(dept.code)

    if failures:
        logger.warning(
            "%d/%d departments failed to scrape for term %s: %s",
            len(failures),
            total_depts,
            term,
            ", ".join(f"{dept.code}: {exc}" for dept, exc in failures),
        )

    return TermScrapeResult(
        courses=all_courses,
        departments=departments,
        succeeded_departments=succeeded_departments,
        failed_departments=failed_departments,
    )
