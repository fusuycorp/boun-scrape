"""Pure HTML parsers for terms, departments, schedules, and quota pages."""

import urllib.parse
from bs4 import BeautifulSoup, Tag

from boun_scrape.domain.models import Course, Department, QuotaRecord
from boun_scrape.scraper.slot_tokenizer import build_slots


def _parse_float(val: str | None) -> float:
    """Safely parse a string value to float."""
    if not val:
        return 0.0
    cleaned = val.strip().replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def extract_viewstate_and_semesters(html: str) -> tuple[dict[str, str], list[str]]:
    """Extract ASP.NET ViewState tokens and available semester codes from semester HTML page.

    Returns a tuple of (viewstate_dict, semesters_list).
    """
    if not html:
        return {}, []

    soup = BeautifulSoup(html, "html.parser")

    vs_node = soup.find("input", {"id": "__VIEWSTATE"}) or soup.find(
        "input", {"name": "__VIEWSTATE"}
    )
    gen_node = soup.find("input", {"id": "__VIEWSTATEGENERATOR"}) or soup.find(
        "input", {"name": "__VIEWSTATEGENERATOR"}
    )
    val_node = soup.find("input", {"id": "__EVENTVALIDATION"}) or soup.find(
        "input", {"name": "__EVENTVALIDATION"}
    )

    viewstate_dict: dict[str, str] = {
        "__VIEWSTATE": vs_node.get("value", "") if isinstance(vs_node, Tag) else "",
        "__VIEWSTATEGENERATOR": (
            gen_node.get("value", "") if isinstance(gen_node, Tag) else ""
        ),
        "__EVENTVALIDATION": (
            val_node.get("value", "") if isinstance(val_node, Tag) else ""
        ),
    }

    # Extract semesters dropdown options
    select_node = soup.find("select", id=lambda x: x and "ddlSemester" in x)
    if not select_node:
        select_node = soup.find("select", attrs={"name": lambda x: x and "ddlSemester" in x})

    semesters: list[str] = []
    if isinstance(select_node, Tag):
        for opt in select_node.find_all("option"):
            val = opt.get("value", "").strip()
            if val:
                semesters.append(val)

    return viewstate_dict, semesters


def parse_departments_from_html(html: str) -> list[Department]:
    """Parse list of departments from semester schedule index HTML."""
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="table-bordered") or soup

    departments: list[Department] = []
    seen: set[tuple[str, str | None]] = set()

    for a in table.find_all("a", href=True):
        href = a["href"]
        if "/scripts/sch.asp?" not in href:
            continue

        parsed = urllib.parse.urlparse(href)
        query = urllib.parse.parse_qs(parsed.query)

        kisaadi = query.get("kisaadi", [""])[0].strip()
        bolum = query.get("bolum", [None])[0]
        if bolum is not None:
            bolum = bolum.strip()
        name = a.get_text(strip=True)

        key = (kisaadi, bolum)
        if key in seen:
            continue
        seen.add(key)

        departments.append(
            Department(
                code=kisaadi,
                name=name,
                bolum=bolum,
                url=href,
            )
        )

    return departments


def parse_schedules_from_html(
    html: str, term: str, department_code: str
) -> list[Course]:
    """Parse schedule table rows into Course models with associated slots.

    Supports:
    - Primary course rows with full metadata.
    - Continuation rows (empty course code) for LAB, Problem Sessions (P.S.), Tutorials.
    - Credit and ECTS conversion to float.
    - Slot tokenization for days, hours, and rooms.
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    courses: list[Course] = []

    for tr in soup.find_all("tr", class_=["schtd", "schtd2"]):
        tds = tr.find_all("td")
        if len(tds) < 11:
            continue

        code_sec = tds[0].get_text(strip=True)
        slot_title = tds[2].get_text(strip=True) if len(tds) > 2 else ""
        credits_raw = tds[3].get_text(strip=True) if len(tds) > 3 else ""
        ects_raw = tds[4].get_text(strip=True) if len(tds) > 4 else ""
        instructor = tds[5].get_text(strip=True) if len(tds) > 5 else ""
        days_str = tds[6].get_text(strip=True) if len(tds) > 6 else ""
        hours_str = tds[7].get_text(strip=True) if len(tds) > 7 else ""
        delivery = tds[8].get_text(strip=True) if len(tds) > 8 else ""
        exam_loc = tds[9].get_text(strip=True) if len(tds) > 9 else ""
        rooms_raw = tds[10].get_text(" | ", strip=True) if len(tds) > 10 else ""
        exam_date = tds[11].get_text(strip=True) if len(tds) > 11 else ""
        sl = tds[12].get_text(strip=True) if len(tds) > 12 else ""
        req_dept = tds[13].get_text(strip=True) if len(tds) > 13 else ""
        other_depts = tds[14].get_text(strip=True) if len(tds) > 14 else ""

        # Continuation row (e.g. LAB, P.S., Tutorial session)
        if not code_sec:
            if courses:
                continuation_slots = build_slots(
                    day_str=days_str,
                    hour_str=hours_str,
                    room_raw=rooms_raw,
                    slot_title=slot_title or None,
                    instructor=instructor or None,
                )
                courses[-1].slots.extend(continuation_slots)
            continue

        # Split code and section
        if "." in code_sec:
            course_code, section = code_sec.rsplit(".", 1)
        else:
            course_code, section = code_sec, ""

        course_code = course_code.strip()
        section = section.strip()

        slots = build_slots(
            day_str=days_str,
            hour_str=hours_str,
            room_raw=rooms_raw,
            slot_title=slot_title or None,
            instructor=instructor or None,
        )

        course = Course(
            term=term,
            department=department_code,
            course_code=course_code,
            section=section,
            course_name=slot_title,
            instructor=instructor,
            credits=_parse_float(credits_raw),
            ects=_parse_float(ects_raw),
            delivery_method=delivery,
            exam_location=exam_loc,
            exam_date=exam_date,
            sl=sl,
            required_for=req_dept,
            departments=other_depts,
            slots=slots,
            raw_code=code_sec,
        )
        courses.append(course)

    return courses


def parse_quota_from_html(html: str) -> list[QuotaRecord]:
    """Parse quota capacity and enrollment rows from quotasearch HTML response."""
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return []

    quota_records: list[QuotaRecord] = []
    # Search in tables for schtd / schtd2 rows
    for table in tables:
        for tr in table.find_all("tr", class_=["schtd", "schtd2"]):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue

            dept = tds[0].get_text(strip=True)
            status = tds[1].get_text(strip=True)
            quota_val = tds[2].get_text(strip=True)
            current_val = tds[3].get_text(strip=True)

            status_lower = status.lower()
            quota_lower = quota_val.lower()

            is_consent = "consent" in quota_lower or "consent" in status_lower
            is_unlimited = "unlimited" in quota_lower or "unlimited" in status_lower

            quota_numeric: int | None = None
            current_numeric: int | None = None

            if quota_val.isdigit():
                quota_numeric = int(quota_val)
            if current_val.isdigit():
                current_numeric = int(current_val)

            available: int | None = None
            if (
                quota_numeric is not None
                and current_numeric is not None
                and not is_consent
                and not is_unlimited
            ):
                available = quota_numeric - current_numeric

            quota_records.append(
                QuotaRecord(
                    department=dept,
                    status=status,
                    quota=quota_val,
                    current=current_val,
                    quota_numeric=quota_numeric,
                    current_numeric=current_numeric,
                    is_consent=is_consent,
                    is_unlimited=is_unlimited,
                    available=available,
                )
            )

    return quota_records
