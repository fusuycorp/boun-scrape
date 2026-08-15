"""Unit and integration tests for data export pipeline (JSON, CSV, SQLite, Deltas)."""

import csv
import json
import sqlite3
from pathlib import Path
import pytest

from boun_scrape.domain.events import ChangeType, CourseDeltaEvent
from boun_scrape.domain.models import Course, CourseSlot
from boun_scrape.pipeline.exporter import (
    CSV_FIELDNAMES,
    export_courses_csv,
    export_courses_json,
    export_courses_sqlite,
    export_deltas_json,
    generate_all_exports,
)
from boun_scrape.storage.database import DatabaseManager
from boun_scrape.storage.repository import CourseRepository


@pytest.fixture
def sample_courses() -> list[Course]:
    c1 = Course(
        term="2024/2025-1",
        department="CMPE",
        course_code="CMPE 150",
        section="01",
        course_name="INTRODUCTION TO COMPUTING",
        instructor="SUZAN USKUDARLI",
        credits=3.0,
        ects=6.0,
        delivery_method="Face to Face",
        exam_location="NH101",
        exam_date="15.01.2025",
        sl="N/A",
        required_for="CMPE, EE",
        departments="ALL",
        slots=[
            CourseSlot(
                day="M",
                hour="1",
                room="NH101",
                slot_title="INTRODUCTION TO COMPUTING",
                instructor="SUZAN USKUDARLI",
            ),
            CourseSlot(
                day="W",
                hour="2",
                room="NH102",
                slot_title="INTRODUCTION TO COMPUTING",
                instructor="SUZAN USKUDARLI",
            ),
            CourseSlot(
                day="Th",
                hour="7",
                room="LAB1",
                slot_title="LAB",
                instructor="ASST. TA",
            ),
        ],
    )

    c2 = Course(
        term="2024/2025-1",
        department="MATH",
        course_code="MATH 492",
        section="01",
        course_name="PROJECT / TÜRKÇE KARAKTERLER: İŞĞÖÜÇ",
        instructor="PROF. DR. ÖĞRETİM ÜYESİ",
        credits=0.0,
        ects=4.0,
        delivery_method="Face to Face",
        slots=[],
    )

    return [c1, c2]


@pytest.fixture
def sample_deltas() -> list[CourseDeltaEvent]:
    return [
        CourseDeltaEvent(
            change_type=ChangeType.ADDED,
            term="2024/2025-1",
            department="CMPE",
            course_code="CMPE 150",
            section="01",
            timestamp="2025-01-15T12:00:00Z",
            old_value=None,
            new_value={"course_code": "CMPE 150", "instructor": "SUZAN USKUDARLI"},
            details="Course CMPE 150.01 was added.",
        ),
        CourseDeltaEvent(
            change_type=ChangeType.INSTRUCTOR_CHANGED,
            term="2024/2025-1",
            department="MATH",
            course_code="MATH 101",
            section="01",
            timestamp="2025-01-15T12:05:00Z",
            old_value={"instructor": "OLD PROF"},
            new_value={"instructor": "NEW PROF"},
            details="Instructor changed.",
        ),
    ]


class TestExportJson:
    """Tests for structured JSON course catalog export."""

    def test_export_courses_json(self, sample_courses: list[Course], tmp_path: Path) -> None:
        target = tmp_path / "exports" / "courses.json"
        res_path = export_courses_json(sample_courses, target)

        assert res_path == target
        assert target.is_file()

        data = json.loads(target.read_text(encoding="utf-8"))
        assert len(data) == 2
        assert data[0]["course_code"] == "CMPE 150"
        assert len(data[0]["slots"]) == 3
        assert data[0]["slots"][0]["room"] == "NH101"
        assert data[1]["course_code"] == "MATH 492"
        assert data[1]["slots"] == []

    def test_export_courses_json_empty(self, tmp_path: Path) -> None:
        target = tmp_path / "empty.json"
        export_courses_json([], target)
        assert json.loads(target.read_text(encoding="utf-8")) == []


