"""Delta detection engine for tracking schedule changes across scrape cycles."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from boun_scrape.domain.events import ChangeType, CourseDeltaEvent
from boun_scrape.domain.models import Course, CourseSlot


def course_slot_to_dict(slot: CourseSlot) -> dict[str, Any]:
    """Serialize CourseSlot to a deterministic dictionary."""
    return {
        "day": slot.day,
        "hour": slot.hour,
        "room": slot.room,
        "slot_title": slot.slot_title or "",
        "instructor": slot.instructor or "",
    }


def course_to_dict(course: Course) -> dict[str, Any]:
    """Serialize Course entity to a deterministic dictionary for diff and hashing."""
    slots = sorted(
        [course_slot_to_dict(s) for s in course.slots],
        key=lambda s: (s["day"], s["hour"], s["room"], s["slot_title"], s["instructor"]),
    )
    return {
        "term": course.term,
        "department": course.department,
        "course_code": course.course_code,
        "section": course.section,
        "course_name": course.course_name,
        "instructor": course.instructor,
        "credits": round(float(course.credits), 2),
        "ects": round(float(course.ects), 2),
        "delivery_method": course.delivery_method,
        "exam_location": course.exam_location,
        "exam_date": course.exam_date,
        "sl": course.sl,
        "required_for": course.required_for,
        "departments": course.departments,
        "slots": slots,
    }


def compute_course_hash(course: Course) -> str:
    """Compute a deterministic SHA-256 hash for a course and its slots."""
    data = course_to_dict(course)
    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_deltas(
    previous_courses: list[Course],
    current_courses: list[Course],
    run_id: str,
    term: str,
) -> list[CourseDeltaEvent]:
    """Compare previous and current course lists to produce discrete delta events."""
    timestamp = datetime.now(timezone.utc).isoformat()
    events: list[CourseDeltaEvent] = []

    prev_map: dict[tuple[str, str, str], Course] = {
        (c.department, c.course_code, c.section): c for c in previous_courses
    }
    curr_map: dict[tuple[str, str, str], Course] = {
        (c.department, c.course_code, c.section): c for c in current_courses
    }

    # 1. Added courses
    for key, curr in curr_map.items():
        if key not in prev_map:
            events.append(
                CourseDeltaEvent(
                    change_type=ChangeType.ADDED,
                    term=term,
                    department=curr.department,
                    course_code=curr.course_code,
                    section=curr.section,
                    timestamp=timestamp,
                    old_value=None,
                    new_value=course_to_dict(curr),
                    details=f"Course {curr.full_code} was added.",
                )
            )

    # 2. Removed courses
    for key, prev in prev_map.items():
        if key not in curr_map:
            events.append(
                CourseDeltaEvent(
                    change_type=ChangeType.REMOVED,
                    term=term,
                    department=prev.department,
                    course_code=prev.course_code,
                    section=prev.section,
                    timestamp=timestamp,
                    old_value=course_to_dict(prev),
                    new_value=None,
                    details=f"Course {prev.full_code} was removed.",
                )
            )

    # 3. Modified courses
    for key, curr in curr_map.items():
        if key not in prev_map:
            continue

        prev = prev_map[key]
        if compute_course_hash(prev) == compute_course_hash(curr):
            continue

        prev_dict = course_to_dict(prev)
        curr_dict = course_to_dict(curr)

        # Track what changed specifically
        has_specific_change = False

        # Instructor change
        if prev.instructor != curr.instructor:
            has_specific_change = True
            events.append(
                CourseDeltaEvent(
                    change_type=ChangeType.INSTRUCTOR_CHANGED,
                    term=term,
                    department=curr.department,
                    course_code=curr.course_code,
                    section=curr.section,
                    timestamp=timestamp,
                    old_value={"instructor": prev.instructor},
                    new_value={"instructor": curr.instructor},
                    details=(
                        f"Instructor changed from '{prev.instructor}' to '{curr.instructor}'."
                    ),
                )
            )

        # Room change
        prev_rooms = [s.room for s in prev.slots]
        curr_rooms = [s.room for s in curr.slots]
        if prev_rooms != curr_rooms:
            has_specific_change = True
            events.append(
                CourseDeltaEvent(
                    change_type=ChangeType.ROOM_CHANGED,
                    term=term,
                    department=curr.department,
                    course_code=curr.course_code,
                    section=curr.section,
                    timestamp=timestamp,
                    old_value={"rooms": prev_rooms},
                    new_value={"rooms": curr_rooms},
                    details=f"Rooms changed from {prev_rooms} to {curr_rooms}.",
                )
            )

        # Slots changed (days / hours / count / title)
        prev_schedule_slots = [(s.day, s.hour, s.slot_title) for s in prev.slots]
        curr_schedule_slots = [(s.day, s.hour, s.slot_title) for s in curr.slots]
        if prev_schedule_slots != curr_schedule_slots:
            has_specific_change = True
            events.append(
                CourseDeltaEvent(
                    change_type=ChangeType.SLOTS_CHANGED,
                    term=term,
                    department=curr.department,
                    course_code=curr.course_code,
                    section=curr.section,
                    timestamp=timestamp,
                    old_value={"slots": prev_dict["slots"]},
                    new_value={"slots": curr_dict["slots"]},
                    details="Course session time slots changed.",
                )
            )

        # Metadata changes
        meta_diff_fields: list[str] = []
        for field in [
            "course_name",
            "credits",
            "ects",
            "delivery_method",
            "exam_location",
            "exam_date",
            "sl",
            "required_for",
            "departments",
        ]:
            if prev_dict[field] != curr_dict[field]:
                meta_diff_fields.append(field)

        if meta_diff_fields or not has_specific_change:
            events.append(
                CourseDeltaEvent(
                    change_type=ChangeType.MODIFIED,
                    term=term,
                    department=curr.department,
                    course_code=curr.course_code,
                    section=curr.section,
                    timestamp=timestamp,
                    old_value={f: prev_dict[f] for f in meta_diff_fields} if meta_diff_fields else prev_dict,
                    new_value={f: curr_dict[f] for f in meta_diff_fields} if meta_diff_fields else curr_dict,
                    details=(
                        f"Fields changed: {', '.join(meta_diff_fields)}"
                        if meta_diff_fields
                        else f"Course {curr.full_code} modified."
                    ),
                )
            )

    return events
