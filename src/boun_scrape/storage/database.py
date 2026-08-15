"""SQLite database connection manager and schema initialization."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_SQL = """
-- Departments table
CREATE TABLE IF NOT EXISTS departments (
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    term TEXT NOT NULL,
    url_bolum TEXT,
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

-- Indexes for high query performance
CREATE INDEX IF NOT EXISTS idx_courses_term_dept ON courses(term, department);
CREATE INDEX IF NOT EXISTS idx_courses_term_code_sec ON courses(term, course_code, section);
CREATE INDEX IF NOT EXISTS idx_course_slots_course_id ON course_slots(course_id);
CREATE INDEX IF NOT EXISTS idx_course_slots_day_hour ON course_slots(day, hour);
CREATE INDEX IF NOT EXISTS idx_course_deltas_run_id ON course_deltas(run_id);
CREATE INDEX IF NOT EXISTS idx_course_deltas_term ON course_deltas(term);
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
            conn.execute("PRAGMA journal_mode = WAL;")
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
            conn.executescript(SCHEMA_SQL)
