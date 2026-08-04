# Backend Architecture Specification

This document details the backend FastAPI application, code modularization, process orchestration, authentication mechanics, and database access layer in `/home/devhax/projects/fusuyfusuy/boun-scrape/backend`.

---

## 1. Overview & Execution Context

The backend is built with **FastAPI** (Python 3.11) and served using **Uvicorn**. Dependency management is handled by **`uv`**, configured via `pyproject.toml` and locked in `uv.lock`.

### Key System Responsibilities
1. Exposing administrative REST APIs for course searching, database statistical analysis, and scraper pipeline management.
2. Managing out-of-band scraping subprocesses with live log buffering and percentage calculation.
3. Proxying real-time CORS-restricted quota requests directly to Boğaziçi University servers.
4. Managing administrative authentication via OAuth2 JWT tokens.

---

## 2. Code Organization (`backend/app/`)

```
backend/app/
├── main.py         # App factory, CORS middleware setup, startup lifecycle event
├── routes.py       # API route definitions and endpoint handlers
├── database.py     # Database connection pool, schema initialization, SQL queries
├── auth.py         # Password hashing, JWT token creation, OAuth2 bearer dependency
├── quota.py        # Real-time scraper for Boğaziçi quota portal
└── scraping.py     # Thread-safe Singleton process runner & stdout log parser
```

---

## 3. Subsystem Breakdown

### 3.1 Application Lifecycle & Entrypoint (`main.py`)
- **App Instance**: Instantiates `FastAPI(title="BOUN Scraper API", version="2.0.0")`.
- **CORS Configuration**: Reads `ALLOWED_ORIGINS` from environment. Configures `CORSMiddleware`. Automatically turns off `allow_credentials` when wildcard origins (`*`) are detected.
- **Startup Event (`@app.on_event("startup")`)**: Triggers `init_db()` from `database.py` on launch to ensure tables and indexes exist before handling requests.

---

### 3.2 Database Layer (`database.py`)

Handles raw SQLite connections and queries. Uses `sqlite3.Row` row factory for dictionary-like column access.

#### Core Helper Functions
* `get_db_connection()`: Connects to SQLite at path specified by `DB_PATH` environment variable (default: `../../schedules.db` or `/data/schedules.db`). Enables foreign keys with `PRAGMA foreign_keys = ON;`.
* `init_db()`: Executes DDL statements creating `courses` and `course_slots` tables, alongside search indexes.
* `get_db_stats()`: Returns total course count, slot count, department count, and term count.
* `get_terms()`: Returns sorted list of unique terms.
* `get_departments()`: Returns sorted list of unique department codes.
* `query_courses(term, department, search, day, page, limit)`: Paginated query builder returning course objects with nested meeting slots.

---

### 3.3 Security & Authentication (`auth.py`)

* **Password Hashing**: Cryptographic password verification using `passlib.context.CryptContext(schemes=["bcrypt"])`.
* **JWT Token Generation**: Generates signed JSON Web Tokens using `python-jose` with `HS256` algorithm. Expiration defaults to 24 hours (`ACCESS_TOKEN_EXPIRE_MINUTES = 1440`).
* **OAuth2 Security Scheme**: `OAuth2PasswordBearer(tokenUrl="/api/auth/login")`.
* **Current User Dependency (`get_current_user`)**: Decodes `Authorization: Bearer <token>` header, extracts `sub` claim (username), and verifies user existence.

---

### 3.4 Process Orchestrator (`scraping.py`)

`ScraperManager` is a **thread-safe Singleton** controlling background execution of scraping scripts (`scraper.py`, `parse_responses.py`, `scrape_all_schedules.py`, `parse_schedules_to_db.py`).

```
                    +--------------------------------+
                    |        ScraperManager          |
                    |        (Thread-Safe)           |
                    +---------------+----------------+
                                    |
            Launches Subprocess     | Monitors stdout in background thread
                                    v
                    +--------------------------------+
                    |  subprocess.Popen(sys.exec)    |
                    +---------------+----------------+
                                    |
                                    | Standard Output Lines
                                    v
                    +--------------------------------+
                    |  _log_reader_loop()            |
                    |  - Regex match: (\d+)/(\d+)    |
                    |  - Updates progress %          |
                    |  - Buffers up to 5,000 lines   |
                    +--------------------------------+
```

#### Key Responsibilities
1. **Subprocess Spawning**: Executes scripts in non-blocking background processes via `subprocess.Popen([sys.executable, script_path, ...])`.
2. **Asynchronous Log Streaming**: `_log_reader_loop` continuously reads `process.stdout`, storing lines in a fixed-size deque (max 5,000 lines).
3. **Regex Progress Tracking**: Scans log lines for pattern `r"(\d+)/(\d+)"` (e.g. `Progress: 140/320`) to calculate progress percentage (`progress = (current / total) * 100`).
4. **Lifecycle Control**: Supports status checks (`get_status()`), log retrieval (`get_logs()`), and process cancellation (`stop_scraping()`).

---

### 3.5 Quota Proxy Engine (`quota.py`)

Requests to `/api/quota/check` trigger `check_quota(abbr, code, section, donem)` in `quota.py`.

#### Operational Mechanics
1. Constructs HTTP GET query to `https://registration.boun.edu.tr/scripts/quotasearch.asp`.
2. Encodes form parameters: `abbr` (e.g. `CMPE`), `code` (e.g. `150`), `section` (e.g. `01`), `donem` (e.g. `2024/2025-1`).
3. Decodes response HTML using `Windows-1254` character encoding.
4. Uses `BeautifulSoup` to parse table rows (`schtd`, `schtd2`).
5. Returns structured quota data: `quota`, `enrolled`, `consent`, `open_slots`, `status` (`open`/`closed`/`consent`/`unlimited`).

---

## 4. Dependencies (`pyproject.toml`)

```toml
[project]
name = "boun-scrape-backend"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.136.1",
    "uvicorn>=0.47.0",
    "requests>=2.33.1",
    "beautifulsoup4>=4.14.3",
    "python-jose[cryptography]>=3.5.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.29",
]
```
