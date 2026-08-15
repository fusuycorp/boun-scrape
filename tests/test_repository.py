"""Integration tests for DatabaseManager and CourseRepository."""

import pytest

from boun_scrape.domain.dto import CourseFilterParams
from boun_scrape.domain.events import ChangeType, CourseDeltaEvent
from boun_scrape.domain.models import (
    Course,
    CourseSlot,
    Department,
    RunStatus,
    ScrapeRunSummary,
)
from boun_scrape.storage.database import DatabaseManager
from boun_scrape.storage.repository import CourseRepository


@pytest.fixture
def repo(tmp_path) -> CourseRepository:
    """Create a clean isolated SQLite database and repository."""
    db_file = str(tmp_path / "test_schedules.db")
    db = DatabaseManager(db_file)
    db.init_db()
    return CourseRepository(db)


class TestRepository:
    """Tests for CourseRepository CRUD and query capabilities."""

    def test_save_and_get_departments(self, repo: CourseRepository) -> None:
        depts = [
            Department(code="CMPE", name="COMPUTER ENGINEERING", bolum="COMPUTER ENGINEERING"),
            Department(code="MATH", name="MATHEMATICS", bolum="MATHEMATICS"),
        ]
        repo.save_departments("2024/2025-1", depts)

        saved = repo.get_departments("2024/2025-1")
        assert len(saved) == 2
        assert {d.code for d in saved} == {"CMPE", "MATH"}

        # Idempotent upsert
        updated_depts = [
            Department(code="CMPE", name="DEPT OF COMPUTER ENGINEERING", bolum="CMPE_NEW"),
        ]
        repo.save_departments("2024/2025-1", updated_depts)
        saved_after = repo.get_departments("2024/2025-1")
        assert len(saved_after) == 2
        cmpe = next(d for d in saved_after if d.code == "CMPE")
        assert cmpe.name == "DEPT OF COMPUTER ENGINEERING"

    def test_save_courses_and_get_courses_with_filters(
        self, repo: CourseRepository
    ) -> None:
        c1 = Course(
            term="2024/2025-1",
            department="CMPE",
            course_code="CMPE 150",
            section="01",
            course_name="INTRO TO COMPUTING",
            instructor="PROF ALICE",
            credits=3.0,
            ects=6.0,
            slots=[
                CourseSlot(day="M", hour="12", room="NH101", slot_title="LEC"),
                CourseSlot(day="W", hour="34", room="NH102", slot_title="LAB"),
            ],
        )
        c2 = Course(
            term="2024/2025-1",
            department="CMPE",
            course_code="CMPE 250",
            section="01",
            course_name="DATA STRUCTURES",
            instructor="PROF BOB",
            credits=4.0,
            ects=8.0,
            slots=[
                CourseSlot(day="T", hour="56", room="BM101", slot_title="LEC"),
            ],
        )
        c3 = Course(
            term="2024/2025-2",
            department="MATH",
            course_code="MATH 101",
            section="01",
            course_name="CALCULUS I",
            instructor="PROF CAROL",
            credits=4.0,
            ects=7.0,
            slots=[
                CourseSlot(day="F", hour="12", room="NH101", slot_title="LEC"),
            ],
        )

        saved_count = repo.save_courses_and_slots("2024/2025-1", [c1, c2])
        assert saved_count == 2
        repo.save_courses_and_slots("2024/2025-2", [c3])

        # Filter by term
        items, total = repo.get_courses(CourseFilterParams(term="2024/2025-1"))
        assert total == 2
        assert len(items) == 2
        assert items[0].slots[0].room in ("NH101", "BM101")

        # Filter by department
        items, total = repo.get_courses(CourseFilterParams(department="CMPE"))
        assert total == 2

        # Filter by instructor
        items, total = repo.get_courses(CourseFilterParams(instructor="ALICE"))
        assert total == 1
        assert items[0].course_code == "CMPE 150"

        # Filter by day
        items, total = repo.get_courses(CourseFilterParams(day="W"))
        assert total == 1
        assert items[0].course_code == "CMPE 150"

        # Filter by room
        items, total = repo.get_courses(CourseFilterParams(room="NH101"))
        assert total == 2  # CMPE 150 and MATH 101

        # Filter by keyword
        items, total = repo.get_courses(CourseFilterParams(keyword="Structures"))
        assert total == 1
        assert items[0].course_code == "CMPE 250"

        # Pagination
        p1, total = repo.get_courses(CourseFilterParams(page=1, size=1))
        assert total == 3
        assert len(p1) == 1

        p2, total = repo.get_courses(CourseFilterParams(page=2, size=1))
        assert total == 3
        assert len(p2) == 1
        assert p1[0].id != p2[0].id

    def test_get_course_by_id(self, repo: CourseRepository) -> None:
        c1 = Course(
            term="2024/2025-1",
            department="CMPE",
            course_code="CMPE 150",
            section="01",
            course_name="INTRO",
            slots=[CourseSlot(day="M", hour="1", room="NH101")],
        )
        repo.save_courses_and_slots("2024/2025-1", [c1])

        courses, _ = repo.get_courses(CourseFilterParams(term="2024/2025-1"))
        assert len(courses) == 1
        course_id = courses[0].id
        assert course_id is not None

        fetched = repo.get_course_by_id(course_id)
        assert fetched is not None
        assert fetched.course_code == "CMPE 150"
        assert len(fetched.slots) == 1
        assert fetched.slots[0].room == "NH101"

        assert repo.get_course_by_id(99999) is None

    def test_get_terms(self, repo: CourseRepository) -> None:
        repo.save_departments("2023/2024-2", [Department(code="EE", name="EE")])
        repo.save_courses_and_slots(
            "2024/2025-1",
            [
                Course(
                    term="2024/2025-1",
                    department="EE",
                    course_code="EE 101",
                    section="01",
                    course_name="EE INTRO",
                )
            ],
        )

        terms = repo.get_terms()
        assert "2024/2025-1" in terms
        assert "2023/2024-2" in terms

    def test_scrape_runs_persistence(self, repo: CourseRepository) -> None:
        summary = ScrapeRunSummary(
            run_id="run-100",
            term="2024/2025-1",
            status=RunStatus.RUNNING,
            total_departments=10,
            total_courses=50,
            started_at="2025-01-15T10:00:00Z",
        )
        repo.save_scrape_run(summary)

        runs = repo.get_scrape_runs("2024/2025-1")
        assert len(runs) == 1
        assert runs[0].run_id == "run-100"
        assert runs[0].status == RunStatus.RUNNING

        # Update run status
        summary.status = RunStatus.COMPLETED
        summary.completed_at = "2025-01-15T10:05:00Z"
        repo.save_scrape_run(summary)

        updated_runs = repo.get_scrape_runs("2024/2025-1")
        assert len(updated_runs) == 1
        assert updated_runs[0].status == RunStatus.COMPLETED
        assert updated_runs[0].completed_at == "2025-01-15T10:05:00Z"

    def test_deltas_persistence(self, repo: CourseRepository) -> None:
        delta = CourseDeltaEvent(
            change_type=ChangeType.INSTRUCTOR_CHANGED,
            term="2024/2025-1",
            department="CMPE",
            course_code="CMPE 150",
            section="01",
            timestamp="2025-01-15T12:00:00Z",
            old_value={"instructor": "DR OLD"},
            new_value={"instructor": "DR NEW"},
        )
        repo.save_deltas([delta], run_id="run-100")

        fetched_deltas = repo.get_deltas(term="2024/2025-1", run_id="run-100")
        assert len(fetched_deltas) == 1
        assert fetched_deltas[0].change_type == ChangeType.INSTRUCTOR_CHANGED
        assert fetched_deltas[0].course_code == "CMPE 150"
        assert fetched_deltas[0].old_value == {"instructor": "DR OLD"}
        assert fetched_deltas[0].new_value == {"instructor": "DR NEW"}
