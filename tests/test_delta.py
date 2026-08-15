"""Unit tests for course hashing and delta detection."""

from boun_scrape.domain.events import ChangeType
from boun_scrape.domain.models import Course, CourseSlot
from boun_scrape.pipeline.delta import (
    compute_course_hash,
    compute_deltas,
    course_slot_to_dict,
    course_to_dict,
)


def _make_sample_course(
    *,
    code: str = "CMPE 150",
    sec: str = "01",
    name: str = "INTRO TO COMPUTING",
    instructor: str = "PROF A",
    credits: float = 3.0,
    ects: float = 6.0,
    slots: list[CourseSlot] | None = None,
    exam_loc: str = "",
) -> Course:
    if slots is None:
        slots = [
            CourseSlot(day="M", hour="1", room="NH101", slot_title="LECTURE", instructor="PROF A"),
            CourseSlot(day="W", hour="2", room="NH101", slot_title="LECTURE", instructor="PROF A"),
        ]
    return Course(
        term="2024/2025-1",
        department="CMPE",
        course_code=code,
        section=sec,
        course_name=name,
        instructor=instructor,
        credits=credits,
        ects=ects,
        delivery_method="Face-to-Face",
        exam_location=exam_loc,
        slots=slots,
    )


class TestDeltaEngine:
    """Tests for SHA-256 hash calculation and delta computation."""

    def test_course_hash_deterministic(self) -> None:
        c1 = _make_sample_course()
        c2 = _make_sample_course()
        assert compute_course_hash(c1) == compute_course_hash(c2)

    def test_course_hash_slot_order_invariant(self) -> None:
        slot1 = CourseSlot(day="M", hour="1", room="NH101")
        slot2 = CourseSlot(day="W", hour="2", room="NH102")
        c1 = _make_sample_course(slots=[slot1, slot2])
        c2 = _make_sample_course(slots=[slot2, slot1])
        assert compute_course_hash(c1) == compute_course_hash(c2)

    def test_course_hash_detects_changes(self) -> None:
        c1 = _make_sample_course(instructor="PROF A")
        c2 = _make_sample_course(instructor="PROF B")
        assert compute_course_hash(c1) != compute_course_hash(c2)

    def test_delta_added_courses(self) -> None:
        c1 = _make_sample_course(code="CMPE 150", sec="01")
        deltas = compute_deltas(
            previous_courses=[],
            current_courses=[c1],
            run_id="run-1",
            term="2024/2025-1",
        )
        assert len(deltas) == 1
        assert deltas[0].change_type == ChangeType.ADDED
        assert deltas[0].course_code == "CMPE 150"
        assert deltas[0].section == "01"
        assert deltas[0].new_value is not None
        assert deltas[0].old_value is None

    def test_delta_removed_courses(self) -> None:
        c1 = _make_sample_course(code="CMPE 150", sec="01")
        deltas = compute_deltas(
            previous_courses=[c1],
            current_courses=[],
            run_id="run-1",
            term="2024/2025-1",
        )
        assert len(deltas) == 1
        assert deltas[0].change_type == ChangeType.REMOVED
        assert deltas[0].course_code == "CMPE 150"
        assert deltas[0].old_value is not None
        assert deltas[0].new_value is None

    def test_delta_no_changes(self) -> None:
        c1 = _make_sample_course()
        c2 = _make_sample_course()
        deltas = compute_deltas(
            previous_courses=[c1],
            current_courses=[c2],
            run_id="run-1",
            term="2024/2025-1",
        )
        assert len(deltas) == 0

    def test_delta_instructor_changed(self) -> None:
        c_old = _make_sample_course(instructor="DR OLD")
        c_new = _make_sample_course(instructor="DR NEW")
        deltas = compute_deltas(
            previous_courses=[c_old],
            current_courses=[c_new],
            run_id="run-1",
            term="2024/2025-1",
        )
        assert len(deltas) == 1
        assert deltas[0].change_type == ChangeType.INSTRUCTOR_CHANGED
        assert deltas[0].old_value == {"instructor": "DR OLD"}
        assert deltas[0].new_value == {"instructor": "DR NEW"}

    def test_delta_room_changed(self) -> None:
        slot_old = [CourseSlot(day="M", hour="1", room="NH101")]
        slot_new = [CourseSlot(day="M", hour="1", room="KB405")]
        c_old = _make_sample_course(slots=slot_old)
        c_new = _make_sample_course(slots=slot_new)
        deltas = compute_deltas(
            previous_courses=[c_old],
            current_courses=[c_new],
            run_id="run-1",
            term="2024/2025-1",
        )
        assert any(d.change_type == ChangeType.ROOM_CHANGED for d in deltas)
        room_event = next(d for d in deltas if d.change_type == ChangeType.ROOM_CHANGED)
        assert room_event.old_value == {"rooms": ["NH101"]}
        assert room_event.new_value == {"rooms": ["KB405"]}

    def test_delta_slots_changed(self) -> None:
        slot_old = [CourseSlot(day="M", hour="1", room="NH101")]
        slot_new = [
            CourseSlot(day="M", hour="1", room="NH101"),
            CourseSlot(day="Th", hour="3", room="NH101"),
        ]
        c_old = _make_sample_course(slots=slot_old)
        c_new = _make_sample_course(slots=slot_new)
        deltas = compute_deltas(
            previous_courses=[c_old],
            current_courses=[c_new],
            run_id="run-1",
            term="2024/2025-1",
        )
        assert any(d.change_type == ChangeType.SLOTS_CHANGED for d in deltas)

    def test_delta_metadata_modified_with_reordered_identical_slots(self) -> None:
        # Same slots, different raw (HTML row) order, plus an unrelated metadata
        # change. Room/slot comparison must sort like the gating hash does, or
        # this spuriously also emits ROOM_CHANGED/SLOTS_CHANGED.
        slot_a = CourseSlot(day="M", hour="1", room="NH101")
        slot_b = CourseSlot(day="W", hour="2", room="NH102")
        c_old = _make_sample_course(credits=3.0, slots=[slot_a, slot_b])
        c_new = _make_sample_course(credits=4.0, slots=[slot_b, slot_a])
        deltas = compute_deltas(
            previous_courses=[c_old],
            current_courses=[c_new],
            run_id="run-1",
            term="2024/2025-1",
        )
        assert len(deltas) == 1
        assert deltas[0].change_type == ChangeType.MODIFIED

    def test_delta_metadata_modified(self) -> None:
        c_old = _make_sample_course(credits=3.0, ects=5.0)
        c_new = _make_sample_course(credits=4.0, ects=6.0)
        deltas = compute_deltas(
            previous_courses=[c_old],
            current_courses=[c_new],
            run_id="run-1",
            term="2024/2025-1",
        )
        assert len(deltas) == 1
        assert deltas[0].change_type == ChangeType.MODIFIED
        assert "credits" in deltas[0].old_value
        assert "ects" in deltas[0].old_value
