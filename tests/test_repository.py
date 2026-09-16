"""Integration tests for DatabaseManager and CourseRepository."""

import sqlite3
from pathlib import Path

import pytest

from boun_scrape.domain.dto import CourseFilterParams
from boun_scrape.domain.events import ChangeType, CourseDeltaEvent
from boun_scrape.domain.models import (
    Course,
    CourseSlot,
    Department,
    QuotaRecord,
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
        assert repo.get_departments_last_cached_at("2024/2025-1") is not None
        assert repo.get_departments_last_cached_at() is not None

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

    def test_scrape_runs_migration_adds_completed_departments(self, tmp_path) -> None:
        """An existing DB created before the column existed must be upgraded in place."""
        db_file = str(tmp_path / "legacy_schedules.db")
        old_schema = """
        CREATE TABLE scrape_runs (
            run_id TEXT PRIMARY KEY,
            term TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            total_departments INTEGER DEFAULT 0,
            total_courses INTEGER DEFAULT 0,
            total_slots INTEGER DEFAULT 0,
            changes_detected INTEGER DEFAULT 0,
            status TEXT,
            error_message TEXT
        );
        """
        conn = sqlite3.connect(db_file)
        conn.executescript(old_schema)
        conn.execute(
            "INSERT INTO scrape_runs (run_id, term, status, total_departments) "
            "VALUES ('run-old', '2024/2025-1', 'completed', 3)"
        )
        conn.commit()
        conn.close()

        db = DatabaseManager(db_file)
        db.init_db()

        repo = CourseRepository(db)
        runs = repo.get_scrape_runs("2024/2025-1")
        assert len(runs) == 1
        assert runs[0].run_id == "run-old"
        assert runs[0].status == RunStatus.COMPLETED
        assert runs[0].completed_departments == 0

        # New saves after migration must persist the column like any other
        summary = ScrapeRunSummary(
            run_id="run-old",
            term="2024/2025-1",
            status=RunStatus.COMPLETED,
            total_departments=3,
            completed_departments=3,
            started_at="2025-01-15T10:00:00Z",
        )
        repo.save_scrape_run(summary)
        assert repo.get_latest_run("2024/2025-1").completed_departments == 3

    def test_scrape_runs_persistence(self, repo: CourseRepository) -> None:
        summary = ScrapeRunSummary(
            run_id="run-100",
            term="2024/2025-1",
            status=RunStatus.RUNNING,
            total_departments=10,
            completed_departments=7,
            total_courses=50,
            started_at="2025-01-15T10:00:00Z",
        )
        repo.save_scrape_run(summary)

        runs = repo.get_scrape_runs("2024/2025-1")
        assert len(runs) == 1
        assert runs[0].run_id == "run-100"
        assert runs[0].status == RunStatus.RUNNING
        assert runs[0].completed_departments == 7

        latest = repo.get_latest_run("2024/2025-1")
        assert latest is not None
        assert latest.completed_departments == 7

        # Update run status; the upsert must carry completed_departments through
        summary.status = RunStatus.COMPLETED
        summary.completed_at = "2025-01-15T10:05:00Z"
        repo.save_scrape_run(summary)

        updated_runs = repo.get_scrape_runs("2024/2025-1")
        assert len(updated_runs) == 1
        assert updated_runs[0].status == RunStatus.COMPLETED
        assert updated_runs[0].completed_at == "2025-01-15T10:05:00Z"
        assert updated_runs[0].completed_departments == 7

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

    def test_save_courses_and_slots_scoped_to_succeeded_departments(
        self, repo: CourseRepository
    ) -> None:
        cmpe_course = Course(
            term="2024/2025-1", department="CMPE", course_code="CMPE 150",
            section="01", course_name="INTRO TO COMPUTING",
        )
        math_course = Course(
            term="2024/2025-1", department="MATH", course_code="MATH 101",
            section="01", course_name="CALCULUS I",
        )
        repo.save_courses_and_slots(
            term="2024/2025-1", courses=[cmpe_course, math_course]
        )
        assert len(repo.get_courses_by_term("2024/2025-1")) == 2

        # Re-scrape where only MATH succeeded this run (CMPE failed and is
        # absent from the passed courses list) -- CMPE's previously-saved
        # data must survive untouched.
        new_math_course = Course(
            term="2024/2025-1", department="MATH", course_code="MATH 101",
            section="01", course_name="CALCULUS I (UPDATED)",
        )
        repo.save_courses_and_slots(
            term="2024/2025-1",
            courses=[new_math_course],
            scraped_departments=["MATH"],
        )

        remaining = repo.get_courses_by_term("2024/2025-1")
        assert len(remaining) == 2
        cmpe = next(c for c in remaining if c.department == "CMPE")
        math = next(c for c in remaining if c.department == "MATH")
        assert cmpe.course_name == "INTRO TO COMPUTING"
        assert math.course_name == "CALCULUS I (UPDATED)"

    def test_save_courses_and_slots_none_replaces_entire_term(
        self, repo: CourseRepository
    ) -> None:
        cmpe_course = Course(
            term="2024/2025-1", department="CMPE", course_code="CMPE 150",
            section="01", course_name="INTRO TO COMPUTING",
        )
        repo.save_courses_and_slots(term="2024/2025-1", courses=[cmpe_course])
        assert len(repo.get_courses_by_term("2024/2025-1")) == 1

        # scraped_departments=None (default) replaces the whole term, even
        # though the new list omits CMPE entirely.
        math_course = Course(
            term="2024/2025-1", department="MATH", course_code="MATH 101",
            section="01", course_name="CALCULUS I",
        )
        repo.save_courses_and_slots(term="2024/2025-1", courses=[math_course])

        remaining = repo.get_courses_by_term("2024/2025-1")
        assert len(remaining) == 1
        assert remaining[0].department == "MATH"

    def test_save_courses_and_slots_empty_scraped_departments_deletes_nothing(
        self, repo: CourseRepository
    ) -> None:
        cmpe_course = Course(
            term="2024/2025-1", department="CMPE", course_code="CMPE 150",
            section="01", course_name="INTRO TO COMPUTING",
        )
        repo.save_courses_and_slots(term="2024/2025-1", courses=[cmpe_course])

        # Nothing succeeded this run -- must be a complete no-op.
        repo.save_courses_and_slots(
            term="2024/2025-1", courses=[], scraped_departments=[]
        )

        remaining = repo.get_courses_by_term("2024/2025-1")
        assert len(remaining) == 1
        assert remaining[0].department == "CMPE"

    def test_deltas_after_timestamp_filter(self, repo: CourseRepository) -> None:
        delta = CourseDeltaEvent(
            change_type=ChangeType.ADDED,
            term="2024/2025-1",
            department="CMPE",
            course_code="CMPE 150",
            section="01",
            timestamp="2025-01-15T12:00:00Z",
            new_value={"instructor": "DR NEW"},
        )
        repo.save_deltas([delta], run_id="run-early")
        with repo.db.connection() as conn:
            conn.execute("UPDATE course_deltas SET created_at = '2025-01-15 09:00:00' WHERE run_id = 'run-early'")
            conn.commit()

        delta2 = CourseDeltaEvent(
            change_type=ChangeType.ADDED,
            term="2024/2025-1",
            department="CMPE",
            course_code="CMPE 250",
            section="01",
            timestamp="2025-01-15T14:00:00Z",
            new_value={"instructor": "DR LATE"},
        )
        repo.save_deltas([delta2], run_id="run-late")
        with repo.db.connection() as conn:
            conn.execute("UPDATE course_deltas SET created_at = '2025-01-15 15:00:00' WHERE run_id = 'run-late'")
            conn.commit()

        recent = repo.get_deltas(term="2024/2025-1", after_timestamp="2025-01-15 10:00:00")
        assert len(recent) == 1
        assert recent[0].course_code == "CMPE 250"

    def test_quota_snapshots_save_and_get(self, repo: CourseRepository) -> None:
        records = [
            QuotaRecord(
                department="CMPE",
                status="Open",
                quota="30",
                current="20",
                quota_numeric=30,
                current_numeric=20,
                available=10,
            ),
            QuotaRecord(
                department="EE",
                status="Consent",
                quota="0",
                current="0",
                is_consent=True,
            ),
        ]
        repo.save_quota_snapshots(term="2024/2025-1", course_code="CMPE 150", section="01", records=records)

        snapshots = repo.get_quota_snapshots(term="2024/2025-1")
        assert len(snapshots) == 2
        by_dept = {s.record.department: s for s in snapshots}
        assert by_dept["CMPE"].record.available == 10
        assert by_dept["CMPE"].course_code == "CMPE 150"
        assert by_dept["CMPE"].section == "01"
        assert by_dept["EE"].record.is_consent is True
        assert snapshots[0].captured_at is not None

        # Saving an empty list is a no-op
        repo.save_quota_snapshots(term="2024/2025-1", course_code="X", section="01", records=[])
        assert len(repo.get_quota_snapshots(term="2024/2025-1")) == 2

    def test_quota_snapshots_bulk_save(self, repo: CourseRepository) -> None:
        # Bulk path (used by capture_quota) persists many sections in one call.
        rows = [
            ("2024/2025-1", "CMPE 150", "01", QuotaRecord(department="CMPE", status="Open", quota="30", current="20")),
            ("2024/2025-1", "CMPE 150", "01", QuotaRecord(department="EE", status="Consent", quota="0", current="0", is_consent=True)),
            ("2024/2025-1", "MATH 101", "02", QuotaRecord(department="MATH", status="Closed", quota="20", current="20")),
        ]
        repo.save_quota_snapshots_bulk(rows)

        snapshots = repo.get_quota_snapshots(term="2024/2025-1")
        assert len(snapshots) == 3
        by_key = {(s.course_code, s.section, s.record.department): s for s in snapshots}
        assert by_key[("CMPE 150", "01", "EE")].record.is_consent is True
        assert by_key[("MATH 101", "02", "MATH")].record.status == "Closed"

        # Empty batch is a no-op
        repo.save_quota_snapshots_bulk([])
        assert len(repo.get_quota_snapshots(term="2024/2025-1")) == 3

    def test_quota_snapshots_after_timestamp_filter(self, repo: CourseRepository) -> None:
        repo.save_quota_snapshots(
            term="2024/2025-1",
            course_code="CMPE 150",
            section="01",
            records=[QuotaRecord(department="CMPE", status="Open", quota="30", current="20")],
        )
        with repo.db.connection() as conn:
            conn.execute("UPDATE quota_snapshots SET captured_at = '2025-01-15 09:00:00'")
            conn.commit()

        repo.save_quota_snapshots(
            term="2024/2025-1",
            course_code="CMPE 250",
            section="01",
            records=[QuotaRecord(department="CMPE", status="Closed", quota="20", current="20")],
        )
        with repo.db.connection() as conn:
            conn.execute(
                "UPDATE quota_snapshots SET captured_at = '2025-01-15 15:00:00' WHERE course_code = 'CMPE 250'"
            )
            conn.commit()

        recent = repo.get_quota_snapshots(term="2024/2025-1", after_timestamp="2025-01-15 10:00:00")
        assert len(recent) == 1
        assert recent[0].course_code == "CMPE 250"

        # No filter returns everything, oldest first
        everything = repo.get_quota_snapshots(term="2024/2025-1")
        assert len(everything) == 2
        assert everything[0].course_code == "CMPE 150"

    def test_idx_courses_unique_and_wal_mode(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "unique_test.db")
        db = DatabaseManager(db_path)
        db.init_db()

        with db.connection() as conn:
            # Verify WAL mode is active
            journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            assert journal_mode.lower() == "wal"

            # Verify indexes exist in sqlite_master
            idx_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_courses_unique'"
            ).fetchone()
            assert idx_row is not None
            assert conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_course_deltas_term_created'"
            ).fetchone() is not None
            assert conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_quota_snapshots_term_captured'"
            ).fetchone() is not None

            # Test unique constraint on courses table
            conn.execute(
                "INSERT INTO courses (term, department, course_code, section) VALUES ('2024/2025-1', 'CMPE', '150', '01')"
            )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO courses (term, department, course_code, section) VALUES ('2024/2025-1', 'CMPE', '150', '01')"
                )

    def test_legacy_schema_migration_adds_content_hash_and_missing_columns(
        self, tmp_path: Path
    ) -> None:
        db_path = str(tmp_path / "legacy.db")
        # Create a database with stripped down legacy courses table
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term TEXT NOT NULL,
                department TEXT NOT NULL,
                course_code TEXT NOT NULL,
                section TEXT NOT NULL,
                course_name TEXT
            )
            """
        )
        conn.execute("CREATE TABLE scrape_runs (id INTEGER PRIMARY KEY, run_id TEXT)")
        conn.execute("CREATE TABLE departments (id INTEGER PRIMARY KEY, term TEXT, code TEXT, name TEXT, bolum TEXT)")
        conn.commit()
        conn.close()

        # Initialize DatabaseManager on legacy database
        db = DatabaseManager(db_path)
        db.init_db()

        # Verify all migrated columns exist and save_courses_and_slots succeeds with content_hash
        repo = CourseRepository(db)
        c = Course(
            term="2026/2027-1",
            department="CMPE",
            course_code="CMPE 150",
            section="01",
            course_name="INTRO TO COMPUTING",
            instructor="PROF ALICE",
            credits=3.0,
            ects=6.0,
        )
        saved = repo.save_courses_and_slots("2026/2027-1", [c])
        assert saved == 1

        loaded = repo.get_courses_by_term("2026/2027-1")
        assert len(loaded) == 1
        assert loaded[0].course_code == "CMPE 150"

        with db.connection() as check_conn:
            hash_val = check_conn.execute("SELECT content_hash FROM courses WHERE course_code = 'CMPE 150'").fetchone()[0]
            assert hash_val is not None
            assert len(hash_val) == 64

    def test_department_coverage_and_status_tracking(self, repo: CourseRepository) -> None:
        term = "2026/2027-1"
        depts = [
            Department(code="CMPE", name="Computer Engineering"),
            Department(code="MATH", name="Mathematics"),
            Department(code="PHYS", name="Physics"),
        ]
        repo.save_departments(term, depts)

        # Initial coverage status
        cov = repo.get_term_coverage(term)
        assert cov.total_departments == 3
        assert cov.completed_departments == 0
        assert cov.pending_departments == 3
        assert cov.failed_departments == 0
        assert cov.percent_complete == 0.0

        # Save courses for CMPE
        courses = [
            Course(
                term=term,
                department="CMPE",
                course_code="CMPE 150",
                section="01",
                course_name="INTRO",
            ),
            Course(
                term=term,
                department="CMPE",
                course_code="CMPE 160",
                section="01",
                course_name="OOP",
            ),
        ]
        repo.save_courses_and_slots(term, courses, scraped_departments=["CMPE"])

        # Mark PHYS as failed
        repo.update_department_scrape_status(
            term=term,
            code="PHYS",
            course_count=0,
            status="FAILED",
            error="Connection timeout",
        )

        completed_set = repo.get_completed_department_codes(term)
        assert completed_set == {"CMPE"}

        cov = repo.get_term_coverage(term)
        assert cov.total_departments == 3
        assert cov.completed_departments == 1
        assert cov.pending_departments == 1
        assert cov.failed_departments == 1
        assert cov.total_courses == 2
        assert cov.percent_complete == 33.3
        assert cov.last_scraped_at is not None

        cmpe_item = next(d for d in cov.departments if d.code == "CMPE")
        assert cmpe_item.status == "COMPLETED"
        assert cmpe_item.course_count == 2
        assert cmpe_item.last_scraped_at is not None

        phys_item = next(d for d in cov.departments if d.code == "PHYS")
        assert phys_item.status == "FAILED"
        assert phys_item.error_message == "Connection timeout"

        math_item = next(d for d in cov.departments if d.code == "MATH")
        assert math_item.status == "PENDING"

    def test_save_courses_and_slots_handles_duplicate_courses_without_error(
        self, repo: CourseRepository
    ) -> None:
        term = "2024/2025-2"
        # Two Course entries with identical (term, department, course_code, section)
        c1 = Course(
            term=term,
            department="HIST",
            course_code="HIST 105",
            section="01",
            course_name="MODERN TURKEY",
            instructor="PROF SMITH",
            slots=[CourseSlot(day="M", hour="3", room="NH 101")],
        )
        c2 = Course(
            term=term,
            department="HIST",
            course_code="HIST 105",
            section="01",
            course_name="MODERN TURKEY",
            instructor="DR DOE",
            slots=[CourseSlot(day="Th", hour="2", room="NH 102")],
        )

        saved = repo.save_courses_and_slots(term, [c1, c2])
        assert saved == 1

        loaded = repo.get_courses_by_term(term)
        assert len(loaded) == 1
        assert loaded[0].course_code == "HIST 105"
        assert loaded[0].section == "01"
        assert len(loaded[0].slots) == 2
        assert "PROF SMITH" in loaded[0].instructor
        assert "DR DOE" in loaded[0].instructor

    def test_master_coverage_and_failed_department_codes(self, repo: CourseRepository) -> None:
        term1 = "2026/2027-1"
        depts1 = [
            Department(code="CMPE", name="Computer Engineering"),
            Department(code="MATH", name="Mathematics"),
            Department(code="PHYS", name="Physics"),
        ]
        repo.save_departments(term1, depts1)
        repo.save_courses_and_slots(
            term1,
            [
                Course(term=term1, department="CMPE", course_code="CMPE 150", section="01", course_name="INTRO"),
                Course(term=term1, department="CMPE", course_code="CMPE 160", section="01", course_name="OOP"),
            ],
            scraped_departments=["CMPE"],
        )
        repo.update_department_scrape_status(
            term=term1,
            code="PHYS",
            course_count=0,
            status="FAILED",
            error="Socket timed out",
        )

        term2 = "2026/2027-2"
        depts2 = [
            Department(code="EE", name="Electrical Engineering"),
            Department(code="IE", name="Industrial Engineering"),
        ]
        repo.save_departments(term2, depts2)
        repo.save_courses_and_slots(
            term2,
            [
                Course(term=term2, department="EE", course_code="EE 201", section="01", course_name="CIRCUITS"),
                Course(term=term2, department="EE", course_code="EE 202", section="01", course_name="SIGNALS"),
                Course(term=term2, department="EE", course_code="EE 303", section="01", course_name="DIGITAL"),
                Course(term=term2, department="IE", course_code="IE 201", section="01", course_name="PROBABILITY"),
            ],
            scraped_departments=["EE", "IE"],
        )

        # Failed department codes check
        assert repo.get_failed_department_codes(term1) == ["PHYS"]
        assert repo.get_failed_department_codes(term2) == []

        # Master coverage calculation check
        master = repo.get_master_coverage()
        assert master.total_terms == 2
        assert master.total_departments == 5
        assert master.completed_departments == 3
        assert master.failed_departments == 1
        assert master.pending_departments == 1
        assert master.total_courses == 6
        assert master.percent_complete == 60.0
        assert len(master.terms) == 2
        terms_dict = {t.term: t for t in master.terms}
        assert terms_dict[term1].completed_departments == 1
        assert terms_dict[term1].failed_departments == 1
        assert terms_dict[term2].completed_departments == 2
        assert terms_dict[term2].failed_departments == 0

    def test_normalize_timestamp_helper(self) -> None:
        from boun_scrape.storage.repository import _normalize_timestamp

        assert _normalize_timestamp(None) is None
        assert _normalize_timestamp("") is None
        assert _normalize_timestamp("   ") is None

        # Space separated
        norm1 = _normalize_timestamp("2026-08-31 14:00:00")
        assert norm1 == "2026-08-31T14:00:00+00:00"

        # Z suffix
        norm2 = _normalize_timestamp("2026-08-31T14:00:00Z")
        assert norm2 == "2026-08-31T14:00:00+00:00"

        # Timezone offset (+03:00 -> converts to UTC 11:00:00)
        norm3 = _normalize_timestamp("2026-08-31T14:00:00+03:00")
        assert norm3 == "2026-08-31T11:00:00+00:00"

        # Numeric epoch string
        norm4 = _normalize_timestamp("1725112800")
        assert norm4 is not None
        assert "T" in norm4

    def test_deltas_cursor_bounds_and_ordering(self, repo: CourseRepository) -> None:
        events = [
            CourseDeltaEvent(
                change_type=ChangeType.ADDED,
                term="2024/2025-1",
                department="CMPE",
                course_code=f"CMPE 15{i}",
                section="01",
                timestamp=f"2026-08-31T1{i}:00:00+00:00",
                new_value={"code": f"CMPE 15{i}"},
            )
            for i in range(1, 5)
        ]
        repo.save_deltas(events, run_id="run-order")

        # Ascending order
        asc_deltas = repo.get_deltas(term="2024/2025-1", run_id="run-order", order="asc")
        assert len(asc_deltas) == 4
        assert asc_deltas[0].course_code == "CMPE 151"
        assert asc_deltas[-1].course_code == "CMPE 154"

        # Descending order (default)
        desc_deltas = repo.get_deltas(term="2024/2025-1", run_id="run-order", order="desc")
        assert len(desc_deltas) == 4
        assert desc_deltas[0].course_code == "CMPE 154"
        assert desc_deltas[-1].course_code == "CMPE 151"

        # Since and until bounds
        bounded = repo.get_deltas(
            term="2024/2025-1",
            run_id="run-order",
            since="2026-08-31T12:00:00Z",
            until="2026-08-31T13:00:00Z",
            order="asc",
        )
        assert len(bounded) == 2
        assert [b.course_code for b in bounded] == ["CMPE 152", "CMPE 153"]

    def test_quota_snapshots_cursor_bounds_and_ordering(self, repo: CourseRepository) -> None:
        term = "2024/2025-1"
        repo.save_quota_snapshots(
            term=term,
            course_code="CMPE 150",
            section="01",
            records=[QuotaRecord(department="CMPE", status="Open", quota="100", current="50")],
        )
        with repo.db.connection() as conn:
            conn.execute("UPDATE quota_snapshots SET captured_at = '2026-08-31T10:00:00+00:00' WHERE course_code = 'CMPE 150'")
            conn.commit()

        repo.save_quota_snapshots(
            term=term,
            course_code="CMPE 160",
            section="01",
            records=[QuotaRecord(department="CMPE", status="Open", quota="80", current="40")],
        )
        with repo.db.connection() as conn:
            conn.execute("UPDATE quota_snapshots SET captured_at = '2026-08-31T12:00:00+00:00' WHERE course_code = 'CMPE 160'")
            conn.commit()

        # Ascending (default for quota snapshots)
        asc_snapshots = repo.get_quota_snapshots(term=term, order="asc")
        assert len(asc_snapshots) == 2
        assert asc_snapshots[0].course_code == "CMPE 150"
        assert asc_snapshots[1].course_code == "CMPE 160"

        # Descending
        desc_snapshots = repo.get_quota_snapshots(term=term, order="desc")
        assert len(desc_snapshots) == 2
        assert desc_snapshots[0].course_code == "CMPE 160"
        assert desc_snapshots[1].course_code == "CMPE 150"

        # since / until filter
        filtered = repo.get_quota_snapshots(term=term, since="2026-08-31 11:00:00")
        assert len(filtered) == 1
        assert filtered[0].course_code == "CMPE 160"

    def test_save_quota_snapshots_persists_canonical_utc(self, repo: CourseRepository) -> None:
        term = "2025/2026-1"
        repo.save_quota_snapshots(
            term=term,
            course_code="EE 101",
            section="01",
            records=[QuotaRecord(department="EE", status="Open", quota="50", current="25")],
        )
        with repo.db.connection() as conn:
            row = conn.execute("SELECT captured_at FROM quota_snapshots WHERE course_code = 'EE 101'").fetchone()
            assert row is not None
            captured_at = row["captured_at"]
            assert "T" in captured_at
            assert "+00:00" in captured_at or "Z" in captured_at

    def test_is_active_term_logic(self, repo: CourseRepository) -> None:
        # Empty repo -> True
        assert repo.is_active_term("2024/2025-1") is True

        # Add terms: past and current
        c1 = Course(term="2020/2021-1", department="CMPE", course_code="CMPE 150", section="01", course_name="Intro")
        c2 = Course(term="2024/2025-2", department="CMPE", course_code="CMPE 150", section="01", course_name="Intro")
        repo.save_courses_and_slots("2020/2021-1", [c1])
        repo.save_courses_and_slots("2024/2025-2", [c2])

        assert repo.is_active_term("2024/2025-2") is True
        assert repo.is_active_term("2025/2026-1") is True  # Newer future term is active
        assert repo.is_active_term("2020/2021-1") is False  # Past term is not active
        assert repo.is_active_term("1999/2000-1") is False

    def test_save_courses_and_slots_past_term_never_deletes(self, repo: CourseRepository) -> None:
        # Seed an active term and a past term
        active_term = "2024/2025-2"
        past_term = "2015/2016-1"

        c_past = Course(term=past_term, department="MATH", course_code="MATH 101", section="01", course_name="Calculus I")
        c_active = Course(term=active_term, department="MATH", course_code="MATH 101", section="01", course_name="Calculus I")
        repo.save_courses_and_slots(past_term, [c_past])
        repo.save_courses_and_slots(active_term, [c_active])

        # Verify both courses exist
        assert len(repo.get_courses_by_term(past_term)) == 1
        assert len(repo.get_courses_by_term(active_term)) == 1

        # Re-scraping past term with empty courses for MATH must NEVER delete existing courses
        repo.save_courses_and_slots(past_term, [], scraped_departments=["MATH"])
        past_courses = repo.get_courses_by_term(past_term)
        assert len(past_courses) == 1, "Past term data must be immutable and never deleted"
        assert past_courses[0].course_code == "MATH 101"

        # Re-scraping active term with empty courses for MATH SHOULD replace/delete (active is source of truth)
        repo.save_courses_and_slots(active_term, [], scraped_departments=["MATH"])
        active_courses = repo.get_courses_by_term(active_term)
        assert len(active_courses) == 0, "Active term should allow replacement by upstream source of truth"

    def test_update_department_scrape_status_preserves_course_count_when_none(self, repo: CourseRepository) -> None:
        term = "2024/2025-1"
        dept = Department(code="CMPE", name="Computer Engineering")
        repo.save_departments(term, [dept])

        # Initially set status to COMPLETED with 42 courses
        repo.update_department_scrape_status(term=term, code="CMPE", course_count=42, status="COMPLETED")
        coverage = repo.get_term_coverage(term)
        assert len(coverage.departments) == 1
        assert coverage.departments[0].course_count == 42
        assert coverage.departments[0].status == "COMPLETED"

        # Quarantining or failure with course_count=None preserves the 42 course count
        repo.update_department_scrape_status(
            term=term,
            code="CMPE",
            course_count=None,
            status="FAILED",
            error="Quarantined: upstream returned 0 courses for active department with existing catalog",
        )
        coverage = repo.get_term_coverage(term)
        assert coverage.departments[0].course_count == 42
        assert coverage.departments[0].status == "FAILED"
        assert "Quarantined" in (coverage.departments[0].error_message or "")
