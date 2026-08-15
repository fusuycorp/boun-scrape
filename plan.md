# Modernization Plan: `boun-scrape`

## Objective
Rewrite and modernize `boun-scrape` from fragmented subprocess scripts into a unified, high-performance, asynchronous service designed to periodically scrape Boğaziçi University registration data, track changes (deltas), and feed downstream services via REST API, Webhooks, and export artifacts (JSON, CSV, SQLite).

---

## Architecture Roadmap

```
src/boun_scrape/
├── domain/                  # Pure typed data models & events (dataclass, enum)
│   ├── models.py            # Course, CourseSlot, Department, QuotaRecord, Run
│   ├── events.py            # CourseDeltaEvent, ChangeType
│   └── dto.py               # Pydantic schemas for API/Feeds
├── scraper/                 # Async scraping & pure parsing
│   ├── slot_tokenizer.py    # Day, hour, and room partition algorithms
│   ├── parser.py            # Pure HTML -> Domain model parsers
│   ├── client.py            # Resilient httpx client (windows-1254, retry, jitter, cookies)
│   ├── quota.py             # Live quota scraper with caching
│   └── flow.py              # End-to-end async scrape pipeline
├── storage/                 # Persistence layer
│   ├── database.py          # SQLite connection & optimized PRAGMAs
│   └── repository.py        # Course, slot, delta & snapshot queries
├── pipeline/                # ETL & Delta engine
│   ├── delta.py             # SHA-256 hash comparison & diff generator
│   └── exporter.py          # Parquet, JSON, CSV, SQLite exporter
├── feeds/                   # Downstream delivery
│   └── webhooks.py          # HMAC-signed webhook dispatcher
├── scheduler/               # Periodic background runner
│   └── runner.py            # Async interval & cron scheduler
├── api/                     # FastAPI v1 REST interface
│   ├── app.py               # Application factory & CORS
│   ├── deps.py              # Dependency injection
│   └── routes/              # Courses, Quota, Feeds, Scraper Control
└── cli/                     # Command-line interface
    ├── app.py               # CLI entrypoint (scrape, serve, daemon, export)
    └── __main__.py
```

---

## Tasks & Phases

### Phase 1: Project Setup & Pure Domain / Parser Layer
- [x] Configure `pyproject.toml` with dependencies (`httpx`, `beautifulsoup4`, `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `typer` or `argparse`, `pytest`, `pytest-asyncio`).
- [x] Implement `domain/models.py`, `domain/events.py`, `domain/dto.py`.
- [x] Implement `scraper/slot_tokenizer.py` (day token lookahead, hour algebraic partition, room broadcasting).
- [x] Implement `scraper/parser.py` (pure BeautifulSoup parsers for terms, departments, schedules, and quota).
- [x] Create tests with real HTML fixtures (`tests/test_slot_tokenizer.py`, `tests/test_parser.py`).

### Phase 2: Async Scraper Engine & Database Layer
- [x] Implement `config.py` (pydantic-settings BaseSettings configuration).
- [x] Implement `scraper/client.py` (async httpx, windows-1254 decoding, cookie store, backoff jitter, recaptcha detection).
- [x] Implement `scraper/flow.py` (orchestrated async pipeline with semaphore rate limiting).
- [x] Implement `storage/database.py` and `storage/repository.py` (normalized schema, transactions, composite indexes, query filters).
- [x] Implement `pipeline/delta.py` (delta computation between consecutive scrape runs).
- [x] Add unit & integration tests (`tests/test_config.py`, `tests/test_client_and_flow.py`, `tests/test_repository.py`, `tests/test_delta.py`).

### Phase 3: Feeds, Exporters & Background Scheduler
- [x] Implement `pipeline/exporter.py` (JSON, CSV, SQLite snapshot compiler).
- [x] Implement `feeds/webhooks.py` (webhook dispatcher with retries and HMAC signatures).
- [x] Implement `scheduler/runner.py` (periodic ingestion daemon).
- [x] Implement `scraper/quota.py` (live quota lookups with in-memory TTL caching).

### Phase 4: API, CLI & Packaging
- [x] Implement FastAPI endpoints under `api/routes/` (`/api/v1/courses`, `/api/v1/departments`, `/api/v1/quota`, `/api/v1/feeds/deltas`, `/api/v1/feeds/exports`, `/api/v1/scraper`).
- [x] Implement CLI commands (`cli/app.py` using typer: `scrape`, `serve`, `daemon`, `export`, `quota`).
- [x] Implement test suites: `tests/test_api.py`, `tests/test_cli.py`, `tests/test_resilience_edge_cases.py`.
- [x] Run full test suite and verify end-to-end functionality (161 tests passing).
- [ ] Build production `Dockerfile` and `docker-compose.yml`.
- [ ] Clean up legacy scripts and dead files.
