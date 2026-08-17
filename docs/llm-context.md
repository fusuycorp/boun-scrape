# LLM Context Reference & Repo Map

> **Note for AI coding assistants**: This file is a condensed, single-file reference summarizing repository architecture, file maps, environment variables, and core code signatures for `boun-scrape`. Use this when reasoning about or modifying code in this codebase. For deeper detail, see the other files in `docs/`.

---

## 1. Core Architecture & Tech Stack

- **Repository**: `boun-scrape` — Boğaziçi University course registration schedule scraper, change-detection service, and REST API, with a small React admin dashboard.
- **Backend**: Single Python package `src/boun_scrape/`, Python 3.12+, FastAPI + Uvicorn, fully async (`httpx`, `asyncio`). Package manager: `uv`.
- **Frontend**: React 19 + Vite + Tailwind CSS v4, terminal/cyberpunk design system. Located in `frontend/`. Calls the `/api/v1/*` surface exclusively.
- **Database**: SQLite (WAL mode), single file at `Settings.db_path` (default `schedules.db`, `/data/schedules.db` in containers).
- **Reverse proxy**: Nginx (frontend container) forwards `/api` to `backend:8000`.

**Important**: There is no `backend/` directory and no standalone scraper subprocess scripts (`scraper.py`, `parse_responses.py`, `scrape_all_schedules.py`, `parse_schedules_to_db.py`) in this codebase — an older architecture described those and has been fully removed. All scraping/parsing/persistence logic lives in `src/boun_scrape/`.

---

## 2. Directory Structure & Key Files

```
boun-scrape/
├── docker-compose.yml              # backend + frontend services; backend runs `serve` only (no daemon)
├── Dockerfile                      # Backend: 2-stage build, uv, python:3.12-slim runtime
├── .env.example                    # Env var template with placeholder secrets
├── pyproject.toml                  # Backend deps + `boun-scrape` console script entry point
│
├── docs/                           # This documentation suite
│   ├── README.md                   # Documentation index
│   ├── architecture.md             # System architecture, C4-style container diagram, security model
│   ├── backend-architecture.md     # Python package module-by-module breakdown
│   ├── frontend-architecture.md    # React SPA structure & design system
│   ├── scraping-pipeline.md        # Scrape flow, parsing, delta detection, quota proxy
│   ├── api-reference.md            # /api/v1/* endpoint reference
│   ├── database-schema.md          # SQLite DDL, indexes, PRAGMAs
│   └── llm-context.md              # THIS FILE
│
├── src/boun_scrape/
│   ├── config.py                    # Settings (pydantic-settings): BOUN_-prefixed + unprefixed env aliases
│   ├── domain/
│   │   ├── models.py                 # Course, CourseSlot, Department, QuotaRecord, ScrapeRunSummary, RunStatus
│   │   ├── events.py                 # CourseDeltaEvent, ChangeType, ScrapeEvent
│   │   └── dto.py                    # Pydantic API DTOs + conversion helpers
│   ├── scraper/
│   │   ├── slot_tokenizer.py         # parse_days / parse_hours / parse_rooms / build_slots
│   │   ├── parser.py                 # BeautifulSoup HTML parsers (ViewState, departments, schedules, quota)
│   │   ├── client.py                 # BounScraperClient (async httpx, jitter, retry, reCAPTCHA detection)
│   │   ├── quota.py                  # QuotaService (TTL-cached live quota fetch)
│   │   └── flow.py                   # discover_terms, fetch_departments, scrape_term_pipeline
│   ├── storage/
│   │   ├── database.py               # DatabaseManager (SQLite conn/PRAGMAs/schema)
│   │   └── repository.py             # CourseRepository (all persistence queries)
│   ├── pipeline/
│   │   ├── delta.py                  # compute_course_hash, compute_deltas (SHA-256 diffing)
│   │   └── exporter.py               # export_courses_json/csv/sqlite (atomic writes)
│   ├── feeds/
│   │   └── webhooks.py               # WebhookDispatcher (HMAC-SHA256 signed delivery)
│   ├── scheduler/
│   │   └── runner.py                 # ScrapeScheduler (execute_scrape_cycle, interval/cron loop)
│   ├── api/
│   │   ├── app.py                    # create_app() factory
│   │   ├── auth.py                   # Hand-rolled JWT (HS256) + bcrypt password verification
│   │   ├── rate_limit.py             # Per-IP sliding window RateLimiter
│   │   ├── deps.py                   # DI providers
│   │   └── routes/                   # auth.py, courses.py, quota.py, feeds.py, scraper.py — all under /api/v1
│   └── cli/
│       └── app.py                    # Typer CLI: scrape, serve, daemon, export, quota
│
└── frontend/                        # React 19 SPA
    ├── Dockerfile                    # Multi-stage build (node -> nginx:alpine)
    ├── nginx.conf                    # SPA fallback + /api proxy to backend:8000
    ├── package.json                  # React 19, Vite 8, Tailwind v4, Lucide React, React Router v7
    └── src/
        ├── App.jsx                    # Router, providers, ProtectedRoute, status ticker bars
        ├── index.css                  # Terminal/cyberpunk design tokens
        ├── api/client.js              # apiRequest() fetch wrapper + api.* methods (calls /api/v1/* exclusively)
        ├── contexts/AuthContext.jsx   # Token state, session validation
        ├── hooks/useSafeAsync.js      # useMountedRef / useSafeCallback
        └── components/
            ├── Dashboard.jsx, ScraperControl.jsx, CourseData.jsx,
            ├── QuotaMonitor.jsx, ConfigManager.jsx, Login.jsx,
            └── Sidebar.jsx, ConfirmDialog.jsx, EmptyState.jsx, Toast.jsx
```