class TestExportCsv:
    """Tests for flattened CSV export matching legacy schema."""

    def test_export_courses_csv_headers_and_flattening(
        self, sample_courses: list[Course], tmp_path: Path
    ) -> None:
        target = tmp_path / "exports" / "courses.csv"
        res_path = export_courses_csv(sample_courses, target)

        assert res_path == target
        assert target.is_file()

        with open(target, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == CSV_FIELDNAMES
            rows = list(reader)

        # c1 has 3 slots -> 3 rows; c2 has 0 slots -> 1 row. Total 4 rows
        assert len(rows) == 4

        # c1 slot 1
        assert rows[0]["course_code"] == "CMPE 150"
        assert rows[0]["day"] == "M"
        assert rows[0]["hour"] == "1"
        assert rows[0]["room"] == "NH101"
        assert rows[0]["slot_title"] == "INTRODUCTION TO COMPUTING"
        assert rows[0]["slot_instructor"] == "SUZAN USKUDARLI"

        # c1 slot 3 (Lab with different instructor)
        assert rows[2]["day"] == "Th"
        assert rows[2]["hour"] == "7"
        assert rows[2]["room"] == "LAB1"
        assert rows[2]["slot_title"] == "LAB"
        assert rows[2]["slot_instructor"] == "ASST. TA"

        # c2 (0 slots -> blank slot columns, preserved Turkish characters)
        assert rows[3]["course_code"] == "MATH 492"
        assert "İŞĞÖÜÇ" in rows[3]["course_name"]
        assert rows[3]["day"] == ""
        assert rows[3]["hour"] == ""
        assert rows[3]["room"] == ""
        assert rows[3]["slot_title"] == ""
        assert rows[3]["slot_instructor"] == ""


class TestExportSqlite:
    """Tests for standalone SQLite database file export."""

    def test_export_courses_sqlite(
        self, sample_courses: list[Course], tmp_path: Path
    ) -> None:
        target = tmp_path / "db" / "courses.db"
        res_path = export_courses_sqlite("2024/2025-1", sample_courses, target)

        assert res_path == target
        assert target.is_file()

        # Connect and verify content via repository
        db_mgr = DatabaseManager(str(target))
        repo = CourseRepository(db_mgr)

        courses = repo.get_courses_by_term("2024/2025-1")
        assert len(courses) == 2
        cmpe = next(c for c in courses if c.course_code == "CMPE 150")
        assert len(cmpe.slots) == 3
        assert cmpe.slots[0].room == "NH101"

    def test_export_courses_sqlite_overwrite(
        self, sample_courses: list[Course], tmp_path: Path
    ) -> None:
        target = tmp_path / "courses.db"
        export_courses_sqlite("2024/2025-1", sample_courses, target)
        assert target.is_file()

        # Re-export with single course
        export_courses_sqlite("2024/2025-1", [sample_courses[0]], target)
        db_mgr = DatabaseManager(str(target))
        repo = CourseRepository(db_mgr)
        courses = repo.get_courses_by_term("2024/2025-1")
        assert len(courses) == 1


class TestExportDeltas:
    """Tests for serializing CourseDeltaEvent to JSON."""

    def test_export_deltas_json(
        self, sample_deltas: list[CourseDeltaEvent], tmp_path: Path
    ) -> None:
        target = tmp_path / "deltas.json"
        res_path = export_deltas_json(sample_deltas, target)

        assert res_path == target
        assert target.is_file()

        data = json.loads(target.read_text(encoding="utf-8"))
        assert len(data) == 2
        assert data[0]["change_type"] == "ADDED"
        assert data[0]["course_code"] == "CMPE 150"
        assert data[1]["change_type"] == "INSTRUCTOR_CHANGED"


class TestGenerateAllExports:
    """Tests for the high-level generate_all_exports function."""

    def test_generate_all_exports(
        self,
        sample_courses: list[Course],
        sample_deltas: list[CourseDeltaEvent],
        tmp_path: Path,
    ) -> None:
        export_dir = tmp_path / "all_exports"
        exports = generate_all_exports(
            term="2024/2025-1",
            courses=sample_courses,
            deltas=sample_deltas,
            output_dir=export_dir,
        )

        assert "json" in exports
        assert "csv" in exports
        assert "sqlite" in exports
        assert "deltas" in exports

        assert exports["json"].is_file()
        assert exports["csv"].is_file()
        assert exports["sqlite"].is_file()
        assert exports["deltas"].is_file()

        assert "courses_2024_2025-1.json" in str(exports["json"])
        assert "courses_2024_2025-1.csv" in str(exports["csv"])
        assert "courses_2024_2025-1.db" in str(exports["sqlite"])
        assert "deltas_2024_2025-1.json" in str(exports["deltas"])

    def test_generate_all_exports_without_deltas(
        self, sample_courses: list[Course], tmp_path: Path
    ) -> None:
        export_dir = tmp_path / "no_deltas"
        exports = generate_all_exports(
            term="2024/2025-1",
            courses=sample_courses,
            deltas=None,
            output_dir=export_dir,
        )

        assert "json" in exports
        assert "csv" in exports
        assert "sqlite" in exports
        assert "deltas" not in exports
