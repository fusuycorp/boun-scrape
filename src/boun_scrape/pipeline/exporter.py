"""Data export utilities for producing JSON, CSV, SQLite, and delta artifacts."""

import csv
import json
import os
import sqlite3
import tempfile
from pathlib import Path

from boun_scrape.domain.events import CourseDeltaEvent
from boun_scrape.domain.models import Course
from boun_scrape.pipeline.delta import course_to_dict
from boun_scrape.storage.database import DatabaseManager
from boun_scrape.storage.repository import CourseRepository


def _tmp_path_for(path: Path) -> Path:
    """Reserve a unique temp path in the same directory as `path` (same filesystem, atomic rename)."""
    fd, name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    os.close(fd)
    return Path(name)

CSV_FIELDNAMES = [
    "term",
    "department",
    "course_code",
    "section",
    "course_name",
    "instructor",
    "credits",
    "ects",
    "delivery_method",
    "exam_location",
    "exam_date",
    "sl",
    "required_for",
    "departments",
    "day",
    "hour",
    "room",
    "slot_title",
    "slot_instructor",
]


def _sanitize_term(term: str) -> str:
    """Convert an academic term into a filesystem-safe string identifier."""
    return term.replace("/", "_").replace("\\", "_").replace(" ", "_").strip()


def export_courses_json(courses: list[Course], output_path: str | Path) -> Path:
    """Export course catalog with nested session slots to a structured JSON file.

    Args:
        courses: List of Course domain objects.
        output_path: Target file path.

    Returns:
        Resolved Path to the created JSON file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = [course_to_dict(c) for c in courses]
    content = json.dumps(data, indent=2, ensure_ascii=False)

    tmp_path = _tmp_path_for(path)
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return path


def export_courses_csv(courses: list[Course], output_path: str | Path) -> Path:
    """Export flattened course sessions to CSV matching legacy schema for 100% compatibility.

    Args:
        courses: List of Course domain objects.
        output_path: Target file path.

    Returns:
        Resolved Path to the created CSV file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = _tmp_path_for(path)
    try:
        _write_courses_csv(tmp_path, courses)
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return path


def _write_courses_csv(path: Path, courses: list[Course]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()

        for course in courses:
            base_row = {
                "term": course.term,
                "department": course.department,
                "course_code": course.course_code,
                "section": course.section,
                "course_name": course.course_name,
                "instructor": course.instructor,
                "credits": course.credits,
                "ects": course.ects,
                "delivery_method": course.delivery_method,
                "exam_location": course.exam_location,
                "exam_date": course.exam_date,
                "sl": course.sl,
                "required_for": course.required_for,
                "departments": course.departments,
            }

            if not course.slots:
                row = base_row.copy()
                row.update(
                    {
                        "day": "",
                        "hour": "",
                        "room": "",
                        "slot_title": "",
                        "slot_instructor": "",
                    }
                )
                writer.writerow(row)
                continue

            for slot in course.slots:
                row = base_row.copy()
                row.update(
                    {
                        "day": slot.day,
                        "hour": slot.hour,
                        "room": slot.room,
                        "slot_title": slot.slot_title or "",
                        "slot_instructor": slot.instructor or "",
                    }
                )
                writer.writerow(row)


def export_courses_sqlite(
    term: str, courses: list[Course], output_path: str | Path
) -> Path:
    """Export courses and session slots into a standalone SQLite database artifact.

    Args:
        term: Academic term string.
        courses: List of Course domain objects.
        output_path: Target file path for the SQLite database.

    Returns:
        Resolved Path to the created SQLite database file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = _tmp_path_for(path)
    tmp_path.unlink()  # DatabaseManager creates the file itself; start from a clean slot
    try:
        db_manager = DatabaseManager(str(tmp_path))
        db_manager.init_db()

        repo = CourseRepository(db_manager)
        repo.save_courses_and_slots(term=term, courses=courses)

        # Force WAL contents back into the main file so the exported artifact
        # is fully self-contained (no dangling -wal/-shm sidecar files).
        checkpoint_conn = sqlite3.connect(str(tmp_path))
        try:
            checkpoint_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        finally:
            checkpoint_conn.close()

        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    finally:
        for sidecar_suffix in ("-wal", "-shm"):
            Path(f"{tmp_path}{sidecar_suffix}").unlink(missing_ok=True)
    return path


def export_deltas_json(
    deltas: list[CourseDeltaEvent], output_path: str | Path
) -> Path:
    """Export detected course change delta events to a structured JSON file.

    Args:
        deltas: List of CourseDeltaEvent objects.
        output_path: Target file path.

    Returns:
        Resolved Path to the created JSON file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    delta_dicts = [
        {
            "change_type": d.change_type.value if hasattr(d.change_type, "value") else str(d.change_type),
            "term": d.term,
            "department": d.department,
            "course_code": d.course_code,
            "section": d.section,
            "timestamp": d.timestamp,
            "old_value": d.old_value,
            "new_value": d.new_value,
            "details": d.details,
        }
        for d in deltas
    ]

    content = json.dumps(delta_dicts, indent=2, ensure_ascii=False)
    path.write_text(content, encoding="utf-8")
    return path


def generate_all_exports(
    term: str,
    courses: list[Course],
    deltas: list[CourseDeltaEvent] | None = None,
    output_dir: str | Path = "exports",
) -> dict[str, Path]:
    """Generate all standard export artifacts (JSON, CSV, SQLite, and optional Deltas).

    Args:
        term: Academic term string.
        courses: List of Course domain objects.
        deltas: Optional list of CourseDeltaEvent objects.
        output_dir: Destination directory for artifacts.

    Returns:
        Dictionary mapping artifact format keys ('json', 'csv', 'sqlite', 'deltas') to Paths.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_term = _sanitize_term(term)

    results: dict[str, Path] = {
        "json": export_courses_json(courses, out_dir / f"courses_{safe_term}.json"),
        "csv": export_courses_csv(courses, out_dir / f"courses_{safe_term}.csv"),
        "sqlite": export_courses_sqlite(
            term, courses, out_dir / f"courses_{safe_term}.db"
        ),
    }

    if deltas is not None:
        results["deltas"] = export_deltas_json(
            deltas, out_dir / f"deltas_{safe_term}.json"
        )

    return results
