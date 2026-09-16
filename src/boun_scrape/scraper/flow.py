"""Asynchronous scraping workflows for Boğaziçi course schedules."""

import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import Any

from boun_scrape.domain.models import Course, Department, TermScrapeResult
from boun_scrape.scraper.client import BounHttpError, BounScraperClient
from boun_scrape.scraper.parser import (
    extract_viewstate_and_semesters,
    parse_departments_from_html,
    parse_schedules_from_html,
)

logger = logging.getLogger(__name__)

SCHEDULE_SEMESTER_URL = "/buis/General/schedule.aspx?p=semester"
SCHEDULE_DEPT_URL = "/scripts/sch.asp"


DEFAULT_KNOWN_DEPARTMENT_CODES: list[tuple[str, str]] = [
    ("AD", "ADMINISTRATION"),
    ("AE", "ADULT EDUCATION"),
    ("ASIA", "ASIAN STUDIES"),
    ("ATA", "ATATURK INSTITUTE FOR MODERN TURKISH HISTORY"),
    ("AUTO", "AUTOMOTIVE ENGINEERING"),
    ("BIS", "BUSINESS INFORMATION SYSTEMS"),
    ("BM", "BIOMEDICAL ENGINEERING"),
    ("BME", "BIOMEDICAL ENGINEERING"),
    ("BPH", "BIOPHYSICS"),
    ("BUS", "MANAGEMENT"),
    ("CET", "COMPUTER EDUCATION & EDUCATIONAL TECHNOLOGY"),
    ("CHE", "CHEMICAL ENGINEERING"),
    ("CHEM", "CHEMISTRY"),
    ("CHIN", "CHINESE"),
    ("CINT", "CONFERENCE INTERPRETING"),
    ("CL", "CLASSICAL LANGUAGES"),
    ("CMPE", "COMPUTER ENGINEERING"),
    ("COGS", "COGNITIVE SCIENCE"),
    ("CONF", "CONFERENCE INTERPRETING"),
    ("CS", "COMPUTER SCIENCE"),
    ("CTR", "CONSTRUCTION TECHNOLOGY AND MANAGEMENT"),
    ("DR", "DIRECTING"),
    ("EC", "ECONOMICS"),
    ("ECE", "EARLY CHILDHOOD EDUCATION"),
    ("ED", "EDUCATIONAL SCIENCES"),
    ("EE", "ELECTRICAL & ELECTRONICS ENGINEERING"),
    ("EF", "FACULTY OF EDUCATION"),
    ("EFL", "ENGLISH AS A FOREIGN LANGUAGE"),
    ("ENG", "ENGLISH"),
    ("ENGC", "ENGLISH COMPOSITION"),
    ("ENGR", "ENGINEERING"),
    ("ENV", "ENVIRONMENTAL SCIENCES"),
    ("ENVT", "ENVIRONMENTAL TECHNOLOGY"),
    ("EQE", "EARTHQUAKE ENGINEERING"),
    ("ERM", "EXECUTIVE REAL ESTATE MANAGEMENT"),
    ("ESC", "ENVIRONMENTAL SCIENCES"),
    ("ETM", "ENGINEERING AND TECHNOLOGY MANAGEMENT"),
    ("EX", "EXCHANGE"),
    ("FA", "FINE ARTS"),
    ("FLED", "FOREIGN LANGUAGE EDUCATION"),
    ("FPA", "FILM AND PERFORMING ARTS"),
    ("FRE", "FRENCH"),
    ("GE", "GENERAL EDUCATION"),
    ("GED", "GENERAL EDUCATION"),
    ("GER", "GERMAN"),
    ("GPH", "GEOPHYSICS"),
    ("GUID", "GUIDANCE & PSYCHOLOGICAL COUNSELING"),
    ("HIST", "HISTORY"),
    ("HUM", "HUMANITIES"),
    ("IE", "INDUSTRIAL ENGINEERING"),
    ("INTR", "INTERNATIONAL RELATIONS"),
    ("INTT", "INTERNATIONAL TRADE"),
    ("ITA", "ITALIAN"),
    ("JP", "JAPANESE"),
    ("KOR", "KOREAN"),
    ("LAT", "LATIN"),
    ("LAW", "LAW"),
    ("LING", "LINGUISTICS"),
    ("LL", "LIFELONG LEARNING"),
    ("LS", "LEARNING SCIENCES"),
    ("MATH", "MATHEMATICS"),
    ("ME", "MECHANICAL ENGINEERING"),
    ("MED", "MEDICAL EDUCATION"),
    ("MECA", "MECHATRONICS"),
    ("MIR", "INTERNATIONAL RELATIONS: TURKEY, EUROPE AND THE MIDDLE EAST"),
    ("MIS", "MANAGEMENT INFORMATION SYSTEMS"),
    ("MS", "MATERIALS SCIENCE"),
    ("PA", "PERFORMING ARTS"),
    ("PE", "PHYSICAL EDUCATION"),
    ("PHIL", "PHILOSOPHY"),
    ("PHYS", "PHYSICS"),
    ("POLS", "POLITICAL SCIENCE & INTERNATIONAL RELATIONS"),
    ("PRED", "PRIMARY EDUCATION"),
    ("PSY", "PSYCHOLOGY"),
    ("RU", "RUSSIAN"),
    ("SCED", "SECONDARY SCHOOL SCIENCE AND MATHEMATICS EDUCATION"),
    ("SCO", "SYSTEMS AND CONTROL"),
    ("SE", "SOFTWARE ENGINEERING"),
    ("SOC", "SOCIOLOGY"),
    ("SPAN", "SPANISH"),
    ("SPL", "SPECIAL EDUCATION"),
    ("STS", "SCIENCE, TECHNOLOGY AND SOCIETY"),
    ("SWE", "SOFTWARE ENGINEERING"),
    ("SWO", "SOCIAL WORK"),
    ("TK", "TURKISH"),
    ("TRM", "TOURISM MANAGEMENT"),
    ("TRP", "TRANSLATION STUDIES"),
    ("TRX", "TRANSLATION AND INTERPRETING"),
    ("TS", "TURKISH STUDIES"),
    ("TURK", "TURKISH LANGUAGE & LITERATURE"),
    ("WTR", "WRITING"),
    ("WW", "WESTERN LANGUAGES"),
    ("XMBA", "EXECUTIVE MBA"),
    ("YADYOK", "SCHOOL OF FOREIGN LANGUAGES"),
]


