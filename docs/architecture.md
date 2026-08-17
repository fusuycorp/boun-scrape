# System Architecture Blueprint

This document details the software architecture, design principles, deployment topology, and security model of **boun-scrape**.

---

## 1. Architectural Overview & System Context

boun-scrape provides automated scraping, in-process parsing, change detection, relational persistence, and a REST API for Boğaziçi University (BOUN) course registration schedules, plus on-demand live quota lookups.

### Key Architectural Characteristics
- **Single Python package.** All backend logic — scraping, parsing, diffing, persistence, scheduling, and the HTTP API — lives in `src/boun_scrape/`, organized into `domain/`, `scraper/`, `storage/`, `pipeline/`, `feeds/`, `scheduler/`, `api/`, and `cli/` modules. There is no separate `/backend` directory and no standalone subprocess scripts.
- **Fully asynchronous.** The scraper uses `httpx.AsyncClient` with `asyncio.Semaphore`-bounded concurrency (default 10, configurable via `MAX_CONCURRENCY`), not threads or process pools.
- **Embedded persistent datastore.** SQLite in WAL mode — a single file, zero external DB dependency.
- **On-demand, not automatic scheduling.** Scraping runs only when explicitly triggered: via the CLI (`boun-scrape scrape` for a one-off run, `boun-scrape daemon` for periodic interval/cron scraping), or via an authenticated API call (`POST /api/v1/scraper/trigger`). The shipped `docker-compose.yml` does **not** run the daemon — its `backend` service only serves the API.
- **Change detection built in.** Every scrape cycle diffs the newly scraped courses against what's currently in the database for that term, using SHA-256 content hashing, and records categorized delta events.
- **Live quota proxy.** Real-time quota lookups are proxied to `registration.boun.edu.tr` on demand, with a short in-memory TTL cache.
- **Single API surface.** One typed, documented surface under `/api/v1/*`, used by both external API clients and the shipped React frontend.
- **Containerized.** Root `Dockerfile` builds the Python backend; `frontend/Dockerfile` builds the React SPA behind Nginx. `docker-compose.yml` wires the two together.

---

## 2. Container Diagram

```
+-----------------------------------------------------------------------------------+
|                                  USER BROWSER                                     |
|  - React 19 SPA (Vite), terminal/cyberpunk aesthetic                              |
|  - JWT stored in localStorage, calls /api/v1/* endpoints exclusively              |
+----------------------------------------+------------------------------------------+
                                         |
                                         | HTTP (port 5173 in compose / 80 in prod)
                                         v
+-----------------------------------------------------------------------------------+
|                            FRONTEND CONTAINER (Nginx)                             |
|  - Serves compiled static JS/CSS assets                                           |
|  - Reverse-proxies /api -> http://backend:8000/api                                |
+----------------------------------------+------------------------------------------+
                                         |
                                         | Internal Docker bridge network
                                         v
+-----------------------------------------------------------------------------------+
|                       BACKEND CONTAINER (FastAPI + Uvicorn)                       |
|  boun_scrape.api.app:create_app                                                   |
|  - Hand-rolled JWT auth (HS256 HMAC, base64url) + bcrypt password verification    |
|  - /api/v1/* : auth, courses, quota, feeds, scraper (typed, documented)           |
|  - Per-IP sliding-window rate limiting on login and quota endpoints               |
+-------------------+---------------------------------------+-----------------------+
                    |                                       |
  Reads/Writes via  |                                       | Triggers on demand
  CourseRepository  v                                       v
+-----------------------+               +-------------------------------------------+
| SQLite (WAL mode)      |               | ScrapeScheduler.execute_scrape_cycle()    |
| /data/schedules.db     |               | scrape -> diff (SHA-256) -> persist ->    |
| courses, course_slots, |               | export (JSON/CSV/SQLite) -> webhooks      |
| scrape_runs,           |               +-------------------+-----------------------+
| course_deltas          |                                   |
+-----------------------+                                    | httpx.AsyncClient (async, jittered, retried)
                                                               v
                                        +-------------------------------------------+
                                        | BOĞAZİÇİ UNIVERSITY SERVERS                |
                                        | registration.bogazici.edu.tr (schedules,   |
                                        |   ASP.NET Web Forms / ViewState POST flow) |
                                        | registration.boun.edu.tr (live quota,      |
                                        |   /scripts/quotasearch.asp)                |
                                        +-------------------------------------------+
```

