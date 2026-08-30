"""Domain layer data models, enums, events, and DTOs."""

from boun_scrape.domain.dto import (
    CourseDTO,
    CourseFilterParams,
    CourseSlotDTO,
    DeltaEventDTO,
    DepartmentCoverageItemDTO,
    DepartmentDTO,
    MasterCoverageSummaryDTO,
    PaginatedResponse,
    QuotaDTO,
    ScrapeRunDTO,
    TermCoverageSummaryDTO,
)
from boun_scrape.domain.events import (
    ChangeType,
    CourseDeltaEvent,
    ScrapeEvent,
)
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

__all__ = [
    "ChangeType",
    "Course",
    "CourseDTO",
    "CourseDeltaEvent",
    "CourseFilterParams",
    "CourseSlot",
    "CourseSlotDTO",
    "DayOfWeek",
    "DeltaEventDTO",
    "Department",
    "DepartmentCoverageItemDTO",
    "DepartmentDTO",
    "MasterCoverageSummaryDTO",
    "PaginatedResponse",
    "QuotaDTO",
    "QuotaRecord",
    "QuotaStatus",
    "RunStatus",
    "ScrapeEvent",
    "ScrapeRunDTO",
    "ScrapeRunSummary",
    "ScrapeSnapshot",
    "TermCoverageSummaryDTO",
]
