"""SQLite database connection manager and schema initialization."""

import logging
import sqlite3
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)
SCHEMA_SQL = """
-- Departments table
CREATE TABLE IF NOT EXISTS departments (
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    term TEXT NOT NULL,
    url_bolum TEXT,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_scraped_at TIMESTAMP,
    course_count INTEGER DEFAULT 0,
    last_status TEXT DEFAULT 'PENDING',
    last_error TEXT,
    PRIMARY KEY(code, term)
);

-- Courses table
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL,
    department TEXT NOT NULL,
    course_code TEXT NOT NULL,
    section TEXT NOT NULL,
    course_name TEXT,
    instructor TEXT,
    credits REAL,
    ects REAL,
    delivery_method TEXT,
    exam_location TEXT,
    exam_date TEXT,
    sl TEXT,
    required_for TEXT,
    departments TEXT,
    content_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Course slots table
CREATE TABLE IF NOT EXISTS course_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    day TEXT,
    hour TEXT,
    room TEXT,
    slot_title TEXT,
    instructor TEXT
);

-- Scrape runs summary table
CREATE TABLE IF NOT EXISTS scrape_runs (
    run_id TEXT PRIMARY KEY,
    term TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_departments INTEGER DEFAULT 0,
    completed_departments INTEGER DEFAULT 0,
    total_courses INTEGER DEFAULT 0,
    total_slots INTEGER DEFAULT 0,
    changes_detected INTEGER DEFAULT 0,
    status TEXT,
    error_message TEXT
);

-- Course deltas table
CREATE TABLE IF NOT EXISTS course_deltas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    term TEXT,
    change_type TEXT,
    course_code TEXT,
    section TEXT,
    diff_fields TEXT,
    previous_data TEXT,
    current_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Quota snapshot log (append-only; one row per captured department-quota line per scrape)
CREATE TABLE IF NOT EXISTS quota_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL,
    course_code TEXT NOT NULL,
    section TEXT NOT NULL,
    quota_department TEXT,
    status TEXT,
    quota TEXT,
    current TEXT,
    quota_numeric INTEGER,
    current_numeric INTEGER,
    is_consent INTEGER DEFAULT 0,
    is_unlimited INTEGER DEFAULT 0,
    available INTEGER,
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for high query performance
CREATE INDEX IF NOT EXISTS idx_courses_term_dept ON courses(term, department);
CREATE INDEX IF NOT EXISTS idx_courses_term_code_sec ON courses(term, course_code, section);
CREATE INDEX IF NOT EXISTS idx_courses_pagination ON courses(term, course_code, section, id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_courses_unique ON courses(term, department, course_code, section);
CREATE INDEX IF NOT EXISTS idx_course_slots_course_id ON course_slots(course_id);
CREATE INDEX IF NOT EXISTS idx_course_slots_day_hour ON course_slots(day, hour);
CREATE INDEX IF NOT EXISTS idx_course_deltas_run_id ON course_deltas(run_id);
CREATE INDEX IF NOT EXISTS idx_course_deltas_term ON course_deltas(term);
CREATE INDEX IF NOT EXISTS idx_course_deltas_created_at ON course_deltas(created_at);
CREATE INDEX IF NOT EXISTS idx_course_deltas_term_created ON course_deltas(term, created_at);
CREATE INDEX IF NOT EXISTS idx_quota_snapshots_term_code_sec ON quota_snapshots(term, course_code, section);
CREATE INDEX IF NOT EXISTS idx_quota_snapshots_captured_at ON quota_snapshots(captured_at);
CREATE INDEX IF NOT EXISTS idx_quota_snapshots_term_captured ON quota_snapshots(term, captured_at);
"""

