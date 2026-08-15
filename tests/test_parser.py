"""Unit tests for HTML parsers (ViewState, Semesters, Departments, Schedules, Quota)."""

from pathlib import Path
import pytest

from boun_scrape.domain.models import Course, CourseSlot, Department, QuotaRecord
from boun_scrape.scraper.parser import (
    extract_viewstate_and_semesters,
    parse_departments_from_html,
    parse_quota_from_html,
    parse_schedules_from_html,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def semester_html() -> str:
    with open(FIXTURES_DIR / "sample_semester.html", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def schedule_html() -> str:
    with open(FIXTURES_DIR / "sample_schedule.html", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def quota_html() -> str:
    with open(FIXTURES_DIR / "sample_quota.html", "r", encoding="utf-8") as f:
        return f.read()


class TestViewStateAndSemesters:
    """Tests for extracting ASP.NET form parameters and semester list."""

    def test_extract_from_sample_semester(self, semester_html: str) -> None:
        viewstate, semesters = extract_viewstate_and_semesters(semester_html)

        assert "__VIEWSTATE" in viewstate
        assert len(viewstate["__VIEWSTATE"]) > 50
        assert viewstate["__VIEWSTATEGENERATOR"] == "4BE93B14"
        assert "__EVENTVALIDATION" in viewstate
        assert len(viewstate["__EVENTVALIDATION"]) > 50

        assert len(semesters) > 0
        assert "2025/2026-3" in semesters
        assert "2024/2025-1" in semesters
        assert "1970/1971-1" in semesters

    def test_extract_empty_html(self) -> None:
        viewstate, semesters = extract_viewstate_and_semesters("")
        assert viewstate == {}
        assert semesters == []


class TestParseDepartments:
    """Tests for extracting department listings."""

    def test_parse_from_sample_semester(self, semester_html: str) -> None:
        departments = parse_departments_from_html(semester_html)

        assert len(departments) >= 2
        ec = next((d for d in departments if d.code == "EC"), None)
        assert ec is not None
        assert ec.name == "ECONOMICS"
        assert ec.bolum == "ECONOMICS"
        assert "donem=1970/1971-1" in (ec.url or "")

        ad = next((d for d in departments if d.code == "AD"), None)
        assert ad is not None
        assert ad.name == "MANAGEMENT"
        assert ad.bolum == "MANAGEMENT"

    def test_parse_departments_empty(self) -> None:
        assert parse_departments_from_html("") == []
        assert parse_departments_from_html("<html><body>No links here</body></html>") == []


class TestParseSchedules:
    """Tests for parsing course schedules and session continuation rows."""

    def test_parse_schedule_full(self, schedule_html: str) -> None:
        courses = parse_schedules_from_html(
            schedule_html, term="2024/2025-1", department_code="CMPE"
        )

        assert len(courses) == 4

        # 1. CMPE 150.01 with continuation Lab row
        cmpe150 = courses[0]
        assert cmpe150.term == "2024/2025-1"
        assert cmpe150.department == "CMPE"
        assert cmpe150.course_code == "CMPE 150"
        assert cmpe150.section == "01"
        assert cmpe150.course_name == "INTRODUCTION TO COMPUTING"
        assert cmpe150.credits == 3.0
        assert cmpe150.ects == 6.0
        assert cmpe150.instructor == "SUZAN USKUDARLI"
        assert cmpe150.delivery_method == "Face to Face"
        assert cmpe150.exam_location == "NH101"
        assert cmpe150.exam_date == "15.01.2025"
        assert cmpe150.required_for == "CMPE, EE"
        assert cmpe150.departments == "ALL"

        # Total 5 slots: 3 lecture slots + 2 lab slots from continuation row
        assert len(cmpe150.slots) == 5
        assert cmpe150.slots[0] == CourseSlot(
            day="M", hour="1", room="NH101", slot_title="INTRODUCTION TO COMPUTING", instructor="SUZAN USKUDARLI"
        )
        assert cmpe150.slots[1] == CourseSlot(
            day="W", hour="2", room="NH102", slot_title="INTRODUCTION TO COMPUTING", instructor="SUZAN USKUDARLI"
        )
        assert cmpe150.slots[2] == CourseSlot(
            day="F", hour="3", room="NH103", slot_title="INTRODUCTION TO COMPUTING", instructor="SUZAN USKUDARLI"
        )
        assert cmpe150.slots[3] == CourseSlot(
            day="Th", hour="7", room="LAB1", slot_title="LAB", instructor="ASST. TA"
        )
        assert cmpe150.slots[4] == CourseSlot(
            day="Th", hour="8", room="LAB1", slot_title="LAB", instructor="ASST. TA"
        )

        # 2. MATH 101.01 with 2-digit hour partition and room replication
        math101 = courses[1]
        assert math101.course_code == "MATH 101"
        assert math101.section == "01"
        assert math101.credits == 4.0
        assert math101.ects == 7.5
        assert len(math101.slots) == 2
        assert math101.slots[0].hour == "10"
        assert math101.slots[0].room == "KB433"
        assert math101.slots[1].hour == "11"
        assert math101.slots[1].room == "KB433"

        # 3. MATH 492.01 with TBA
        math492 = courses[2]
        assert math492.course_code == "MATH 492"
        assert math492.credits == 0.0
        assert math492.ects == 4.0
        assert len(math492.slots) == 1
        assert math492.slots[0].day == "TBA"
        assert math492.slots[0].hour == "TBA"
        assert math492.slots[0].room == "TBA"

        # 4. HIST 105.01 with weekend days
        hist105 = courses[3]
        assert hist105.course_code == "HIST 105"
        assert len(hist105.slots) == 2
        assert hist105.slots[0].day == "St"
        assert hist105.slots[0].hour == "1"
        assert hist105.slots[0].room == "M2170"
        assert hist105.slots[1].day == "Su"
        assert hist105.slots[1].hour == "2"
        assert hist105.slots[1].room == "M2180"

    def test_parse_schedule_empty(self) -> None:
        assert parse_schedules_from_html("", "2024/2025-1", "CMPE") == []

    def test_parse_schedule_edge_cases(self) -> None:
        html = """
        <table>
            <tr class="schtd">
                <td>CMPE 150</td>
                <td>CMPE</td>
                <td>INTRO</td>
                <td>3,5</td>
                <td>N/A</td>
                <td>INSTRUCTOR</td>
                <td>MWF</td>
                <td>123</td>
                <td></td>
                <td></td>
                <td></td>
                <td></td>
                <td></td>
                <td></td>
                <td></td>
            </tr>
            <!-- Short row ignored -->
            <tr class="schtd">
                <td>SHORT ROW</td>
                <td>ONLY 2 CELLS</td>
            </tr>
        </table>
        """
        courses = parse_schedules_from_html(html, term="2024/2025-1", department_code="CMPE")
        assert len(courses) == 1
        assert courses[0].course_code == "CMPE 150"
        assert courses[0].section == ""
        assert courses[0].credits == 3.5
        assert courses[0].ects == 0.0


class TestParseQuota:
    """Tests for parsing course quota tables and statuses."""

    def test_parse_quota_records(self, quota_html: str) -> None:
        records = parse_quota_from_html(quota_html)

        assert len(records) == 5

        # 1. Standard open quota
        cmpe = records[0]
        assert cmpe.department == "CMPE"
        assert cmpe.status == "Open"
        assert cmpe.quota == "45"
        assert cmpe.current == "30"
        assert cmpe.quota_numeric == 45
        assert cmpe.current_numeric == 30
        assert cmpe.is_consent is False
        assert cmpe.is_unlimited is False
        assert cmpe.available == 15

        # 2. Closed quota
        ee = records[1]
        assert ee.department == "EE"
        assert ee.status == "Closed"
        assert ee.quota_numeric == 10
        assert ee.current_numeric == 10
        assert ee.available == 0

        # 3. Consent quota
        ie = records[2]
        assert ie.department == "IE"
        assert ie.status == "Consent"
        assert ie.is_consent is True
        assert ie.quota_numeric is None
        assert ie.current_numeric == 5
        assert ie.available is None

        # 4. Unlimited quota
        all_dept = records[3]
        assert all_dept.department == "ALL"
        assert all_dept.is_unlimited is True
        assert all_dept.quota_numeric is None
        assert all_dept.current_numeric == 12
        assert all_dept.available is None

        # 5. Zero quota
        math = records[4]
        assert math.department == "MATH"
        assert math.quota_numeric == 0
        assert math.current_numeric == 0
        assert math.available == 0

    def test_parse_quota_empty(self) -> None:
        assert parse_quota_from_html("") == []
        assert parse_quota_from_html("<html><body>No tables</body></html>") == []

    def test_parse_quota_case_insensitive_and_short_rows(self) -> None:
        html = """
        <table>
            <tr class="schtd">
                <td>PHYS</td>
                <td>CONSENT REQUIRED</td>
                <td>consent</td>
                <td>3</td>
            </tr>
            <tr class="schtd">
                <td>TOO SHORT</td>
                <td>CELL</td>
            </tr>
        </table>
        """
        records = parse_quota_from_html(html)
        assert len(records) == 1
        assert records[0].department == "PHYS"
        assert records[0].is_consent is True
        assert records[0].current_numeric == 3