---

## 3. Environment Variables

Every field in `Settings` (`src/boun_scrape/config.py`) accepts **both** a `BOUN_`-prefixed and an unprefixed name (Dokploy compatibility) — e.g. `BOUN_DB_PATH` or `DB_PATH`.

| Key | Default | Notes |
|---|---|---|
| `ENVIRONMENT` | `development` | One of `development`/`dev`/`test`/`testing`/`local` enables dev secret auto-generation; anything else requires explicit secrets. |
| `DB_PATH` | `schedules.db` | SQLite file path. |
| `BASE_URL` | `https://registration.bogazici.edu.tr` | Schedule scraping target. |
| `QUOTA_URL` | `https://registration.boun.edu.tr` | Live quota target. |
| `COOKIES_PATH` | `cookies.txt` | Session cookie file for the scraper client. |
| `MAX_CONCURRENCY` | `10` | `asyncio.Semaphore` bound for concurrent department scraping. |
| `REQUEST_TIMEOUT` | `15.0` | httpx request timeout (seconds). |
| `MIN_JITTER` / `MAX_JITTER` | `0.05` / `0.2` | Randomized delay range before each request. |
| `JWT_SECRET_KEY` | `None` | **No hardcoded default.** Required outside dev environments — app fails to start without it. |
| `ADMIN_USER` | `admin` | Admin login username. |
| `ADMIN_PASSWORD_HASH` | `None` | **No hardcoded default.** bcrypt hash. Required outside dev environments. |
| `WEBHOOK_SECRET` | `""` | HMAC-SHA256 signing key for outbound webhooks (unsigned if empty). |
| `EXPORT_DIR` | `exports` | Destination for JSON/CSV/SQLite export artifacts. |
| `ALLOWED_ORIGINS` | `["*"]` | CORS origins (comma-separated string or JSON list). Credentials disabled automatically when wildcard. |

**Never** put a real secret value in documentation or example files — `.env.example` uses placeholder strings like `CHANGE_ME_GENERATE_A_RANDOM_SECRET`, and code examples for generating secrets are the only acceptable form.

---

## 4. Key Code Signatures

### Scrape cycle entry point (`scheduler/runner.py`)
```python
class ScrapeScheduler:
    async def execute_scrape_cycle(
        self, term: str | None = None, export: bool = True, dispatch_webhooks: bool = True,
    ) -> ScrapeRunSummary: ...
    def start(self) -> asyncio.Task[None]: ...   # starts interval/cron background loop
    async def stop(self) -> None: ...
```

### Repository (`storage/repository.py`)
```python
class CourseRepository:
    def get_courses(self, filters: CourseFilterParams) -> tuple[list[Course], int]: ...
    def save_courses_and_slots(self, term: str, courses: list[Course]) -> int: ...  # atomic term replace
    def get_deltas(self, term: str | None = None, run_id: str | None = None, limit: int = 100) -> list[CourseDeltaEvent]: ...
```

### Delta detection (`pipeline/delta.py`)
```python
def compute_course_hash(course: Course) -> str: ...   # SHA-256 over canonical JSON
def compute_deltas(previous_courses: list[Course], current_courses: list[Course], run_id: str, term: str) -> list[CourseDeltaEvent]: ...
```

### Auth (`api/auth.py`) — hand-rolled JWT, NOT python-jose
```python
def create_jwt_token(payload: dict, secret_key: str, expires_delta: timedelta | None = None) -> str: ...
def verify_jwt_token(token: str, secret_key: str) -> dict | None: ...
def verify_password(plain_password: str, password_hash: str) -> bool: ...  # bcrypt.checkpw only
```

### Frontend unmount-safety hook (`frontend/src/hooks/useSafeAsync.js`)
```javascript
export function useMountedRef() {
  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    return () => { isMountedRef.current = false; };
  }, []);
  return isMountedRef;
}
```

---

## 5. Development Commands

### Backend (CLI)
```bash
uv pip install -e .
boun-scrape scrape --term "2024/2025-1"     # one-off scrape
boun-scrape serve --reload                   # API server, dev mode, http://localhost:8000/docs
boun-scrape daemon --interval 3600           # periodic background scraping (NOT run by docker-compose)
boun-scrape export --term "2024/2025-1" --format all
boun-scrape quota --abbr CMPE --code 150 --section 01
```

### Frontend
```bash
cd frontend
npm run dev      # or `bun dev`
```

### Full containerized stack
```bash
docker compose up -d --build
```
- Frontend: `http://localhost:5173`
- API + OpenAPI docs: `http://localhost:8000/docs`
- Note: this does **not** start the scheduler daemon — only `serve` (the API). Scraping must be triggered via `POST /api/v1/scraper/trigger`, or by running `boun-scrape daemon` as a separate process.

### Tests
```bash
uv pip install -e ".[dev]"
pytest
```
CI (`.github/workflows/deploy.yml`) runs `pytest` in a `test` job that gates the Docker build/push/Dokploy-redeploy job.
