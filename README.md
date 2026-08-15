# boun-scrape

An asynchronous ingestion service for Boğaziçi University (BOUN) course registration data. It scrapes course schedules and live enrollment quotas from the university's registration portals, detects changes between scrape cycles, persists everything to SQLite, and exposes it all through a REST API — with a small React dashboard on top.

---

## What it does

- **Scrapes** course schedules from `registration.bogazici.edu.tr` (an ASP.NET Web Forms site — the scraper drives its ViewState POST flow) and live quota/enrollment data from `registration.boun.edu.tr`.
- **Detects changes** between consecutive scrapes of the same term using SHA-256 content hashing, and classifies them (course added/removed, instructor changed, room changed, time slot changed, or other metadata modified).
- **Persists** courses, meeting slots, scrape run history, and change deltas to a single SQLite database.
- **Serves** everything over a FastAPI REST API — course search, live quota lookups, change feeds, run history, and file exports (JSON/CSV/SQLite).
- **Notifies** external systems of detected changes via HMAC-signed webhooks.
- **Ships** a Typer CLI (`boun-scrape`) for one-off scrapes, running the API server, running a background scheduling daemon, exporting data, and checking live quota from the terminal.

The whole backend is a single Python package: `src/boun_scrape/`. There is no separate subprocess pipeline — scraping, parsing, diffing, and persistence all happen in-process using `asyncio` and `httpx`.

---

## Architecture at a glance

```
                     ┌──────────────────────────┐
                     │  React 19 / Vite SPA      │
                     │  (frontend/, terminal UI) │
                     └────────────┬──────────────┘
                                  │ /api/* (legacy compat router)
                                  ▼
                     ┌──────────────────────────┐
                     │   FastAPI application     │
                     │   boun_scrape.api.app     │
                     │  /api/v1/*  +  /api/*     │
                     └──┬─────────────┬──────────┘
                        │             │
             reads/writes             triggers
                        ▼             ▼
              ┌──────────────┐  ┌───────────────────────┐
              │ SQLite (WAL) │  │ ScrapeScheduler        │
              │ courses,     │  │ (async scrape cycle:   │
              │ slots, runs, │  │  scrape -> diff ->     │
              │ deltas       │  │  persist -> export ->  │
              └──────────────┘  │  webhook dispatch)     │
                                 └───────────┬────────────┘
                                             │ httpx (async)
                                             ▼
                          registration.bogazici.edu.tr (schedules)
                          registration.boun.edu.tr (live quota)
```

See [docs/architecture.md](docs/architecture.md) for the full breakdown.

---

## Repository layout

```
src/boun_scrape/
├── domain/       Pure dataclasses (Course, CourseSlot, Department, QuotaRecord, ScrapeRunSummary)
│                 and pydantic DTOs for the API boundary
├── scraper/      HTML tokenizer, BeautifulSoup parser, async httpx client, live quota service,
│                 async scrape flow (asyncio.Semaphore-bounded concurrency)
├── storage/      SQLite DatabaseManager (WAL mode) and CourseRepository (queries)
├── pipeline/     SHA-256 content-hash delta detection, JSON/CSV/SQLite exporters
├── feeds/        HMAC-SHA256 signed webhook dispatcher
├── scheduler/    ScrapeScheduler — the interval/cron background daemon loop
├── api/          FastAPI app factory, hand-rolled JWT auth, rate limiting, routes
└── cli/          Typer CLI: scrape, serve, daemon, export, quota

frontend/         React 19 + Vite + Tailwind 4 SPA (terminal/cyberpunk aesthetic),
                   talks to the legacy /api/* router only

docs/             Architecture and reference documentation (see docs/README.md)
```

---

## Quickstart

### Option A — CLI (local development)

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv pip install -e .

# Run a one-off scrape of the current term into schedules.db
boun-scrape scrape

# Serve the REST API on :8000 (http://localhost:8000/docs for OpenAPI docs)
boun-scrape serve --reload

# Export persisted data for a term to JSON/CSV/SQLite
boun-scrape export --term "2024/2025-1" --format all

# Check live quota for a course section
boun-scrape quota --abbr CMPE --code 150 --section 01
```

In development (`ENVIRONMENT` unset or one of `development`/`dev`/`test`/`testing`/`local`), the app auto-generates an ephemeral JWT secret and admin password on startup and logs the generated password so you can log in — no `.env` required to get started.

Scraping is **not** automatic — `boun-scrape scrape` runs once and exits. For periodic scraping, run the daemon explicitly:

```bash
boun-scrape daemon --interval 3600        # every hour
boun-scrape daemon --cron "0 */2 * * *"   # every 2 hours, cron syntax
```

### Option B — Docker Compose

```bash
cp .env.example .env
# edit .env: set ENVIRONMENT=production, JWT_SECRET_KEY, ADMIN_PASSWORD_HASH, ALLOWED_ORIGINS
docker compose up -d --build
```

- Frontend dashboard: `http://localhost:5173`
- API + OpenAPI docs: `http://localhost:8000/docs`

`docker-compose.yml` runs two services — `backend` (the FastAPI server, via `boun-scrape serve` under uvicorn) and `frontend` (Nginx, serving the built SPA and reverse-proxying `/api` to `backend:8000`). **Neither service runs the scheduler daemon.** The container's default command only serves the API; scraping must be triggered on demand via `POST /api/v1/scraper/trigger` (or the legacy `POST /api/scrape/start`), or by running `boun-scrape daemon` yourself (e.g. as a separate process or container).

In production, `ENVIRONMENT`, `JWT_SECRET_KEY`, and `ADMIN_PASSWORD_HASH` are required — the app refuses to start without them. Generate values with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"                                   # JWT_SECRET_KEY
python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())" # ADMIN_PASSWORD_HASH
```

---

## Documentation

Detailed reference docs live in [`docs/`](docs/README.md):

- [`docs/architecture.md`](docs/architecture.md) — system architecture, component breakdown, security model
- [`docs/backend-architecture.md`](docs/backend-architecture.md) — package-by-package breakdown of `src/boun_scrape/`
- [`docs/scraping-pipeline.md`](docs/scraping-pipeline.md) — how scraping, parsing, and delta detection work
- [`docs/database-schema.md`](docs/database-schema.md) — SQLite schema, indexes, PRAGMAs
- [`docs/api-reference.md`](docs/api-reference.md) — REST endpoints (`/api/v1/*` and legacy `/api/*`)
- [`docs/frontend-architecture.md`](docs/frontend-architecture.md) — React SPA structure and design system
- [`docs/llm-context.md`](docs/llm-context.md) — condensed repo map for AI coding assistants

---

## Testing

```bash
uv pip install -e ".[dev]"
pytest
```

CI (`.github/workflows/deploy.yml`) runs the test suite before building and pushing Docker images and triggering a Dokploy redeploy on pushes to `main`.