Note: `docker-compose.yml`'s `backend` service runs `serve` only (via the Dockerfile `CMD`). Nothing in the shipped compose file invokes `boun-scrape daemon`; the `ScrapeScheduler`'s periodic loop is dormant unless a process explicitly calls `.start()` on it (which the CLI's `daemon` command does).

---

## 3. Top-Level Component Decomposition

### 3.1 Frontend (`frontend/`)
- **Framework**: React 19 + Vite.
- **Styling**: Tailwind CSS v4 + a custom terminal/cyberpunk design system (`src/index.css`) — dark "void" backgrounds, neon phosphor accents (green/amber/pink/cyan), CRT scanline overlay, monospace typography.
- **Routing**: React Router v7, client-side, with a `ProtectedRoute` wrapper gating everything except `/login`.
- **API access**: A single `src/api/client.js` module wraps `fetch`, attaches the JWT from `localStorage` as a Bearer token, and calls exclusively into the `/api/v1/*` surface.
- See [frontend-architecture.md](frontend-architecture.md) for component-level detail.

### 3.2 Backend (`src/boun_scrape/`)
- **Framework**: FastAPI (Python 3.12+) served via Uvicorn.
- **Dependency management**: `uv`, `pyproject.toml`.
- **Package structure**:
  - `domain/` — pure dataclasses (`Course`, `CourseSlot`, `Department`, `QuotaRecord`, `ScrapeRunSummary`, `RunStatus`), change events (`CourseDeltaEvent`, `ChangeType`), and pydantic DTOs for the API boundary.
  - `scraper/` — `slot_tokenizer.py` (day/hour/room string parsing), `parser.py` (BeautifulSoup HTML → domain objects), `client.py` (async httpx client: windows-1254 decoding, jitter, retry/backoff, reCAPTCHA detection), `quota.py` (live quota fetch with TTL cache), `flow.py` (async scrape orchestration with `asyncio.Semaphore` concurrency).
  - `storage/` — `database.py` (SQLite connection/schema manager, WAL mode), `repository.py` (`CourseRepository`, all queries).
  - `pipeline/` — `delta.py` (SHA-256 content-hash diffing), `exporter.py` (JSON/CSV/SQLite export with atomic temp-file + `os.replace` writes).
  - `feeds/` — `webhooks.py` (HMAC-SHA256 signed async webhook dispatcher).
  - `scheduler/` — `runner.py` (`ScrapeScheduler`: orchestrates a full scrape cycle and, optionally, an interval/cron background loop).
  - `api/` — `app.py` (FastAPI factory, CORS, exception handlers), `auth.py` (JWT + bcrypt), `rate_limit.py` (per-IP sliding window), `deps.py` (DI providers), `routes/` (`auth.py`, `courses.py`, `quota.py`, `feeds.py`, `scraper.py`, all mounted under `/api/v1`).
  - `cli/` — Typer app (`scrape`, `serve`, `daemon`, `export`, `quota` subcommands).
- See [backend-architecture.md](backend-architecture.md) for full module detail.

### 3.3 Scraping & Change Detection
- Scraping is invoked as a single async call, not a multi-stage subprocess pipeline: `scrape_term_pipeline()` discovers departments for a term, then fetches and parses each department's schedule concurrently (bounded by `asyncio.Semaphore`).
- Each scrape cycle (`ScrapeScheduler.execute_scrape_cycle`) does, in order: resolve target term → scrape current courses → load previously-persisted courses for that term → compute deltas (`pipeline/delta.py`) → atomically replace persisted courses/slots for the term → save deltas → optionally export artifacts → optionally dispatch webhooks.
- See [scraping-pipeline.md](scraping-pipeline.md) for the full breakdown.

---

## 4. Security Architecture & Threat Model

1. **Authentication**:
   - Hand-rolled JWT implementation in `api/auth.py` — HS256 HMAC signing over base64url-encoded header/payload, **not** `python-jose`. Tokens expire after 24 hours by default.
   - Password verification is bcrypt-only (`bcrypt.checkpw`) — no plaintext or alternate hash fallback.
   - `Settings.jwt_secret_key` and `Settings.admin_password_hash` have **no hardcoded defaults**. A `model_validator` on `Settings` raises at startup if either is unset and `ENVIRONMENT` is not one of `development`/`dev`/`test`/`testing`/`local`. In those dev environments, an ephemeral secret and admin password are generated at startup (the generated plaintext password is logged so the developer can log in; it does not persist across restarts).
   - Login (`POST /api/v1/auth/login`) is rate-limited to 5 requests per 60 seconds per client IP.
2. **Authorization**:
   - All `/api/v1/scraper/*` and `/api/v1/quota*` endpoints require a valid Bearer token via `Depends(get_current_user)`.
   - Read-only course/department/term/stats listing under `/api/v1/*` is unauthenticated.
3. **CORS**:
   - `CORSMiddleware` reads `ALLOWED_ORIGINS` (default `["*"]`). Credentials are automatically disabled when the origin list is the wildcard, to satisfy browser CORS rules.
4. **Rate limiting**:
   - In-memory, per-IP, sliding-window `RateLimiter` instances scoped to `app.state` (not module globals, so test/app instances don't leak state into each other). Applied to `/api/v1/auth/login` (5/60s) and quota endpoints (30/60s). Single-process only — not a substitute for an edge/WAF rate limiter in a multi-worker deployment.
5. **Scraper politeness & anti-bot handling**:
   - Randomized jitter (`MIN_JITTER`–`MAX_JITTER`, default 0.05–0.2s) before each HTTP request.
   - Exponential backoff retry (up to 3 attempts) on transport errors and 5xx responses.
   - Explicit detection of the registration portal's reCAPTCHA block page — raises `RecaptchaBlockedError` rather than silently failing or retrying into a wall.
6. **Nginx reverse proxy**:
   - Frontend container is the only public-facing entrypoint; the backend is only reachable on the internal Docker bridge network at `backend:8000`. Standard forwarding headers (`X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`) are set.

---

## 5. Persistence Strategy

- **Database**: Single SQLite file at `Settings.db_path` (default `schedules.db`; `/data/schedules.db` inside the container, backed by the `schedules_data` named volume in `docker-compose.yml`).
- **Connection PRAGMAs** (`storage/database.py`): `foreign_keys = ON`, `busy_timeout = 5000`, and (for on-disk databases) `journal_mode = WAL`, `synchronous = NORMAL`.
- **Writes**: Course/slot replacement for a term happens inside a single transaction (`DatabaseManager.transaction()` context manager) — old rows for the term are deleted (cascading to slots via `ON DELETE CASCADE`) and new rows inserted, so a scrape cycle never leaves a term half-updated.
- **Change tracking**: Each course row carries a `content_hash` (SHA-256 over a canonical JSON serialization of its fields and slots) so identical scrapes are cheap to detect as unchanged.
- **Exports**: `pipeline/exporter.py` writes JSON/CSV/SQLite artifacts atomically (write to a temp file in the same directory, then `os.replace`) to avoid readers observing partially-written files.
- See [database-schema.md](database-schema.md) for full table definitions and indexes.

---

## 6. Deployment Topology

- **`Dockerfile`** (repo root): two-stage build. Builder stage uses `uv` to create a virtualenv and install the package; runtime stage is `python:3.12-slim`, copies the venv and source, and runs `uvicorn boun_scrape.api.app:create_app --factory --host 0.0.0.0 --port 8000`. Includes a `HEALTHCHECK` hitting `/`.
- **`docker-compose.yml`**: two services, `backend` and `frontend`, on the default bridge network. `backend` mounts a `schedules_data` named volume at `/data`. Required production secrets (`JWT_SECRET_KEY`, `ADMIN_PASSWORD_HASH`) are read from the environment with no baked-in defaults.
- **`.github/workflows/deploy.yml`**: on push to `main`, a `test` job runs `pytest`; only if that passes does the `build-and-deploy` job build and push both Docker images and trigger a Dokploy redeploy via API call.
- **Config**: `src/boun_scrape/config.py` — a pydantic-settings `Settings` class. Every field accepts both a `BOUN_`-prefixed and an unprefixed environment variable name (for Dokploy compatibility), e.g. `BOUN_DB_PATH` or `DB_PATH`.
