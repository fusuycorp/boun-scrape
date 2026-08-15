"""Domain change events and scrape lifecycle events."""

from dataclasses import dataclass, field
from enum import StrEnum


class ChangeType(StrEnum):
    """Categorized change type for course delta detection."""

    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"
    SLOTS_CHANGED = "SLOTS_CHANGED"
    INSTRUCTOR_CHANGED = "INSTRUCTOR_CHANGED"
    ROOM_CHANGED = "ROOM_CHANGED"


@dataclass(slots=True, kw_only=True)
class CourseDeltaEvent:
    """Represents a detected change between consecutive course snapshots."""

    change_type: ChangeType
    term: str
    department: str
    course_code: str
    section: str
    timestamp: str
    old_value: dict[str, object] | None = None
    new_value: dict[str, object] | None = None
    details: str | None = None


@dataclass(slots=True, kw_only=True)
class ScrapeEvent:
    """Lifecycle event emitted during scraping execution."""

    event_type: str
    run_id: str
    term: str
    timestamp: str
    payload: dict[str, object] = field(default_factory=dict)
