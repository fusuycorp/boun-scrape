"""Unit tests for domain models, events, and DTO validation."""

import pytest
from boun_scrape.domain.dto import (
    CourseDTO,
    CourseFilterParams,
    CourseSlotDTO,
    DeltaEventDTO,
    DepartmentDTO,
    PaginatedResponse,
    QuotaDTO,
    ScrapeRunDTO,
)
from boun_scrape.domain.events import ChangeType, CourseDeltaEvent, ScrapeEvent
from boun_scrape.domain.models import (
    Course,
    CourseSlot,
    DayOfWeek,
    Department,
    QuotaRecord,
    QuotaStatus,
    RunStatus,
    ScrapeRunSummary,
    ScrapeSnapshot,
)


class TestDomainModels:
    """Tests for dataclass domain models."""

    def test_department_model(self) -> None:
        dept = Department(code="CMPE", name="COMPUTER ENGINEERING", bolum="COMPUTER ENGINEERING")
        assert dept.code == "CMPE"
        assert dept.name == "COMPUTER ENGINEERING"
        assert dept.bolum == "COMPUTER ENGINEERING"
        assert dept.url is None

    def test_course_and_slot_model(self) -> None:
        slot = CourseSlot(day="M", hour="1", room="NH101", slot_title="LECTURE", instructor="PROF")
        course = Course(
            term="2024/2025-1",
            department="CMPE",
            course_code="CMPE 150",
            section="01",
            course_name="INTRO",
            credits=3.0,
            ects=6.0,
            slots=[slot],
        )
        assert course.full_code == "CMPE 150.01"
        assert len(course.slots) == 1
        assert course.slots[0].day == "M"

    def test_course_full_code_without_section(self) -> None:
        course = Course(
            term="2024/2025-1",
            department="MATH",
            course_code="MATH 101",
            section="",
            course_name="CALCULUS",
        )
        assert course.full_code == "MATH 101"

    def test_quota_record_model(self) -> None:
        rec = QuotaRecord(
            department="CMPE",
            status=QuotaStatus.OPEN,
            quota="50",
            current="30",
            quota_numeric=50,
            current_numeric=30,
            is_consent=False,
            is_unlimited=False,
            available=20,
        )
        assert rec.department == "CMPE"
        assert rec.available == 20

    def test_scrape_snapshot_and_summary(self) -> None:
        snapshot = ScrapeSnapshot(term="2024/2025-1", department_code="CMPE")
        assert snapshot.term == "2024/2025-1"
        assert snapshot.courses == []

        summary = ScrapeRunSummary(
            run_id="run-1",
            term="2024/2025-1",
            status=RunStatus.RUNNING,
            total_departments=10,
        )
        assert summary.run_id == "run-1"
        assert summary.status == RunStatus.RUNNING


class TestDomainEvents:
    """Tests for change events."""

    def test_course_delta_event(self) -> None:
        event = CourseDeltaEvent(
            change_type=ChangeType.INSTRUCTOR_CHANGED,
            term="2024/2025-1",
            department="CMPE",
            course_code="CMPE 150",
            section="01",
            timestamp="2025-01-15T12:00:00Z",
            old_value={"instructor": "OLD INSTRUCTOR"},
            new_value={"instructor": "NEW INSTRUCTOR"},
        )
        assert event.change_type == ChangeType.INSTRUCTOR_CHANGED
        assert event.old_value == {"instructor": "OLD INSTRUCTOR"}

    def test_scrape_event(self) -> None:
        event = ScrapeEvent(
            event_type="term_scraped",
            run_id="run-123",
            term="2024/2025-1",
            timestamp="2025-01-15T12:00:00Z",
            payload={"departments_count": 42},
        )
        assert event.event_type == "term_scraped"
        assert event.payload["departments_count"] == 42


class TestDTOValidation:
    """Tests for Pydantic DTO serialization and validation."""

    def test_course_dto_serialization(self) -> None:
        slot_dto = CourseSlotDTO(day="M", hour="1", room="NH101")
        dto = CourseDTO(
            term="2024/2025-1",
            department="CMPE",
            course_code="CMPE 150",
            section="01",
            course_name="INTRO",
            credits=3.0,
            ects=6.0,
            slots=[slot_dto],
        )
        data = dto.model_dump()
        assert data["course_code"] == "CMPE 150"
        assert len(data["slots"]) == 1
        assert data["slots"][0]["room"] == "NH101"

    def test_paginated_response_dto(self) -> None:
        items = [
            DepartmentDTO(code="CMPE", name="COMPUTER ENGINEERING"),
            DepartmentDTO(code="EE", name="ELECTRICAL ENGINEERING"),
        ]
        page = PaginatedResponse[DepartmentDTO](
            items=items,
            total=2,
            page=1,
            size=10,
            pages=1,
        )
        assert page.total == 2
        assert len(page.items) == 2
        assert page.items[0].code == "CMPE"

    def test_filter_params_validation(self) -> None:
        params = CourseFilterParams(department="CMPE", page=2, size=25)
        assert params.department == "CMPE"
        assert params.page == 2
        assert params.size == 25
