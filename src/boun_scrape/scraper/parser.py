"""Pure HTML parsers for terms, departments, schedules, and quota pages."""

import re
import urllib.parse
from bs4 import BeautifulSoup, Tag

from boun_scrape.domain.models import Course, CourseSlot, Department, QuotaRecord
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


def _build_column_index_map(soup: BeautifulSoup) -> dict[str, int]:
    """Map semantic field names to column indices dynamically from table header."""
    title_tr = soup.find("tr", class_="schtitle") or soup.find(
        "tr", class_=lambda c: bool(c and "title" in str(c).lower())
    )
    if not title_tr:
        return {
            "code_sec": 0,
            "name": 2,
            "credits": 3,
            "ects": 4,
            "instructor": 5,
            "days": 6,
            "hours": 7,
            "delivery": 8,
            "exam_loc": 9,
            "rooms": 10,
            "exam_date": 11,
            "sl": 12,
            "req_dept": 13,
            "other_depts": 14,
        }

    headers = [td.get_text(strip=True).lower() for td in title_tr.find_all(["td", "th"])]
    col_map: dict[str, int] = {}

    for idx, h in enumerate(headers):
        clean_h = re.sub(r"[^a-z0-9\.]", "", h)
        if clean_h in ("code.sec", "codesec", "code", "derskodu") and "code_sec" not in col_map:
            col_map["code_sec"] = idx
        elif clean_h in ("name", "dersadi", "coursename", "title") and "name" not in col_map:
            col_map["name"] = idx
        elif clean_h in ("cr.", "cr", "credit", "kredi") and "credits" not in col_map:
            col_map["credits"] = idx
        elif clean_h in ("ects", "akts") and "ects" not in col_map:
            col_map["ects"] = idx
        elif ("instr" in clean_h or "ogretim" in clean_h) and "instructor" not in col_map:
            col_map["instructor"] = idx
        elif clean_h in ("days", "gun", "gunler") and "days" not in col_map:
            col_map["days"] = idx
        elif clean_h in ("hours", "saat", "saatler") and "hours" not in col_map:
            col_map["hours"] = idx
        elif ("delivery" in clean_h or "ogretimturu" in clean_h) and "delivery" not in col_map:
            col_map["delivery"] = idx
        elif ("examloc" in clean_h or "finalexamlocation" in clean_h or "sinavyeri" in clean_h) and "exam_loc" not in col_map:
            col_map["exam_loc"] = idx
        elif ("room" in clean_h or "derslik" in clean_h) and "rooms" not in col_map:
            col_map["rooms"] = idx
        elif ("exam" in clean_h or "sinav" in clean_h or "examdate" in clean_h) and "exam_date" not in col_map:
            col_map["exam_date"] = idx
        elif clean_h in ("s.l.", "sl.", "sl", "kontenjan") and "sl" not in col_map:
            col_map["sl"] = idx
        elif ("req" in clean_h or "required" in clean_h) and "req_dept" not in col_map:
            col_map["req_dept"] = idx
        elif ("dept" in clean_h or "department" in clean_h or "bolum" in clean_h) and "other_depts" not in col_map:
            col_map["other_depts"] = idx

    defaults = {
        "code_sec": 0,
        "name": 2,
        "credits": 3,
        "ects": 4,
        "instructor": 5,
        "days": 6,
        "hours": 7,
        "delivery": 8,
        "exam_loc": 9,
        "rooms": 10,
        "exam_date": 11,
        "sl": 12,
        "req_dept": 13,
        "other_depts": 14,
    }
    for key, def_idx in defaults.items():
        if key not in col_map:
            col_map[key] = def_idx

    return col_map