async def discover_terms(client: BounScraperClient) -> list[str]:
    """Discover available academic terms from the schedule semester page."""
    response = await client.get(SCHEDULE_SEMESTER_URL)
    _, terms = extract_viewstate_and_semesters(response.text)
    return terms


async def check_portal_canary(client: BounScraperClient) -> bool:
    """Probe the portal root endpoint with strict timeout to determine if registration is hard down."""
    try:
        response = await client.get(SCHEDULE_SEMESTER_URL, retries=1)
        return response.status_code == 200 and len(response.text) > 100
    except Exception:
        return False


async def fetch_departments(client: BounScraperClient, term: str) -> list[Department]:
    """Fetch the list of departments offering courses in a given term."""
    # Step 1: Initial GET to obtain ASP.NET ViewState and token fields
    init_resp = await client.get(SCHEDULE_SEMESTER_URL)
    vs_dict, _ = extract_viewstate_and_semesters(init_resp.text)

    token = client.recaptcha_token

    # Step 2: Submit search form for target semester
    post_data = {
        "__VIEWSTATE": vs_dict.get("__VIEWSTATE", ""),
        "__VIEWSTATEGENERATOR": vs_dict.get("__VIEWSTATEGENERATOR", ""),
        "__EVENTVALIDATION": vs_dict.get("__EVENTVALIDATION", ""),
        "ctl00$cphMainContent$ddlSemester": term,
        "ctl00$cphMainContent$btnSearch": "Go",
        "ctl00$cphMainContent$gRecResp": token,
    }

    try:
        resp = await client.post(SCHEDULE_SEMESTER_URL, data=post_data)
    finally:
        if token:
            client.invalidate_recaptcha_token()

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

    try:
        response = await client.get(SCHEDULE_DEPT_URL, params=params)
    except BounHttpError as exc:
        if exc.status_code == 500 and bolum:
            logger.info(
                "Portal returned 500 for department %s with bolum='%s'; retrying with empty bolum fallback",
                dept_code,
                bolum,
            )
            fallback_params = {
                "donem": term,
                "kisaadi": dept_code,
                "bolum": "",
            }
            response = await client.get(SCHEDULE_DEPT_URL, params=fallback_params)
        else:
            raise

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
    cached_departments: list[Department] | None = None,
    target_departments: list[str] | None = None,
    skip_already_scraped: bool = False,
    completed_department_codes: set[str] | None = None,
) -> TermScrapeResult:
    """Execute end-to-end term scraping pipeline with concurrency rate-limiting.

    Args:
        client: The scraper client instance.
        term: Term string identifier (e.g. '2024/2025-1').
        progress_callback: Callback invoked when a department completes:
            (completed_count, total_count, department, courses).
        concurrency: Maximum number of concurrent department requests.
        cached_departments: Optional pre-cached department list to fallback to if
            live department discovery fails (e.g. unauthenticated / no cookies).
        target_departments: Optional subset of department codes to scrape.
        skip_already_scraped: If True, bypass departments in completed_department_codes.
        completed_department_codes: Optional set of already-scraped department codes.

    Returns:
        TermScrapeResult with aggregated courses and per-department success/failure tracking.
    """
    departments: list[Department] = []
    fetch_error: Exception | None = None
    try:
        departments = await fetch_departments(client, term)
    except Exception as exc:
        fetch_error = exc
        logger.warning(
            "fetch_departments failed for term %s: %s. Attempting fallback to cached/heuristic departments.",
            term,
            exc,
        )

    if not departments:
        if cached_departments:
            logger.info(
                "Using %d cached/heuristic departments for term %s (live discovery blocked/unavailable)",
                len(cached_departments),
                term,
            )
            departments = cached_departments
        else:
            logger.warning(
                "No cached departments found for term %s and live discovery failed (%s). "
                "Dropping into heuristic mode using %d default known Boğaziçi departments.",
                term,
                fetch_error or "no departments returned",
                len(DEFAULT_KNOWN_DEPARTMENT_CODES),
            )
            departments = [
                Department(code=code, name=name, bolum=name)
                for code, name in DEFAULT_KNOWN_DEPARTMENT_CODES
            ]

    # Filter departments by target list or skip already scraped
    if target_departments:
        target_set = {d.upper().strip() for d in target_departments}
        departments = [d for d in departments if d.code.upper() in target_set]

    if skip_already_scraped and completed_department_codes:
        skipped_count = sum(1 for d in departments if d.code in completed_department_codes)
        if skipped_count > 0:
            logger.info(
                "Skipping %d already-scraped departments for term %s (incremental mode)",
                skipped_count,
                term,
            )
            departments = [d for d in departments if d.code not in completed_department_codes]

    if not departments:
        logger.info("No departments remaining to scrape for term %s after filters", term)
        return TermScrapeResult(
            courses=[], departments=[], succeeded_departments=[], failed_departments=[]
        )

    total_depts = len(departments)
    completed_count = 0
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(concurrency)

    consecutive_failures = 0
    circuit_breaker_tripped = False
    failure_lock = asyncio.Lock()

    async def _scrape_single_dept(dept: Department) -> list[Course]:
        nonlocal completed_count, consecutive_failures, circuit_breaker_tripped
        if circuit_breaker_tripped:
            raise BounHttpError("Circuit breaker active: registration portal is hard down")

        async with sem:
            if circuit_breaker_tripped:
                raise BounHttpError("Circuit breaker active: registration portal is hard down")

            try:
                courses = await fetch_department_schedule(client, term, dept)
                async with failure_lock:
                    consecutive_failures = 0
            except BaseException as exc:
                async with failure_lock:
                    consecutive_failures += 1
                    if consecutive_failures >= 2 and not circuit_breaker_tripped:
                        logger.warning(
                            "Encountered %d consecutive department failures for term %s; checking portal root canary...",
                            consecutive_failures,
                            term,
                        )
                        canary_ok = await check_portal_canary(client)
                        if not canary_ok:
                            circuit_breaker_tripped = True
                            logger.error(
                                "Portal root canary probe failed! Tripping circuit breaker — registration portal is HARD DOWN."
                            )
                raise exc

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

    if circuit_breaker_tripped:
        raise BounHttpError("Registration portal is hard down (circuit breaker tripped via failed root canary)")

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
        if total_depts > 0 and len(failures) == total_depts:
            first_exc = failures[0][1]
            raise first_exc

    return TermScrapeResult(
        courses=all_courses,
        departments=departments,
        succeeded_departments=succeeded_departments,
        failed_departments=failed_departments,
    )
