"""Data Transfer Objects (DTOs) for API and serialization boundaries."""

from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

from boun_scrape.domain.events import ChangeType, CourseDeltaEvent
from boun_scrape.domain.models import (
    Course,
    CourseSlot,
    Department,
    QuotaRecord,
    RunStatus,
    ScrapeRunSummary,
)

T = TypeVar("T")


class CourseSlotDTO(BaseModel):
    """Slot DTO for serialized course sessions."""

    id: int | None = None
    course_id: int | None = None
    day: str
    hour: str
    room: str
    slot_title: str | None = None
    instructor: str | None = None


class CourseDTO(BaseModel):
    """Course DTO for API responses and export feeds."""

    id: int | None = None
    term: str
    department: str
    course_code: str
    section: str
    course_name: str
    instructor: str = ""
    credits: float = 0.0
    ects: float = 0.0
    delivery_method: str = ""
    exam_location: str = ""
    exam_date: str = ""
    sl: str = ""
    required_for: str = ""
    departments: str = ""
    slots: list[CourseSlotDTO] = Field(default_factory=list)
    raw_code: str | None = None


class DepartmentDTO(BaseModel):
    """Department DTO."""

    code: str
    name: str
    bolum: str | None = None
    url: str | None = None


class QuotaDTO(BaseModel):
    """Quota capacity DTO."""

    department: str
    status: str
    quota: str
    current: str
    quota_numeric: int | None = None
    current_numeric: int | None = None
    is_consent: bool = False
    is_unlimited: bool = False
    available: int | None = None


class DeltaEventDTO(BaseModel):
    """Course delta event DTO."""

    change_type: ChangeType
    term: str
    department: str
    course_code: str
    section: str
    timestamp: str
    old_value: dict[str, object] | None = None
    new_value: dict[str, object] | None = None
    details: str | None = None


class ScrapeRunDTO(BaseModel):
    """Scrape run status and summary DTO."""

    run_id: str
    term: str
    status: RunStatus
    total_departments: int = 0
    completed_departments: int = 0
    total_courses: int = 0
    total_slots: int = 0
    changes_detected: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None


class CourseFilterParams(BaseModel):
    """Filter parameters for querying courses."""

    term: str | None = None
    department: str | None = None
    course_code: str | None = None
    instructor: str | None = None
    day: str | None = None
    hour: str | None = None
    room: str | None = None
    slot_title: str | None = None
    keyword: str | None = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=50, ge=1, le=500)


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated envelope for collections."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int


class QuotaQueryItem(BaseModel):
    """Item for batch quota queries."""

    term: str
    abbr: str
    code: str
    section: str = ""


class BatchQuotaRequest(BaseModel):
    """Payload for batch quota requests."""

    items: list[QuotaQueryItem]
    concurrency: int = Field(default=5, ge=1, le=50)
    bypass_cache: bool = False


class ScrapeTriggerRequest(BaseModel):
    """Payload for triggering a scraper cycle."""

    term: str | None = None
    export: bool = True
    dispatch_webhooks: bool = True
    background: bool = True


class ScrapeStatusDTO(BaseModel):
    """Scraper scheduler and engine status."""

    is_running: bool
    is_scraping: bool
    interval_seconds: int
    cron_expression: str | None = None
    run_count: int
    last_run_time: str | None = None
    next_run_time: str | None = None
    last_run_summary: dict[str, Any] | None = None


class LogEntryDTO(BaseModel):
    """Structured log record for API consumers."""

    timestamp: str
    level: str
    name: str
    message: str


class HealthCheckDTO(BaseModel):
    """Dokploy / Docker health check response."""

    status: str = "ok"
    service: str = "boun-scrape"
    version: str = "0.2.0"


# Conversion helpers
def course_slot_to_dto(slot: CourseSlot) -> CourseSlotDTO:
    """Convert CourseSlot domain model to CourseSlotDTO."""
    return CourseSlotDTO(
        id=slot.id,
        course_id=slot.course_id,
        day=slot.day,
        hour=slot.hour,
        room=slot.room,
        slot_title=slot.slot_title,
        instructor=slot.instructor,
    )


def course_to_dto(course: Course) -> CourseDTO:
    """Convert Course domain model to CourseDTO."""
    return CourseDTO(
        id=course.id,
        term=course.term,
        department=course.department,
        course_code=course.course_code,
        section=course.section,
        course_name=course.course_name,
        instructor=course.instructor,
        credits=course.credits,
        ects=course.ects,
        delivery_method=course.delivery_method,
        exam_location=course.exam_location,
        exam_date=course.exam_date,
        sl=course.sl,
        required_for=course.required_for,
        departments=course.departments,
        slots=[course_slot_to_dto(s) for s in course.slots],
        raw_code=course.raw_code,
    )


def department_to_dto(dept: Department) -> DepartmentDTO:
    """Convert Department domain model to DepartmentDTO."""
    return DepartmentDTO(
        code=dept.code,
        name=dept.name,
        bolum=dept.bolum,
        url=dept.url,
    )


def quota_to_dto(q: QuotaRecord) -> QuotaDTO:
    """Convert QuotaRecord domain model to QuotaDTO."""
    return QuotaDTO(
        department=q.department,
        status=q.status,
        quota=q.quota,
        current=q.current,
        quota_numeric=q.quota_numeric,
        current_numeric=q.current_numeric,
        is_consent=q.is_consent,
        is_unlimited=q.is_unlimited,
        available=q.available,
    )


def delta_to_dto(d: CourseDeltaEvent) -> DeltaEventDTO:
    """Convert CourseDeltaEvent domain model to DeltaEventDTO."""
    return DeltaEventDTO(
        change_type=d.change_type,
        term=d.term,
        department=d.department,
        course_code=d.course_code,
        section=d.section,
        timestamp=d.timestamp,
        old_value=d.old_value,
        new_value=d.new_value,
        details=d.details,
    )


def run_to_dto(r: ScrapeRunSummary) -> ScrapeRunDTO:
    """Convert ScrapeRunSummary domain model to ScrapeRunDTO."""
    return ScrapeRunDTO(
        run_id=r.run_id,
        term=r.term,
        status=r.status,
        total_departments=r.total_departments,
        completed_departments=r.completed_departments,
        total_courses=r.total_courses,
        total_slots=r.total_slots,
        changes_detected=r.changes_detected,
        started_at=r.started_at,
        completed_at=r.completed_at,
        error_message=r.error_message,
    )
