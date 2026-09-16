"""Data export utilities for producing JSON, CSV, SQLite, and delta artifacts."""

import csv
import json
import logging
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

from boun_scrape.domain.events import CourseDeltaEvent
from boun_scrape.domain.models import Course
from boun_scrape.pipeline.delta import course_to_dict
from boun_scrape.storage.database import DatabaseManager
from boun_scrape.storage.repository import CourseRepository

logger = logging.getLogger(__name__)


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


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_csv_cell(val: Any) -> Any:
    """Escape potential formula injection prefixes in CSV cells (CWE-1236)."""
    if isinstance(val, str) and val.startswith(_FORMULA_PREFIXES):
        return f"'{val}"
    return val


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
                writer.writerow({k: _sanitize_csv_cell(v) for k, v in row.items()})
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
                writer.writerow({k: _sanitize_csv_cell(v) for k, v in row.items()})


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
    tmp_path = _tmp_path_for(path)
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
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


def prune_old_exports(
    output_dir: Path | str,
    keep_last_n: int | None = None,
    max_age_days: int | None = None,
) -> list[Path]:
    """Clean up export artifacts beyond keep_last_n newest terms or older than max_age_days.

    If keep_last_n is None or <= 0, retention pruning by term count is disabled.
    If max_age_days is None or <= 0, age-based pruning is disabled.

    Args:
        output_dir: Directory containing export artifacts.
        keep_last_n: Maximum number of most recent terms to retain (None/<=0 disables).
        max_age_days: Maximum age in days before an export file is pruned (None/<=0 disables).

    Returns:
        List of Path objects for the deleted files.
    """
    out_path = Path(output_dir)
    if not out_path.is_dir():
        return []

    if (keep_last_n is None or keep_last_n <= 0) and (max_age_days is None or max_age_days <= 0):
        return []

    term_files: dict[str, list[Path]] = {}
    term_latest_mtime: dict[str, float] = {}
    file_mtimes: dict[Path, float] = {}

    for entry in out_path.iterdir():
        if not entry.is_file() or entry.name.startswith("."):
            continue

        term: str | None = None
        if entry.name.startswith("courses_") and "." in entry.name[len("courses_"):]:
            term = entry.name[len("courses_"):].rpartition(".")[0]
        elif entry.name.startswith("deltas_") and "." in entry.name[len("deltas_"):]:
            term = entry.name[len("deltas_"):].rpartition(".")[0]

        if not term:
            continue

        try:
            mtime = entry.stat().st_mtime
        except OSError:
            mtime = 0.0

        term_files.setdefault(term, []).append(entry)
        term_latest_mtime[term] = max(term_latest_mtime.get(term, 0.0), mtime)
        file_mtimes[entry] = mtime

    kept_terms: set[str] | None = None
    if keep_last_n is not None and keep_last_n > 0:
        sorted_terms = sorted(
            term_files.keys(),
            key=lambda t: (term_latest_mtime.get(t, 0.0), t),
            reverse=True,
        )
        kept_terms = set(sorted_terms[:keep_last_n])

    now = time.time()
    max_age_seconds = (max_age_days * 86400.0) if (max_age_days is not None and max_age_days > 0) else None

    pruned: list[Path] = []
    for term, files in term_files.items():
        for f in files:
            f_mtime = file_mtimes.get(f, 0.0)
            is_beyond_n = (term not in kept_terms) if kept_terms is not None else False
            is_too_old = ((now - f_mtime) > max_age_seconds) if max_age_seconds is not None else False
            if is_beyond_n or is_too_old:
                try:
                    f.unlink(missing_ok=True)
                    pruned.append(f)
                except OSError as exc:
                    logger.warning("Failed to prune export file %s: %s", f, exc)

    return pruned


def export_all_terms(
    repo: CourseRepository,
    output_dir: str | Path = "exports",
    format: str = "all",
) -> dict[str, dict[str, Path]]:
    """Export all academic terms that have courses in the repository into structured artifacts."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    fmt = format.lower().strip()

    with repo.db.connection() as conn:
        rows = conn.execute("SELECT DISTINCT term FROM courses ORDER BY term ASC").fetchall()
        terms = [r[0] for r in rows if r[0]]

    exported_terms: dict[str, dict[str, Path]] = {}
    for term in terms:
        courses = repo.get_courses_by_term(term)
        if not courses:
            continue
        safe_term = _sanitize_term(term)
        term_results: dict[str, Path] = {}
        if fmt == "json":
            term_results["json"] = export_courses_json(courses, out_path / f"courses_{safe_term}.json")
        elif fmt == "csv":
            term_results["csv"] = export_courses_csv(courses, out_path / f"courses_{safe_term}.csv")
        elif fmt in ("sqlite", "db"):
            term_results["sqlite"] = export_courses_sqlite(term, courses, out_path / f"courses_{safe_term}.db")
        elif fmt == "all":
            term_results = generate_all_exports(term=term, courses=courses, output_dir=out_path)
        else:
            raise ValueError(f"Invalid format '{format}'. Supported formats: json, csv, sqlite, all")
        exported_terms[term] = term_results

    return exported_terms

