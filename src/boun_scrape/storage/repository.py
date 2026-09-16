"""High-performance repository for SQLite persistence of courses, slots, and runs."""

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any

from boun_scrape.domain.dto import (
    CourseFilterParams,
    DepartmentCoverageItemDTO,
    MasterCoverageSummaryDTO,
    TermCoverageSummaryDTO,
)
from boun_scrape.domain.events import ChangeType, CourseDeltaEvent
from boun_scrape.domain.models import (
    Course,
    CourseSlot,
    Department,
    QuotaRecord,
    QuotaSnapshot,
    RunStatus,
    ScrapeRunSummary,
    compute_course_hash,
)
from boun_scrape.storage.database import DatabaseManager


def _normalize_timestamp(ts: str | None) -> str | None:
    """Normalize timestamp string/epoch to canonical ISO-8601 UTC string for SQLite comparison."""
    if ts is None:
        return None
    raw = ts.strip()
    if not raw:
        return None
    try:
        if raw.replace(".", "", 1).isdigit() and not ("-" in raw or ":" in raw):
            dt = datetime.fromtimestamp(float(raw), tz=timezone.utc)
            return dt.isoformat()

        norm = raw[:-1] + "+00:00" if (raw.endswith("Z") or raw.endswith("z")) else raw
        if " " in norm and "T" not in norm:
            norm = norm.replace(" ", "T", 1)

        dt = datetime.fromisoformat(norm)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat()
    except (ValueError, TypeError, OverflowError):
        return raw


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
                INSERT INTO departments (code, name, term, url_bolum, cached_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(code, term) DO UPDATE SET
                    name = excluded.name,
                    url_bolum = excluded.url_bolum,
                    cached_at = CURRENT_TIMESTAMP
                """,
                [(d.code, d.name, term, d.bolum or d.url) for d in depts],
            )

    def save_courses_and_slots(
        self,
        term: str,
        courses: list[Course],
        scraped_departments: list[str] | None = None,
        is_active: bool | None = None,
    ) -> int:
        """Atomically persist courses and slots for a given term.

        For past terms (is_active=False), existing courses and slots are never deleted,
        protecting historical catalog data from transient empty scrapes or changes.
        For active terms (is_active=True), upstream is the source of truth, so rows for
        scraped_departments are replaced. If scraped_departments is provided, only rows
        for those departments are replaced -- departments not in this list are left
        untouched. Pass None (the default) to replace all departments for the term.

        Returns the total number of courses persisted.
        """
        if is_active is None:
            is_active = self.is_active_term(term)

        # Normalise scraped_departments: dedupe, strip, drop empties (guards S-02)
        filtered_scraped: list[str] | None = None
        if scraped_departments is not None:
            filtered_scraped = [d for d in dict.fromkeys(s.strip() for s in scraped_departments if s and s.strip()) if d]
        with self.db.transaction() as conn:
            # Delete dependent slots first so the operation works regardless of
            # whether course_slots.course_id has ON DELETE CASCADE (new DBs) or
            # NO ACTION/RESTRICT (legacy prod DBs created before the CASCADE fix).
            # Past terms are immutable historical archives; we never delete existing courses.
            if is_active:
                if filtered_scraped is None:
                    conn.execute(
                        "DELETE FROM course_slots WHERE course_id IN (SELECT id FROM courses WHERE term = ?)",
                        (term,),
                    )
                    conn.execute("DELETE FROM courses WHERE term = ?", (term,))
                elif filtered_scraped:
                    if len(filtered_scraped) > 900:
                        for i in range(0, len(filtered_scraped), 900):
                            chunk = filtered_scraped[i : i + 900]
                            ph = ",".join("?" for _ in chunk)
                            conn.execute(
                                f"DELETE FROM course_slots WHERE course_id IN (SELECT id FROM courses WHERE term = ? AND department IN ({ph}))",
                                (term, *chunk),
                            )
                            conn.execute(
                                f"DELETE FROM courses WHERE term = ? AND department IN ({ph})",
                                (term, *chunk),
                            )
                    else:
                        placeholders = ",".join("?" for _ in filtered_scraped)
                        conn.execute(
                            f"DELETE FROM course_slots WHERE course_id IN (SELECT id FROM courses WHERE term = ? AND department IN ({placeholders}))",
                            (term, *filtered_scraped),
                        )
                        conn.execute(
                            f"DELETE FROM courses WHERE term = ? AND department IN ({placeholders})",
                            (term, *filtered_scraped),
                        )
            # else: filtered_scraped == [] means nothing succeeded this run -- delete nothing.
            merged_courses: list[Course] = []
            seen_course_keys: dict[tuple[str, str, str, str], Course] = {}
            for course in courses:
                key = (course.term, course.department, course.course_code, course.section)
                if key in seen_course_keys:
                    existing = seen_course_keys[key]
                    existing.slots.extend(course.slots)
                    if course.instructor:
                        existing_set = {s.strip() for s in (existing.instructor or "").split(",") if s.strip()}
                        if course.instructor.strip() not in existing_set:
                            existing.instructor = (
                                f"{existing.instructor}, {course.instructor}"
                                if existing.instructor
                                else course.instructor
                            )
                else:
                    seen_course_keys[key] = course
                    merged_courses.append(course)

            for course in merged_courses:
                content_hash = compute_course_hash(course)
                cursor = conn.execute(
                    """
                    INSERT INTO courses (
                        term, department, course_code, section, course_name,
                        instructor, credits, ects, delivery_method, exam_location,
                        exam_date, sl, required_for, departments, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(term, department, course_code, section) DO UPDATE SET
                        course_name = excluded.course_name,
                        instructor = excluded.instructor,
                        credits = excluded.credits,
                        ects = excluded.ects,
                        delivery_method = excluded.delivery_method,
                        exam_location = excluded.exam_location,
                        exam_date = excluded.exam_date,
                        sl = excluded.sl,
                        required_for = excluded.required_for,
                        departments = excluded.departments,
                        content_hash = excluded.content_hash,
                        updated_at = CURRENT_TIMESTAMP
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
                if not course_id:
                    row = conn.execute(
                        "SELECT id FROM courses WHERE term = ? AND department = ? AND course_code = ? AND section = ?",
                        (course.term, course.department, course.course_code, course.section),
                    ).fetchone()
                    course_id = row["id"] if row else None

                if course.slots and course_id is not None:
                    conn.execute("DELETE FROM course_slots WHERE course_id = ?", (course_id,))
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

            # Update per-department course counts and COMPLETED status
            depts_to_update = (
                set(filtered_scraped)
                if filtered_scraped is not None
                else {c.department for c in merged_courses}
            )
            dept_counts: dict[str, int] = {}
            for c in merged_courses:
                dept_counts[c.department] = dept_counts.get(c.department, 0) + 1

            for dept_code in depts_to_update:
                cnt = dept_counts.get(dept_code, 0)
                conn.execute(
                    """
                    UPDATE departments
                    SET last_scraped_at = CURRENT_TIMESTAMP,
                        course_count = ?,
                        last_status = 'COMPLETED',
                        last_error = NULL
                    WHERE term = ? AND code = ?
                    """,
                    (cnt, term, dept_code),
                )

        return len(merged_courses)

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

            slots_by_course_id: dict[int, list[CourseSlot]] = {row["id"]: [] for row in course_rows}
            slots_query = """
                SELECT s.* FROM course_slots s
                JOIN courses c ON s.course_id = c.id
                WHERE c.term = ?
                ORDER BY s.course_id, s.id ASC
            """
            slot_rows = conn.execute(slots_query, (term,)).fetchall()
            for slot_row in slot_rows:
                cid = slot_row["course_id"]
                if cid in slots_by_course_id:
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

    def get_departments_last_cached_at(self, term: str | None = None) -> str | None:
        """Fetch the latest cached_at timestamp for departments, optionally filtered by term."""
        with self.db.connection() as conn:
            if term:
                row = conn.execute(
                    "SELECT MAX(cached_at) AS last_cached FROM departments WHERE term = ?",
                    (term,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT MAX(cached_at) AS last_cached FROM departments"
                ).fetchone()
            return row["last_cached"] if row and row["last_cached"] else None

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

    def is_active_term(self, term: str) -> bool:
        """Check if a term is the current active/latest term.

        Past terms are historical archives and must never have existing courses deleted.
        A term is considered active if it matches or exceeds the latest recorded term in the
        database, or if no terms are recorded yet.
        """
        terms = self.get_terms()
        if not terms:
            return True
        return term >= terms[0]

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
        since: str | None = None,
        until: str | None = None,
        order: str = "desc",
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

        after_norm = _normalize_timestamp(after_timestamp)
        since_norm = _normalize_timestamp(since)
        until_norm = _normalize_timestamp(until)

        if after_norm:
            conditions.append("replace(created_at, ' ', 'T') > ?")
            params.append(after_norm)
        elif since_norm:
            conditions.append("replace(created_at, ' ', 'T') >= ?")
            params.append(since_norm)

        if until_norm:
            conditions.append("replace(created_at, ' ', 'T') <= ?")
            params.append(until_norm)

        order_dir = "ASC" if str(order).strip().upper() == "ASC" else "DESC"
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT * FROM course_deltas
            {where_clause}
            ORDER BY created_at {order_dir}, id {order_dir}
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

        now_utc = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.executemany(
                """
                INSERT INTO quota_snapshots (
                    term, course_code, section, quota_department, status, quota, current,
                    quota_numeric, current_numeric, is_consent, is_unlimited, available,
                    captured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        term, course_code, section, r.department, r.status, r.quota, r.current,
                        r.quota_numeric, r.current_numeric, int(r.is_consent), int(r.is_unlimited),
                        r.available, now_utc,
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

        now_utc = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            for r in records:
                conn.execute(
                    """
                    INSERT INTO quota_snapshots (
                        term, course_code, section, quota_department, status, quota, current,
                        quota_numeric, current_numeric, is_consent, is_unlimited, available,
                        captured_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        term, course_code, section, r.department, r.status, r.quota, r.current,
                        r.quota_numeric, r.current_numeric, int(r.is_consent), int(r.is_unlimited),
                        r.available, now_utc,
                    ),
                )

    def get_quota_snapshots(
        self,
        term: str | None = None,
        after_timestamp: str | None = None,
        since: str | None = None,
        until: str | None = None,
        order: str = "asc",
        limit: int = 500,
    ) -> list[QuotaSnapshot]:
        """Fetch quota snapshots, optionally filtered by term and/or captured strictly after a timestamp."""
        conditions: list[str] = []
        params: list[Any] = []

        if term:
            conditions.append("term = ?")
            params.append(term)

        after_norm = _normalize_timestamp(after_timestamp)
        since_norm = _normalize_timestamp(since)
        until_norm = _normalize_timestamp(until)

        if after_norm:
            conditions.append("replace(captured_at, ' ', 'T') > ?")
            params.append(after_norm)
        elif since_norm:
            conditions.append("replace(captured_at, ' ', 'T') >= ?")
            params.append(since_norm)

        if until_norm:
            conditions.append("replace(captured_at, ' ', 'T') <= ?")
            params.append(until_norm)

        order_dir = "DESC" if str(order).strip().upper() == "DESC" else "ASC"
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT * FROM quota_snapshots
            {where_clause}
            ORDER BY captured_at {order_dir}, id {order_dir}
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

    def update_department_scrape_status(
        self,
        term: str,
        code: str,
        course_count: int | None = None,
        status: str = "COMPLETED",
        error: str | None = None,
    ) -> None:
        """Update the scrape outcome and timestamp for a single department."""
        with self.db.connection() as conn:
            if course_count is not None:
                conn.execute(
                    """
                    UPDATE departments
                    SET last_scraped_at = CURRENT_TIMESTAMP,
                        course_count = ?,
                        last_status = ?,
                        last_error = ?
                    WHERE term = ? AND code = ?
                    """,
                    (course_count, status, error, term, code),
                )
            else:
                conn.execute(
                    """
                    UPDATE departments
                    SET last_scraped_at = CURRENT_TIMESTAMP,
                        last_status = ?,
                        last_error = ?
                    WHERE term = ? AND code = ?
                    """,
                    (status, error, term, code),
                )
            conn.commit()

    def get_completed_department_codes(self, term: str) -> set[str]:
        """Return the set of department codes that have been successfully scraped for a term."""
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT code FROM departments WHERE term = ? AND last_status = 'COMPLETED'",
                (term,),
            ).fetchall()
            return {row["code"] for row in rows}

    def get_failed_department_codes(self, term: str) -> list[str]:
        """Return the list of department codes that failed to scrape for a term."""
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT code FROM departments WHERE term = ? AND last_status = 'FAILED' ORDER BY code ASC",
                (term,),
            ).fetchall()
            return [row["code"] for row in rows]

    def get_term_coverage(self, term: str) -> TermCoverageSummaryDTO:
        """Calculate and return coverage metrics and department breakdown for an academic term."""
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT code, name, term, course_count, last_scraped_at, last_status, last_error, cached_at
                FROM departments
                WHERE term = ?
                ORDER BY code ASC
                """,
                (term,),
            ).fetchall()

            dept_items = [
                DepartmentCoverageItemDTO(
                    code=row["code"],
                    name=row["name"],
                    term=row["term"],
                    course_count=row["course_count"] or 0,
                    last_scraped_at=row["last_scraped_at"],
                    status=row["last_status"] or "PENDING",
                    error_message=row["last_error"],
                    cached_at=row["cached_at"],
                )
                for row in rows
            ]

            total_depts = len(dept_items)
            completed = sum(1 for d in dept_items if d.status == "COMPLETED")
            failed = sum(1 for d in dept_items if d.status == "FAILED")
            pending = total_depts - completed - failed
            total_courses = sum(d.course_count for d in dept_items)
            pct = round((completed / total_depts * 100), 1) if total_depts > 0 else 0.0

            last_scraped = None
            scraped_times = [d.last_scraped_at for d in dept_items if d.last_scraped_at]
            if scraped_times:
                last_scraped = max(scraped_times)

            return TermCoverageSummaryDTO(
                term=term,
                total_departments=total_depts,
                completed_departments=completed,
                pending_departments=pending,
                failed_departments=failed,
                total_courses=total_courses,
                percent_complete=pct,
                last_scraped_at=last_scraped,
                departments=dept_items,
            )

    def get_master_coverage(self) -> MasterCoverageSummaryDTO:
        """Calculate aggregate multi-term coverage telemetry across all academic terms."""
        terms = self.get_terms()
        if not terms:
            return MasterCoverageSummaryDTO()

        term_summaries = [self.get_term_coverage(t) for t in terms]
        total_depts = sum(s.total_departments for s in term_summaries)
        completed = sum(s.completed_departments for s in term_summaries)
        pending = sum(s.pending_departments for s in term_summaries)
        failed = sum(s.failed_departments for s in term_summaries)
        total_courses = sum(s.total_courses for s in term_summaries)
        pct = round((completed / total_depts * 100), 1) if total_depts > 0 else 0.0

        return MasterCoverageSummaryDTO(
            total_terms=len(term_summaries),
            total_departments=total_depts,
            completed_departments=completed,
            pending_departments=pending,
            failed_departments=failed,
            total_courses=total_courses,
            percent_complete=pct,
            terms=term_summaries,
        )
