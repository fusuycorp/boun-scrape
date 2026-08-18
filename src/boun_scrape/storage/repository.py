"""High-performance repository for SQLite persistence of courses, slots, and runs."""

import json
import sqlite3
from typing import Any

from boun_scrape.domain.dto import CourseFilterParams
from boun_scrape.domain.events import ChangeType, CourseDeltaEvent
from boun_scrape.domain.models import (
    Course,
    CourseSlot,
    Department,
    QuotaRecord,
    QuotaSnapshot,
    RunStatus,
    ScrapeRunSummary,
)
from boun_scrape.pipeline.delta import compute_course_hash
from boun_scrape.storage.database import DatabaseManager


def _row_to_course(row: sqlite3.Row, slots: list[CourseSlot]) -> Course:
    """Map a database row and slot list to a Course domain entity."""
    return Course(
        id=row["id"],
        term=row["term"],
        department=row["department"],
        course_code=row["course_code"],
        section=row["section"],
        course_name=row["course_name"] or "",
        instructor=row["instructor"] or "",
        credits=float(row["credits"] or 0.0),
        ects=float(row["ects"] or 0.0),
        delivery_method=row["delivery_method"] or "",
        exam_location=row["exam_location"] or "",
        exam_date=row["exam_date"] or "",
        sl=row["sl"] or "",
        required_for=row["required_for"] or "",
        departments=row["departments"] or "",
        slots=slots,
    )


def _row_to_slot(row: sqlite3.Row) -> CourseSlot:
    """Map a course_slots database row to a CourseSlot domain entity."""
    return CourseSlot(
        id=row["id"],
        course_id=row["course_id"],
        day=row["day"] or "",
        hour=row["hour"] or "",
        room=row["room"] or "",
        slot_title=row["slot_title"],
        instructor=row["instructor"],
    )