def _get_cell_text(tds: list[Tag], col_idx: int | None, default: str = "", separator: str = "") -> str:
    """Safely get text from a td tag at index."""
    if col_idx is None or col_idx >= len(tds):
        return default
    if separator:
        return tds[col_idx].get_text(separator, strip=True)
    return tds[col_idx].get_text(strip=True)


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
    courses_by_key: dict[tuple[str, str], Course] = {}
    last_key: tuple[str, str] | None = None
    col_map = _build_column_index_map(soup)

    for tr in soup.find_all("tr", class_=["schtd", "schtd2"]):
        tds = tr.find_all("td")
        if len(tds) < 10:
            continue

        code_sec = _get_cell_text(tds, col_map.get("code_sec"))
        slot_title = _get_cell_text(tds, col_map.get("name"))
        credits_raw = _get_cell_text(tds, col_map.get("credits"))
        ects_raw = _get_cell_text(tds, col_map.get("ects"))
        instructor = _get_cell_text(tds, col_map.get("instructor"))
        days_str = _get_cell_text(tds, col_map.get("days"))
        hours_str = _get_cell_text(tds, col_map.get("hours"))
        delivery = _get_cell_text(tds, col_map.get("delivery"))
        exam_loc = _get_cell_text(tds, col_map.get("exam_loc"))
        rooms_raw = _get_cell_text(tds, col_map.get("rooms"), separator=" | ")
        exam_date = _get_cell_text(tds, col_map.get("exam_date"))
        sl = _get_cell_text(tds, col_map.get("sl"))
        req_dept = _get_cell_text(tds, col_map.get("req_dept"))
        other_depts = _get_cell_text(tds, col_map.get("other_depts"))

        # Continuation row (e.g. LAB, P.S., Tutorial session)
        if not code_sec:
            if last_key is not None and last_key in courses_by_key:
                continuation_slots = build_slots(
                    day_str=days_str,
                    hour_str=hours_str,
                    room_raw=rooms_raw,
                    slot_title=slot_title or None,
                    instructor=instructor or None,
                )
                courses_by_key[last_key].slots.extend(continuation_slots)
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

        key = (course_code, section)
        if key in courses_by_key:
            existing = courses_by_key[key]
            existing.slots.extend(slots)
            if instructor:
                existing_insts = [s.strip() for s in (existing.instructor or "").split(",") if s.strip()]
                new_insts = [s.strip() for s in instructor.split(",") if s.strip()]
                for inst in new_insts:
                    if inst not in existing_insts:
                        existing_insts.append(inst)
                existing.instructor = ", ".join(existing_insts) if existing_insts else ""
                existing.instructors = list(existing_insts)
            last_key = key
            continue
        inst_list = [s.strip() for s in instructor.split(",") if s.strip()] if instructor else []
        course = Course(
            term=term,
            department=department_code,
            course_code=course_code,
            section=section,
            course_name=slot_title,
            instructor=instructor,
            instructors=inst_list,
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
        courses_by_key[key] = course
        last_key = key

    for course in courses:
        forward_fill_course_rooms(course)

    return courses


def _is_same_session_block(title_a: str | None, title_b: str | None) -> bool:
    """Check if two session titles belong to the same session block (e.g. lecture or lab)."""
    t_a = (title_a or "").strip()
    t_b = (title_b or "").strip()
    if not t_a or not t_b:
        return True
    return t_a.lower() == t_b.lower()


def forward_fill_course_slots(slots: list[CourseSlot]) -> list[CourseSlot]:
    """Forward-fill blank room values across contiguous hours of the same day and session block."""
    if not slots:
        return slots

    slots_by_day: dict[str, list[CourseSlot]] = {}
    for slot in slots:
        if not slot.day or slot.day.upper() == "TBA":
            continue
        slots_by_day.setdefault(slot.day, []).append(slot)

    for day_slots in slots_by_day.values():
        numeric_slots: list[tuple[int, CourseSlot]] = []
        for slot in day_slots:
            hr_str = (slot.hour or "").strip()
            if hr_str.isdigit():
                numeric_slots.append((int(hr_str), slot))

        if len(numeric_slots) < 2:
            continue

        numeric_slots.sort(key=lambda x: x[0])

        prev_hour: int | None = None
        prev_room: str = ""
        prev_title: str | None = None

        for hr, slot in numeric_slots:
            curr_room = (slot.room or "").strip()
            if curr_room.upper() == "N/A":
                curr_room = ""
            curr_title = slot.slot_title

            if (
                not curr_room
                and prev_room
                and prev_hour is not None
                and hr == prev_hour + 1
                and _is_same_session_block(prev_title, curr_title)
            ):
                slot.room = prev_room
                curr_room = prev_room
            elif curr_room and curr_room.upper() not in ("N/A", "TBA"):
                prev_room = curr_room
            else:
                prev_room = ""

            prev_hour = hr
            prev_title = curr_title

    return slots


def forward_fill_course_rooms(course: Course) -> Course:
    """Forward-fill blank room values across contiguous hours for all slots of a course."""
    forward_fill_course_slots(course.slots)
    return course


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

            m_quota = re.search(r"\d+", quota_val)
            if m_quota:
                quota_numeric = int(m_quota.group())
            m_curr = re.search(r"\d+", current_val)
            if m_curr:
                current_numeric = int(m_curr.group())

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
