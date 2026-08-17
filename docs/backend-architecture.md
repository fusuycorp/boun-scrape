# Backend Architecture Specification

This document details the backend Python package (`src/boun_scrape/`), its module boundaries, request flow, and background execution model.

---

## 1. Overview & Execution Context

The backend is a single installable Python package, `boun_scrape`, built with **FastAPI** (Python 3.12+) and served via **Uvicorn**. Dependency management uses **`uv`** (`pyproject.toml`). It ships one console script, `boun-scrape` (`src/boun_scrape/cli/app.py:main`), which is a Typer CLI exposing `scrape`, `serve`, `daemon`, `export`, and `quota` subcommands.

There are no standalone pipeline scripts and no subprocess orchestration. Scraping runs as native `asyncio` coroutines inside whichever process invoked it — the CLI process for `boun-scrape scrape`/`daemon`, or the FastAPI server process when triggered via `/api/v1/scraper/trigger` (backed by `scheduler.run_in_background()`, which retains a strong reference to the task so it isn't garbage-collected mid-run).

### Key Responsibilities
1. Serving REST endpoints for course search, live quota, change feeds, run history, and file exports.
2. Running scrape cycles on demand (or on an interval/cron schedule if the `daemon` CLI command is used) with built-in change detection.
3. Authenticating administrative operations via a hand-rolled JWT scheme and bcrypt password verification.
4. Dispatching HMAC-signed webhooks when courses change.

---

## 2. Code Organization (`src/boun_scrape/`)

```
src/boun_scrape/
├── config.py              # pydantic-settings Settings class (env vars, secret resolution)
├── domain/
│   ├── models.py           # Course, CourseSlot, Department, QuotaRecord, ScrapeRunSummary, RunStatus, DayOfWeek, QuotaStatus
│   ├── events.py           # CourseDeltaEvent, ChangeType, ScrapeEvent
│   └── dto.py               # Pydantic DTOs + domain<->DTO conversion helpers
├── scraper/
│   ├── slot_tokenizer.py   # Day/hour/room string tokenization (parse_days, parse_hours, parse_rooms, build_slots)
│   ├── parser.py           # BeautifulSoup HTML parsers (ViewState, departments, schedules, quota)
│   ├── client.py           # BounScraperClient: async httpx client (jitter, retry, windows-1254, reCAPTCHA detection)
│   ├── quota.py            # QuotaService: live quota fetch with in-memory TTL cache
│   └── flow.py             # discover_terms, fetch_departments, fetch_department_schedule, scrape_term_pipeline
├── storage/
│   ├── database.py         # DatabaseManager: SQLite connection factory, PRAGMAs, schema DDL
│   └── repository.py       # CourseRepository: all persistence queries
├── pipeline/
│   ├── delta.py            # compute_course_hash, compute_deltas (SHA-256 content diffing)
│   └── exporter.py         # export_courses_json/csv/sqlite, generate_all_exports (atomic writes)
├── feeds/
│   └── webhooks.py         # WebhookDispatcher: HMAC-SHA256 signed async delivery with retry
├── scheduler/
│   └── runner.py           # ScrapeScheduler: execute_scrape_cycle(), interval/cron background loop
├── api/
│   ├── app.py              # create_app() factory, CORS, lifespan (DB init), exception handlers
│   ├── auth.py              # create_jwt_token / verify_jwt_token (hand-rolled HS256), verify_password (bcrypt), get_current_user
│   ├── rate_limit.py         # RateLimiter (per-IP sliding window), scoped to app.state
│   ├── logging_buffer.py    # In-memory circular log buffer for /scraper/logs
│   ├── deps.py               # FastAPI dependency providers (settings, repo, client, quota service, scheduler, log buffer)
│   └── routes/
│       ├── auth.py          # /api/v1/auth/login, /api/v1/auth/me
│       ├── courses.py       # /api/v1/courses, /api/v1/departments, /api/v1/terms, /api/v1/stats
│       ├── quota.py         # /api/v1/quota, /api/v1/quota/batch
│       ├── feeds.py         # /api/v1/feeds/deltas, /api/v1/feeds/runs, /api/v1/feeds/exports/{term}/{format}
│       └── scraper.py       # /api/v1/scraper/trigger, /status, /stop, /logs, /config
└── cli/
    └── app.py               # Typer CLI: scrape, serve, daemon, export, quota
```

---

## 3. Subsystem Breakdown

### 3.1 Application Factory & Lifecycle (`api/app.py`)
- `create_app(settings: Settings | None = None) -> FastAPI` builds the app: sets up buffered logging, instantiates `FastAPI(title="boun-scrape API", version="0.2.0", lifespan=lifespan)`, attaches per-app `login_rate_limiter` and `quota_rate_limiter` to `app.state`, configures `CORSMiddleware` from `Settings.allowed_origins`, registers a `GET /` health check (`HealthCheckDTO`), registers exception handlers for `ScrapeAlreadyRunningError` (409), `ScrapeSchedulerError` (500), and `ValueError` (400), then mounts `auth_router`, `courses_router`, `quota_router`, `feeds_router`, `scraper_router` — all under `/api/v1`.
- The `lifespan` async context manager runs `DatabaseManager(settings.db_path).init_db()` on startup so schema exists before the first request.

### 3.2 Storage Layer (`storage/database.py`, `storage/repository.py`)
- `DatabaseManager` owns connection creation (`sqlite3.connect(..., check_same_thread=False)`, row factory `sqlite3.Row`), PRAGMA configuration, and two context managers: `connection()` (plain) and `transaction()` (commit/rollback via `with conn:`).
- `CourseRepository` wraps `DatabaseManager` with all higher-level queries: `save_departments`, `save_courses_and_slots` (atomic term replace), `get_courses` (filtered/paginated), `get_courses_by_term`, `get_course_by_id`, `get_departments`, `get_terms`, `save_scrape_run`, `get_scrape_runs`, `get_latest_run`, `save_deltas`, `get_deltas`.

### 3.3 Security & Authentication (`api/auth.py`)
- **JWT**: hand-rolled HS256 implementation — `create_jwt_token`/`verify_jwt_token` build/verify a `header.payload.signature` token using base64url encoding and `hmac.new(..., hashlib.sha256)`. This is **not** `python-jose` or any third-party JWT library; it's ~80 lines of stdlib `hmac`/`base64`/`json`. Tokens default to a 1-day expiry (`exp`/`iat` claims).
- **Password verification**: `verify_password(plain, hash)` calls `bcrypt.checkpw` exclusively. No plaintext comparison, no alternate hash fallback — an invalid (non-bcrypt) hash simply fails verification.
- **`get_current_user`**: FastAPI dependency reading the `Authorization: Bearer` header via `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)`, verifying the JWT against `settings.jwt_secret_key`, and returning the `sub` claim (username). Raises 401 if missing/invalid.
- **Secrets**: `Settings.jwt_secret_key` and `Settings.admin_password_hash` are `None` by default with no hardcoded fallback values. See `config.py`'s `_resolve_secrets` model validator — production (non-dev `ENVIRONMENT`) startup fails loudly if either is unset; dev environments get an ephemeral generated secret/password instead.

### 3.4 Rate Limiting (`api/rate_limit.py`)
- `RateLimiter(max_requests, window_seconds)` — an in-memory, per-client-IP `deque`-based sliding window. Instantiated per FastAPI app (`app.state.login_rate_limiter`, `app.state.quota_rate_limiter`) rather than as a module global, so separate app instances (e.g. tests) don't share state. Single-process only — insufficient alone for a multi-worker/multi-replica deployment.

### 3.5 Dependency Injection (`api/deps.py`)
- Provides FastAPI `Depends()`-compatible factory functions for `Settings`, `DatabaseManager`, `CourseRepository`, `BounScraperClient`, `QuotaService`, `WebhookDispatcher`, `ScrapeScheduler`, and `LogBuffer`. The scraper client, quota service, webhook dispatcher, and scheduler are process-wide singletons via `@lru_cache`, so a single `BounScraperClient` connection pool and a single `ScrapeScheduler` (with its own cycle lock) are shared across all requests.

### 3.6 Scraper Client (`scraper/client.py`)
- `BounScraperClient` wraps `httpx.AsyncClient` with: cookie loading from `cookies_path` (Netscape/curl/key=value formats supported), a connection pool sized off `max_concurrency`, jittered delay before every request (`min_jitter`–`max_jitter`), automatic `windows-1254` response decoding, reCAPTCHA block-page detection (raises `RecaptchaBlockedError`), and exponential-backoff retry (default 3 attempts) on transport errors and 5xx responses — 4xx errors are not retried.

### 3.7 Scrape Orchestration (`scheduler/runner.py`)
- `ScrapeScheduler.execute_scrape_cycle(term, export, dispatch_webhooks)` is the single entry point for a full scrape: resolves the target term (explicit arg → `default_term` → portal discovery of the first available term), scrapes it (`scraper.flow.scrape_term_pipeline`), loads the previously-persisted courses for that term, computes deltas (`pipeline.delta.compute_deltas`), atomically persists courses/slots and deltas, optionally writes export artifacts, and optionally dispatches webhooks. A run's status (`pending`/`running`/`completed`/`failed`/`cancelled`) is persisted to `scrape_runs` throughout, including on failure.
- Concurrent cycles are prevented by an `asyncio.Lock` (`_cycle_lock`); a second trigger while one is running raises `ScrapeAlreadyRunningError`.
- `ScrapeScheduler.start()`/`.stop()` control an optional background loop (`_schedule_loop`) that re-invokes `execute_scrape_cycle()` on a fixed interval or cron expression (via `croniter`). This loop is **only** started by the CLI's `daemon` command — it is never started implicitly by `create_app()` or the `serve` command.

### 3.8 Live Quota (`scraper/quota.py`)
- `QuotaService.fetch_quota(term, abbr, code, section, bypass_cache)` queries `{quota_url}/scripts/quotasearch.asp`, parses the response with `scraper.parser.parse_quota_from_html`, and caches results in memory for `ttl_seconds` (default 30s) keyed by `term:abbr:code:section`. `fetch_batch_quotas` runs multiple lookups concurrently under an `asyncio.Semaphore`.

---

## 4. Dependencies (`pyproject.toml`)

```toml
[project]
name = "boun-scrape"
version = "0.2.0"
requires-python = ">=3.11"
dependencies = [
    "beautifulsoup4>=4.12.3",
    "fastapi>=0.115.0",
    "httpx>=0.28.1",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.4.0",
    "typer>=0.12.0",
    "uvicorn>=0.30.0",
    "croniter>=2.0.0",
    "python-multipart>=0.0.18",
    "bcrypt>=4.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0"]

[project.scripts]
boun-scrape = "boun_scrape.cli.app:main"
```

Notably absent compared to older iterations of this project: `requests` (replaced by `httpx`), `python-jose` (JWT is hand-rolled), and `passlib` (password hashing calls `bcrypt` directly).
