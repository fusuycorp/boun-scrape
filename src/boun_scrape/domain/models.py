"""Pure domain models and enums for boun-scrape."""

from dataclasses import dataclass, field
from enum import StrEnum


class DayOfWeek(StrEnum):
    """Standard day representation in Boğaziçi schedule codes."""

    MON = "M"
    TUE = "T"
    WED = "W"
    THU = "Th"
    FRI = "F"
    SAT = "St"
    SUN = "Su"
    TBA = "TBA"


class QuotaStatus(StrEnum):
    """Course quota availability status."""

    OPEN = "Open"
    CLOSED = "Closed"
    CONSENT = "Consent"
    UNLIMITED = "Unlimited"
    UNKNOWN = "Unknown"


class RunStatus(StrEnum):
    """Execution status for a scraping job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True, kw_only=True)
class Department:
    """Department / Program entity."""

    code: str
    name: str
    bolum: str | None = None
    url: str | None = None


@dataclass(slots=True, kw_only=True)
class CourseSlot:
    """A single timeslot and room allocation for a course session."""

    id: int | None = None
    course_id: int | None = None
    day: str
    hour: str
    room: str
    slot_title: str | None = None
    instructor: str | None = None


@dataclass(slots=True, kw_only=True)
class Course:
    """A full course entity with session slots."""

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
    slots: list[CourseSlot] = field(default_factory=list)
    raw_code: str | None = None

    @property
    def full_code(self) -> str:
        """Full composite course code including section."""
        if self.section:
            return f"{self.course_code}.{self.section}"
        return self.course_code


@dataclass(slots=True, kw_only=True)
class QuotaRecord:
    """Live or snapshot quota capacity for a department/course."""

    department: str
    status: str
    quota: str
    current: str
    quota_numeric: int | None = None
    current_numeric: int | None = None
    is_consent: bool = False
    is_unlimited: bool = False
    available: int | None = None


@dataclass(slots=True, kw_only=True)
class ScrapeSnapshot:
    """Point-in-time snapshot of parsed courses for a department."""

    term: str
    department_code: str
    courses: list[Course] = field(default_factory=list)
    snapshot_hash: str | None = None
    scraped_at: str | None = None


@dataclass(slots=True, kw_only=True)
class ScrapeRunSummary:
    """Summary of a scrape execution."""

    run_id: str
    term: str
    status: RunStatus = RunStatus.PENDING
    total_departments: int = 0
    completed_departments: int = 0
    total_courses: int = 0
    total_slots: int = 0
    changes_detected: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None