class CourseRepository:
    """Repository managing domain persistence, indexing, and queries."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def save_departments(self, term: str, depts: list[Department]) -> None:
        """Upsert departments for a specific academic term."""
        if not depts:
            return

        with self.db.transaction() as conn:
            conn.executemany(
                """
                INSERT INTO departments (code, name, term, url_bolum)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(code, term) DO UPDATE SET
                    name = excluded.name,
                    url_bolum = excluded.url_bolum
                """,
                [(d.code, d.name, term, d.bolum or d.url) for d in depts],
            )

    def save_courses_and_slots(
        self, term: str, courses: list[Course], scraped_departments: list[str] | None = None
    ) -> int:
        """Atomically replace courses and slots for a given term.

        If `scraped_departments` is provided, only rows for those departments are
        replaced -- departments not in this list (e.g. ones that failed to scrape
        this run) are left untouched rather than deleted, so a transient failure
        on one department never destroys previously-good data for it. Pass None
        (the default) to replace the entire term unconditionally, matching the
        old behavior.

        Returns the total number of courses persisted.
        """
        with self.db.transaction() as conn:
            # Foreign keys cascade slot deletion
            if scraped_departments is None:
                conn.execute("DELETE FROM courses WHERE term = ?", (term,))
            elif scraped_departments:
                placeholders = ",".join("?" for _ in scraped_departments)
                conn.execute(
                    f"DELETE FROM courses WHERE term = ? AND department IN ({placeholders})",
                    (term, *scraped_departments),
                )
            # else: scraped_departments == [] means nothing succeeded this run -- delete nothing.

            for course in courses:
                content_hash = compute_course_hash(course)
                cursor = conn.execute(
                    """
                    INSERT INTO courses (
                        term, department, course_code, section, course_name,
                        instructor, credits, ects, delivery_method, exam_location,
                        exam_date, sl, required_for, departments, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        course.term,
                        course.department,
                        course.course_code,
                        course.section,
                        course.course_name,
                        course.instructor,
                        course.credits,
                        course.ects,
                        course.delivery_method,
                        course.exam_location,
                        course.exam_date,
                        course.sl,
                        course.required_for,
                        course.departments,
                        content_hash,
                    ),
                )
                course_id = cursor.lastrowid
                if course.slots and course_id is not None:
                    conn.executemany(
                        """
                        INSERT INTO course_slots (course_id, day, hour, room, slot_title, instructor)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (
                                course_id,
                                s.day,
                                s.hour,
                                s.room,
                                s.slot_title,
                                s.instructor,
                            )
                            for s in course.slots
                        ],
                    )

        return len(courses)

    def get_courses(self, filters: CourseFilterParams) -> tuple[list[Course], int]:
        """Query courses with pagination, filters, and eager slot fetching."""
        conditions: list[str] = []
        params: list[Any] = []

        if filters.term:
            conditions.append("c.term = ?")
            params.append(filters.term)
        if filters.department:
            conditions.append("c.department = ?")
            params.append(filters.department.upper())
        if filters.course_code:
            conditions.append("(c.course_code LIKE ? OR c.course_code = ?)")
            params.extend([f"%{filters.course_code}%", filters.course_code])
        if filters.instructor:
            conditions.append("c.instructor LIKE ?")
            params.append(f"%{filters.instructor}%")
        if filters.day:
            conditions.append(
                "EXISTS (SELECT 1 FROM course_slots s WHERE s.course_id = c.id AND s.day = ?)"
            )
            params.append(filters.day)
        if filters.hour:
            conditions.append(
                "EXISTS (SELECT 1 FROM course_slots s WHERE s.course_id = c.id AND s.hour LIKE ?)"
            )
            params.append(f"%{filters.hour}%")
        if filters.room:
            conditions.append(
                "EXISTS (SELECT 1 FROM course_slots s WHERE s.course_id = c.id AND s.room LIKE ?)"
            )
            params.append(f"%{filters.room}%")
        if filters.slot_title:
            conditions.append(
                "EXISTS (SELECT 1 FROM course_slots s WHERE s.course_id = c.id AND s.slot_title LIKE ?)"
            )
            params.append(f"%{filters.slot_title}%")
        if filters.keyword:
            conditions.append(
                "(c.course_code LIKE ? OR c.course_name LIKE ? OR c.instructor LIKE ? OR c.department LIKE ?)"
            )
            kw = f"%{filters.keyword}%"
            params.extend([kw, kw, kw, kw])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self.db.connection() as conn:
            # Get total count
            count_query = f"SELECT COUNT(*) AS total FROM courses c {where_clause}"
            total = conn.execute(count_query, params).fetchone()["total"]
            if total == 0:
                return [], 0

            # Get paginated course rows
            offset = (filters.page - 1) * filters.size
            course_query = f"""
                SELECT c.*
                FROM courses c
                {where_clause}
                ORDER BY c.course_code ASC, c.section ASC, c.id ASC
                LIMIT ? OFFSET ?
            """
            course_rows = conn.execute(course_query, (*params, filters.size, offset)).fetchall()

            course_ids = [row["id"] for row in course_rows]
            slots_by_course_id: dict[int, list[CourseSlot]] = {cid: [] for cid in course_ids}

            if course_ids:
                placeholders = ",".join("?" * len(course_ids))
                slots_query = f"""
                    SELECT *
                    FROM course_slots
                    WHERE course_id IN ({placeholders})
                    ORDER BY course_id, id ASC
                """
                slot_rows = conn.execute(slots_query, course_ids).fetchall()
                for slot_row in slot_rows:
                    cid = slot_row["course_id"]
                    slots_by_course_id[cid].append(_row_to_slot(slot_row))

            courses = [
                _row_to_course(row, slots_by_course_id[row["id"]])
                for row in course_rows
            ]
            return courses, total

    def get_courses_by_term(self, term: str) -> list[Course]:
        """Fetch all courses and their slots for a given term without pagination limits."""
        with self.db.connection() as conn:
            course_rows = conn.execute(
                """
                SELECT * FROM courses
                WHERE term = ?
                ORDER BY course_code ASC, section ASC, id ASC
                """,
                (term,),
            ).fetchall()
            if not course_rows:
                return []

            course_ids = [row["id"] for row in course_rows]
            slots_by_course_id: dict[int, list[CourseSlot]] = {cid: [] for cid in course_ids}
            placeholders = ",".join("?" * len(course_ids))
            slots_query = f"""
                SELECT * FROM course_slots
                WHERE course_id IN ({placeholders})
                ORDER BY course_id, id ASC
            """
            slot_rows = conn.execute(slots_query, course_ids).fetchall()
            for slot_row in slot_rows:
                cid = slot_row["course_id"]
                slots_by_course_id[cid].append(_row_to_slot(slot_row))

            return [
                _row_to_course(row, slots_by_course_id[row["id"]])
                for row in course_rows
            ]

    def get_course_by_id(self, course_id: int) -> Course | None:
        """Fetch a single course with its slots by course primary key ID."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM courses WHERE id = ?", (course_id,)
            ).fetchone()
            if row is None:
                return None

            slot_rows = conn.execute(
                "SELECT * FROM course_slots WHERE course_id = ? ORDER BY id ASC",
                (course_id,),
            ).fetchall()
            slots = [_row_to_slot(s) for s in slot_rows]
            return _row_to_course(row, slots)

    def get_departments(self, term: str | None = None) -> list[Department]:
        """Fetch departments, optionally filtered by term."""
        with self.db.connection() as conn:
            if term:
                rows = conn.execute(
                    "SELECT code, name, term, url_bolum FROM departments WHERE term = ? ORDER BY code ASC",
                    (term,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT DISTINCT code, name, url_bolum FROM departments ORDER BY code ASC"
                ).fetchall()

            return [
                Department(
                    code=r["code"],
                    name=r["name"],
                    bolum=r["url_bolum"],
                )
                for r in rows
            ]

    def get_terms(self) -> list[str]:
        """Fetch all unique terms present in courses or departments."""
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT term FROM courses
                UNION
                SELECT DISTINCT term FROM departments
                ORDER BY term DESC
                """
            ).fetchall()
            return [r["term"] for r in rows if r["term"]]

    def save_scrape_run(self, summary: ScrapeRunSummary) -> None:
        """Persist or update scrape run execution status."""
        status_val = (
            summary.status.value
            if isinstance(summary.status, RunStatus)
            else str(summary.status)
        )
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO scrape_runs (
                    run_id, term, started_at, completed_at,
                    total_departments, completed_departments, total_courses, total_slots,
                    changes_detected, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    term = excluded.term,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    total_departments = excluded.total_departments,
                    completed_departments = excluded.completed_departments,
                    total_courses = excluded.total_courses,
                    total_slots = excluded.total_slots,
                    changes_detected = excluded.changes_detected,
                    status = excluded.status,
                    error_message = excluded.error_message
                """,
                (
                    summary.run_id,
                    summary.term,
                    summary.started_at,
                    summary.completed_at,
                    summary.total_departments,
                    summary.completed_departments,
                    summary.total_courses,
                    summary.total_slots,
                    summary.changes_detected,
                    status_val,
                    summary.error_message,
                ),
            )

    def get_scrape_runs(
        self, term: str | None = None, limit: int = 50
    ) -> list[ScrapeRunSummary]:
        """Fetch recent scrape run summaries."""
        with self.db.connection() as conn:
            if term:
                rows = conn.execute(
                    """
                    SELECT * FROM scrape_runs
                    WHERE term = ?
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (term, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM scrape_runs
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            runs: list[ScrapeRunSummary] = []
            for r in rows:
                try:
                    status = RunStatus(r["status"])
                except (ValueError, TypeError):
                    status = RunStatus.PENDING

                runs.append(
                    ScrapeRunSummary(
                        run_id=r["run_id"],
                        term=r["term"],
                        status=status,
                        total_departments=r["total_departments"] or 0,
                        completed_departments=r["completed_departments"] or 0,
                        total_courses=r["total_courses"] or 0,
                        total_slots=r["total_slots"] or 0,
                        changes_detected=r["changes_detected"] or 0,
                        started_at=r["started_at"],
                        completed_at=r["completed_at"],
                        error_message=r["error_message"],
                    )
                )
            return runs

    def get_latest_run(self, term: str | None = None) -> ScrapeRunSummary | None:
        """Fetch the most recent scrape run summary."""
        runs = self.get_scrape_runs(term=term, limit=1)
        return runs[0] if runs else None

    def save_deltas(
        self, deltas: list[CourseDeltaEvent], run_id: str | None = None
    ) -> None:
        """Persist course change delta events."""
        if not deltas:
            return

        with self.db.transaction() as conn:
            for d in deltas:
                change_type_str = (
                    d.change_type.value
                    if isinstance(d.change_type, ChangeType)
                    else str(d.change_type)
                )
                diff_fields = None
                if d.new_value and d.old_value:
                    diff_fields = json.dumps(
                        [k for k in d.new_value if d.new_value.get(k) != d.old_value.get(k)]
                    )
                elif d.new_value:
                    diff_fields = json.dumps(list(d.new_value.keys()))
                elif d.old_value:
                    diff_fields = json.dumps(list(d.old_value.keys()))

                conn.execute(
                    """
                    INSERT INTO course_deltas (
                        run_id, term, change_type, course_code, section,
                        diff_fields, previous_data, current_data, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        d.term,
                        change_type_str,
                        d.course_code,
                        d.section,
                        diff_fields,
                        json.dumps(d.old_value) if d.old_value else None,
                        json.dumps(d.new_value) if d.new_value else None,
                        d.timestamp,
                    ),
                )

    def get_deltas(
        self,
        term: str | None = None,
        run_id: str | None = None,
        after_timestamp: str | None = None,
        limit: int = 100,
    ) -> list[CourseDeltaEvent]:
        """Fetch historical course delta events with optional filtering."""
        conditions: list[str] = []
        params: list[Any] = []

        if term:
            conditions.append("term = ?")
            params.append(term)
        if run_id:
            conditions.append("run_id = ?")
            params.append(run_id)
        if after_timestamp:
            conditions.append("created_at > ?")
            params.append(after_timestamp)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT * FROM course_deltas
            {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """
        params.append(limit)

        with self.db.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            events: list[CourseDeltaEvent] = []
            for r in rows:
                try:
                    ctype = ChangeType(r["change_type"])
                except (ValueError, TypeError):
                    ctype = ChangeType.MODIFIED

                old_val = json.loads(r["previous_data"]) if r["previous_data"] else None
                new_val = json.loads(r["current_data"]) if r["current_data"] else None

                dept = ""
                if new_val and isinstance(new_val, dict) and "department" in new_val:
                    dept = str(new_val["department"])
                elif old_val and isinstance(old_val, dict) and "department" in old_val:
                    dept = str(old_val["department"])

                events.append(
                    CourseDeltaEvent(
                        change_type=ctype,
                        term=r["term"],
                        department=dept,
                        course_code=r["course_code"],
                        section=r["section"],
                        timestamp=r["created_at"],
                        old_value=old_val,
                        new_value=new_val,
                        details=r["diff_fields"],
                    )
                )
            return events

    def save_quota_snapshots_bulk(
        self, rows: list[tuple[str, str, str, QuotaRecord]]
    ) -> None:
        """Persist many quota records across course sections in a single transaction.

        Args:
            rows: list of (term, course_code, section, QuotaRecord) tuples. This is the
                hot path for capture_quota — batching avoids one commit per section.
        """
        if not rows:
            return

        with self.db.transaction() as conn:
            conn.executemany(
                """
                INSERT INTO quota_snapshots (
                    term, course_code, section, quota_department, status, quota, current,
                    quota_numeric, current_numeric, is_consent, is_unlimited, available
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        term, course_code, section, r.department, r.status, r.quota, r.current,
                        r.quota_numeric, r.current_numeric, int(r.is_consent), int(r.is_unlimited),
                        r.available,
                    )
                    for term, course_code, section, r in rows
                ],
            )

    def save_quota_snapshots(
        self, term: str, course_code: str, section: str, records: list[QuotaRecord]
    ) -> None:
        """Persist a batch of quota records captured for one course section."""
        if not records:
            return

        with self.db.transaction() as conn:
            for r in records:
                conn.execute(
                    """
                    INSERT INTO quota_snapshots (
                        term, course_code, section, quota_department, status, quota, current,
                        quota_numeric, current_numeric, is_consent, is_unlimited, available
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        term, course_code, section, r.department, r.status, r.quota, r.current,
                        r.quota_numeric, r.current_numeric, int(r.is_consent), int(r.is_unlimited),
                        r.available,
                    ),
                )

    def get_quota_snapshots(
        self,
        term: str | None = None,
        after_timestamp: str | None = None,
        limit: int = 500,
    ) -> list[QuotaSnapshot]:
        """Fetch quota snapshots, optionally filtered by term and/or captured strictly after a timestamp."""
        conditions: list[str] = []
        params: list[Any] = []

        if term:
            conditions.append("term = ?")
            params.append(term)
        if after_timestamp:
            conditions.append("captured_at > ?")
            params.append(after_timestamp)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT * FROM quota_snapshots
            {where_clause}
            ORDER BY captured_at ASC, id ASC
            LIMIT ?
        """
        params.append(limit)

        with self.db.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                QuotaSnapshot(
                    term=row["term"],
                    course_code=row["course_code"],
                    section=row["section"],
                    record=QuotaRecord(
                        department=row["quota_department"] or "",
                        status=row["status"] or "",
                        quota=row["quota"] or "",
                        current=row["current"] or "",
                        quota_numeric=row["quota_numeric"],
                        current_numeric=row["current_numeric"],
                        is_consent=bool(row["is_consent"]),
                        is_unlimited=bool(row["is_unlimited"]),
                        available=row["available"],
                    ),
                    captured_at=row["captured_at"],
                )
                for row in rows
            ]