class DatabaseManager:
    """Manages SQLite database connections, PRAGMA configuration, and schema."""

    def __init__(self, db_path: str = "schedules.db") -> None:
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection with optimal PRAGMAs."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row

        # Apply database PRAGMAs
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        if self.db_path != ":memory:":
            conn.execute("PRAGMA synchronous = NORMAL;")

        return conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager yielding a managed connection."""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager yielding a connection within a commit/rollback transaction."""
        conn = self.get_connection()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def init_db(self) -> None:
        """Initialize SQLite database tables and indexes."""
        with self.connection() as conn:
            if self.db_path != ":memory:":
                conn.execute("PRAGMA journal_mode = WAL;")
            conn.executescript(SCHEMA_SQL)
            self._migrate_schema(conn)

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Apply additive column migrations for databases created before columns existed."""
        # 1. scrape_runs migrations
        scrape_run_cols = {row["name"] for row in conn.execute("PRAGMA table_info(scrape_runs)")}
        expected_run_cols = [
            ("term", "TEXT"),
            ("started_at", "TIMESTAMP"),
            ("completed_at", "TIMESTAMP"),
            ("total_departments", "INTEGER DEFAULT 0"),
            ("completed_departments", "INTEGER DEFAULT 0"),
            ("total_courses", "INTEGER DEFAULT 0"),
            ("total_slots", "INTEGER DEFAULT 0"),
            ("changes_detected", "INTEGER DEFAULT 0"),
            ("status", "TEXT"),
            ("error_message", "TEXT"),
        ]
        for col, col_def in expected_run_cols:
            if col not in scrape_run_cols:
                conn.execute(f"ALTER TABLE scrape_runs ADD COLUMN {col} {col_def}")
                conn.commit()

        # 2. departments migrations
        dept_cols = {row["name"] for row in conn.execute("PRAGMA table_info(departments)")}
        expected_dept_cols = [
            ("url_bolum", "TEXT"),
            ("cached_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("last_scraped_at", "TIMESTAMP"),
            ("course_count", "INTEGER DEFAULT 0"),
            ("last_status", "TEXT DEFAULT 'PENDING'"),
            ("last_error", "TEXT"),
        ]
        for col, col_def in expected_dept_cols:
            if col not in dept_cols:
                conn.execute(f"ALTER TABLE departments ADD COLUMN {col} {col_def}")
                conn.commit()

        # 3. courses migrations
        course_cols = {row["name"] for row in conn.execute("PRAGMA table_info(courses)")}
        expected_course_cols = [
            ("course_name", "TEXT"),
            ("instructor", "TEXT"),
            ("credits", "REAL"),
            ("ects", "REAL"),
            ("delivery_method", "TEXT"),
            ("exam_location", "TEXT"),
            ("exam_date", "TEXT"),
            ("sl", "TEXT"),
            ("required_for", "TEXT"),
            ("departments", "TEXT"),
            ("content_hash", "TEXT"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ]
        for col, col_def in expected_course_cols:
            if col not in course_cols:
                conn.execute(f"ALTER TABLE courses ADD COLUMN {col} {col_def}")
                conn.commit()

        # 4. course_slots migrations
        slot_cols = {row["name"] for row in conn.execute("PRAGMA table_info(course_slots)")}
        expected_slot_cols = [
            ("day", "TEXT"),
            ("hour", "TEXT"),
            ("room", "TEXT"),
            ("slot_title", "TEXT"),
            ("instructor", "TEXT"),
        ]
        for col, col_def in expected_slot_cols:
            if col not in slot_cols:
                conn.execute(f"ALTER TABLE course_slots ADD COLUMN {col} {col_def}")
                conn.commit()

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_courses_unique ON courses (term, department, course_code, section)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_courses_pagination ON courses (term, course_code, section, id)"
        )
        # S-07: ensure course_deltas created_at index exists for existing DBs
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_course_deltas_created_at ON course_deltas(created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_course_deltas_term_created ON course_deltas(term, created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quota_snapshots_term_captured ON quota_snapshots(term, captured_at)"
        )

        # 5. Fix legacy course_slots FK missing ON DELETE CASCADE (prod DBs created
        #    before the CASCADE fix have NO ACTION, causing DELETE FROM courses
        #    to fail with FOREIGN KEY constraint when slots exist). SQLite cannot
        #    ALTER a FK, so we recreate the table when the FK is wrong.
        self._migrate_course_slots_fk(conn)

    def _migrate_course_slots_fk(self, conn: sqlite3.Connection) -> None:
        """Recreate course_slots with correct ON DELETE CASCADE if legacy FK detected."""
        try:
            fk_rows = conn.execute("PRAGMA foreign_key_list(course_slots)").fetchall()
        except sqlite3.OperationalError:
            return
        # Already correct if exactly one FK to courses(id) with CASCADE
        if fk_rows and all(
            r["table"] == "courses" and r["from"] == "course_id" and r["to"] == "id" and r["on_delete"] == "CASCADE"
            for r in fk_rows
        ):
            # Also verify NOT NULL on course_id (legacy prod had nullable)
            col_info = {r["name"]: r for r in conn.execute("PRAGMA table_info(course_slots)").fetchall()}
            course_id_row = col_info.get("course_id")
            if course_id_row is not None and course_id_row["notnull"] == 1:
                return
        # Need rebuild — preserve data, rebuild with correct schema
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
            # Retry BEGIN IMMEDIATE under contention (API + scheduler on same file)
            for attempt in range(3):
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    break
                except sqlite3.OperationalError as exc:
                    msg = str(exc).lower()
                    is_busy = "locked" in msg or "busy" in msg
                    if is_busy and attempt < 2:
                        time.sleep(0.05 * (2**attempt))
                        continue
                    logger.warning("course_slots FK migration: BEGIN IMMEDIATE failed (%s)", exc)
                    try:
                        conn.execute("PRAGMA foreign_keys = ON")
                    except Exception:
                        pass
                    raise
            else:
                # Could not acquire lock after retries
                try:
                    conn.execute("PRAGMA foreign_keys = ON")
                except Exception:
                    pass
                return
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS course_slots_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                    day TEXT,
                    hour TEXT,
                    room TEXT,
                    slot_title TEXT,
                    instructor TEXT
                );
                INSERT OR IGNORE INTO course_slots_new (id, course_id, day, hour, room, slot_title, instructor)
                    SELECT id, course_id, day, hour, room, slot_title, instructor FROM course_slots;
                DROP TABLE course_slots;
                ALTER TABLE course_slots_new RENAME TO course_slots;
                CREATE INDEX IF NOT EXISTS idx_course_slots_course_id ON course_slots(course_id);
                CREATE INDEX IF NOT EXISTS idx_course_slots_day_hour ON course_slots(day, hour);
                """
            )
            if conn.in_transaction:
                conn.execute("COMMIT")
            # Verify no FK violations after rebuild
            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                logger.warning("course_slots FK migration: %d violations after rebuild (best-effort)", len(violations))
        except sqlite3.OperationalError as exc:
            # "cannot commit - no transaction is active" is benign if executescript already committed
            if "no transaction" in str(exc).lower():
                logger.warning("course_slots FK migration commit benign: %s", exc)
            else:
                try:
                    if conn.in_transaction:
                        conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise
        except Exception as exc:
            logger.warning("course_slots FK migration failed: %s", exc)
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
        finally:
            try:
                conn.execute("PRAGMA foreign_keys = ON")
            except Exception:
                pass
