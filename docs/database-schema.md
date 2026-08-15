# Database Schema Specification

This document details the SQLite database design, table definitions, indexes, PRAGMAs, and persistence behavior for **boun-scrape**. Schema is defined in a single place: `src/boun_scrape/storage/database.py` (`SCHEMA_SQL`), applied via `DatabaseManager.init_db()` (called on every API server startup and by every CLI command that touches the DB).

---

## 1. Entity-Relationship Overview

```
+--------------------------+          +------------------------------------+
|       DEPARTMENTS        |          |               COURSES               |
+--------------------------+          +------------------------------------+
| code       TEXT          |          | id (PK, AUTOINCREMENT)  INTEGER    |
| name       TEXT          |          | term                    TEXT       |
| term       TEXT          |          | department               TEXT       |
| url_bolum  TEXT           |          | course_code              TEXT       |
| PK(code, term)            |          | section                  TEXT       |
+--------------------------+          | course_name               TEXT       |
                                       | instructor                TEXT       |
                                       | credits                   REAL       |
                                       | ects                      REAL       |
                                       | delivery_method            TEXT       |
                                       | exam_location              TEXT       |
                                       | exam_date                  TEXT       |
                                       | sl                         TEXT       |
                                       | required_for               TEXT       |
                                       | departments                TEXT       |
                                       | content_hash               TEXT       |
                                       | created_at                 TIMESTAMP  |
                                       | updated_at                 TIMESTAMP  |
                                       +------------+-------------------------+
                                                    | 1
                                                    | cascades on delete
                                                    | N
                                       +------------v-------------------------+
                                       |            COURSE_SLOTS              |
                                       +---------------------------------------+
                                       | id (PK, AUTOINCREMENT)  INTEGER      |
                                       | course_id (FK -> courses.id)         |
                                       | day                      TEXT        |
                                       | hour                     TEXT        |
                                       | room                     TEXT        |
                                       | slot_title                TEXT        |
                                       | instructor                TEXT        |
                                       +---------------------------------------+

+---------------------------------------+     +----------------------------------------+
|              SCRAPE_RUNS                |     |             COURSE_DELTAS               |
+---------------------------------------+     +----------------------------------------+
| run_id (PK)              TEXT          |     | id (PK, AUTOINCREMENT)   INTEGER       |
| term                     TEXT          |     | run_id                   TEXT          |
| started_at               TIMESTAMP     |     | term                     TEXT          |
| completed_at             TIMESTAMP     |     | change_type              TEXT          |
| total_departments        INTEGER       |     | course_code              TEXT          |
| total_courses            INTEGER       |     | section                  TEXT          |
| total_slots              INTEGER       |     | diff_fields              TEXT (JSON)   |
| changes_detected         INTEGER       |     | previous_data            TEXT (JSON)   |
| status                   TEXT          |     | current_data             TEXT (JSON)   |
| error_message            TEXT          |     | created_at               TIMESTAMP     |
+---------------------------------------+     +----------------------------------------+
```

There is no foreign key from `course_deltas` to `scrape_runs`/`courses` at the schema level — `run_id` and `course_code`/`section` are plain text columns used for filtering, not enforced references. `courses` has no unique constraint on `(term, department, course_code, section)`; uniqueness per term is instead maintained procedurally — `save_courses_and_slots` deletes all rows for a term before re-inserting the freshly scraped set.

---

## 2. Table Definitions (DDL)

```sql
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

-- Course meeting slots table
CREATE TABLE IF NOT EXISTS course_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    day TEXT,
    hour TEXT,
    room TEXT,
    slot_title TEXT,
    instructor TEXT
);

-- Scrape run summary table
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

-- Course change delta events table
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
```

`change_type` values (see `domain/events.py:ChangeType`): `ADDED`, `REMOVED`, `MODIFIED`, `SLOTS_CHANGED`, `INSTRUCTOR_CHANGED`, `ROOM_CHANGED`.

---

## 3. Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_courses_term_dept ON courses(term, department);
CREATE INDEX IF NOT EXISTS idx_courses_term_code_sec ON courses(term, course_code, section);
CREATE INDEX IF NOT EXISTS idx_course_slots_course_id ON course_slots(course_id);
CREATE INDEX IF NOT EXISTS idx_course_slots_day_hour ON course_slots(day, hour);
CREATE INDEX IF NOT EXISTS idx_course_deltas_run_id ON course_deltas(run_id);
CREATE INDEX IF NOT EXISTS idx_course_deltas_term ON course_deltas(term);
```

---

## 4. Connection PRAGMAs

Applied on every connection in `DatabaseManager.get_connection()`:

```sql
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
-- Only for on-disk databases (skipped for ':memory:'):
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
```

WAL mode allows concurrent readers alongside a single writer without blocking, which matters because the API server, CLI commands, and the background scheduler daemon may all open connections against the same database file. `busy_timeout = 5000` gives writers up to 5 seconds to acquire a lock before failing with `SQLITE_BUSY`, instead of failing immediately.

There is no bulk-insert PRAGMA relaxation (no `synchronous = OFF` / `journal_mode = MEMORY`) — durability is preferred over raw insert throughput, and a full term's courses/slots typically number in the low thousands, not requiring it.

---

## 5. Write Path: Atomic Term Replacement

`CourseRepository.save_courses_and_slots(term, courses)` (`storage/repository.py`) runs inside a single `DatabaseManager.transaction()`:

```python
with self.db.transaction() as conn:
    conn.execute("DELETE FROM courses WHERE term = ?", (term,))  # cascades to course_slots
    for course in courses:
        content_hash = compute_course_hash(course)
        cursor = conn.execute("INSERT INTO courses (...) VALUES (...)", (...))
        course_id = cursor.lastrowid
        if course.slots:
            conn.executemany("INSERT INTO course_slots (...) VALUES (...)", [...])
```

Because this runs inside one transaction, a scrape cycle never leaves a term's data half-replaced — readers either see the old complete set or the new complete set, never a partial mix.

---

## 6. Standard Query Patterns

### 6.1 Filtered, paginated course search (`CourseRepository.get_courses`)
Builds a dynamic `WHERE` clause from `CourseFilterParams` (term, department, course_code, instructor, day, hour, room, slot_title, keyword), counts total matches, then fetches one page of `courses` rows plus all matching `course_slots` in a second query (avoiding a row-multiplying `JOIN`):

```sql
SELECT COUNT(*) AS total FROM courses c WHERE ...;

SELECT c.* FROM courses c WHERE ...
ORDER BY c.course_code ASC, c.section ASC, c.id ASC
LIMIT ? OFFSET ?;

SELECT * FROM course_slots
WHERE course_id IN (...)
ORDER BY course_id, id ASC;
```

Day/hour/room/slot_title filters use a correlated `EXISTS` subquery against `course_slots` rather than a `JOIN`, so a course with multiple matching slots isn't duplicated in the result set.

### 6.2 Terms list (union of courses and departments)
```sql
SELECT DISTINCT term FROM courses
UNION
SELECT DISTINCT term FROM departments
ORDER BY term DESC;
```

### 6.3 Legacy `/api/stats` aggregate counts
```sql
SELECT COUNT(*) FROM courses;
SELECT COUNT(*) FROM course_slots;
```
(department and term counts are derived from `CourseRepository.get_departments()` / `get_terms()` in Python, not a single SQL aggregate query.)
