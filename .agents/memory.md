# Project Memory

## Active Epics & Tasks
- In progress (started 2026-08-18): boun-scrape -> boun-archive data seeding.
  `boun-archive` (`~/projects/fusuycorp/boun-archive`) is a separate, mature,
  deployed project — a historical/analytics platform (50+ years of course-slot
  data, trend forecasting, "Ghost Schedule") on Postgres/Meilisearch/SvelteKit,
  NOT a live-state tracker. It has zero write endpoints and its only ingestion
  path today is a one-shot local `schedules.db`/`departments.csv` file drop that
  permanently no-ops after the first successful load (`migrate_to_pg.py`'s gate
  is "does `courses` have any rows at all", not per-term). Agreed plan: (1) a
  one-time backfill pull of boun-scrape's existing export, NOT a resync of
  boun-archive's full 1970s-onward history — boun-scrape never had that data
  anyway, it only ever scrapes the live current portal; (2) ongoing incremental
  sync scoped to the current term only, via polling — `after_timestamp` cursors
  on `/api/v1/feeds/deltas` and the new `/api/v1/feeds/quota-snapshots`, not a
  push/webhook receiver (boun-archive has no auth or write path to receive one
  yet, and building that was explicitly deferred). Infra: both projects already
  sit in the same Dokploy project (`boun-uni`), but no cross-stack Docker
  network exists between any two services in this homelab today — chosen
  transport is boun-archive pulling boun-scrape's already-public export/feed
  API, which avoids needing new network wiring entirely. Remaining work is
  entirely on the boun-archive side (per-term upsert ingestion job, new schema
  for quota/deltas) — out of scope for this repo/session.
- Post-modernization audit (2026-08-15 to 2026-08-17): full security/correctness/docs
  pass completed and deployed. Itemized findings are recorded as ADRs below and in
  `activity.jsonl` (the one-off `plan.md` checklist that originally tracked this
  work was deleted 2026-08-17 once agent-ctx became this project's system of
  record for development tracking).
- Resolved (2026-08-17): the ScraperControl page's 4 "phase" cards (STAGE_1-4) were
  vestigial UI referencing deleted legacy subprocess scripts and were collapsed into
  a single EXEC trigger control. `ScrapeStartRequest`/`phase`/`force_refresh` removed
  end-to-end (frontend `api/client.js`, backend `legacy.py`). If a real per-stage
  pipeline is ever wanted again, it needs actual backend support first (there is
  none — `execute_scrape_cycle()` is one atomic operation), not just UI cards.
- Resolved (2026-08-17): `GET /api/scrape/logs` 500'd on any non-empty log buffer
  (`AttributeError: 'str' object has no attribute 'strftime'` — `legacy.py` called
  `.strftime()` on `LogEntryDTO.timestamp`, which is a plain ISO-8601 `str`, not a
  `datetime`). Bug existed since the original modernization rewrite but was masked
  until the telemetry fix (see ADR below) started actually populating the log
  buffer during scrapes. Fixed via `datetime.fromisoformat(r.timestamp)` before
  formatting. `tests/test_legacy_api.py` had no coverage for a non-empty buffer —
  added `test_legacy_scrape_logs_formats_buffered_entries` to close that gap.
  Gotcha: an empty-input-only test suite can hide bugs that only fire once real
  data flows — worth deliberately testing the non-empty/populated case for any
  buffer- or list-backed endpoint.

## Core Invariants & Architecture Rules
- Auth is bcrypt-only (`api/auth.py::verify_password`). No plaintext/SHA-256
  fallback, no backdoor bypass — do not reintroduce either.
- `Settings.jwt_secret_key` / `Settings.admin_password_hash` have no hardcoded
  defaults. Outside `ENVIRONMENT` in {development,dev,test,testing,local}, the app
  fails fast at startup if either is unset (`config.py::_resolve_secrets`). Dev mode
  generates ephemeral values and logs a warning (plaintext admin password logged
  once, by design, so local dev has a usable login).
- Resolved (2026-08-17): the legacy `/api/*` surface (`api/routes/legacy.py`) is
  gone. There is now exactly one API surface: typed `/api/v1/*`
  (auth/courses/quota/feeds/scraper routers). The frontend (`api/client.js`) calls
  `/api/v1/*` exclusively. `courses`/`departments`/`terms`/`stats` are
  intentionally public (no auth) — `scraper/*` and `quota/*` require
  `Depends(get_current_user)`. See the ADR in `decisions.md` for the full
  rationale and the several live contract-mismatch bugs (broken log terminal,
  quota radar, dashboard counts, config status) this pass fixed along the way.
  Also dropped: the "seed HTML / response.html" config feature — it was accepted
  by the old `/config` POST but never read anywhere in the scraper flow; don't
  reintroduce it without an actual consumer.
- CI (`.github/workflows/deploy.yml`) runs `pytest` in a `test` job that gates
  `build-and-deploy` — do not remove this gate.
- `ScrapeScheduler.get_status()`'s real keys are `is_scraping` / `is_running` /
  `current_progress` (a dict `{completed, total, department}` or `None` when idle).
  A prior bug in `legacy.py` read a nonexistent `is_cycle_running` key — always
  double-check the legacy route's dict construction matches the scheduler's actual
  `get_status()` shape when touching either side.
- `CourseRepository.save_courses_and_slots(term, courses, scraped_departments=None)`
  only replaces rows for departments passed in `scraped_departments` — a department
  that failed to scrape this run keeps its previously-good data instead of being
  deleted (that wipe-on-failure was the 2026-08-18 data-loss bug). Pass None to get
  the old unconditional whole-term replace. `scrape_term_pipeline()` returns a
  `TermScrapeResult` (courses + succeeded/failed department lists), not a bare list.
- `execute_scrape_cycle` persists the term's discovered `Department` list via
  `save_departments` each run (`TermScrapeResult.departments`) — this is what
  populates `/api/v1/departments` and `/stats.total_departments`; do not "simplify" it
  away (save_departments was dead code before 2026-08-18 and the endpoints read an
  empty table).
- `capture_quota` is best-effort: it bulk-inserts via `save_quota_snapshots_bulk` in
  a single transaction (never per-section, which was N fsyncs) and is wrapped so a
  quota failure can never fail the already-succeeded course scrape. `QuotaService`
  cache is bounded by `max_cache_size` (default 2000, evict-oldest).
- Do NOT add eager cross-package re-exports between `storage` and `pipeline`
  (2026-08-18: `pipeline/__init__` re-exported `exporter`, which imports
  `storage.repository`, while `repository` imports `pipeline.delta` — an
  import-order-dependent cycle that broke isolated test collection). Import from the
  submodules directly; keep package `__init__`s importing only acyclic leaf modules.

## Domain Vocabulary & Gotchas
- **Dokploy stack config is NOT synced from this repo's `docker-compose.yml`.**
  Production runs a separately hand-maintained "raw compose" stack stored in
  Dokploy itself (composeId `Y1y6n7j5USm8MF4kHRuAe`), mirrored for reference at
  `~/deployment/selfhosted/services/boun-scrape/docker-stack.yml` (a sibling infra
  repo, not this one). Changing required env vars in `config.py` does NOT
  propagate to production automatically — someone has to separately push
  `compose.env`/`compose.update` to Dokploy. See `~/deployment/selfhosted/docs/
  dokploy-guide.md` §6.7 for the full incident writeup (redeploy silently no-op'ing
  due to an unchecked curl exit code + a stale org-level `DOKPLOY_API_KEY` secret
  that was masking as an org secret but was actually invalid — fixed via a
  repo-level secret override).
- This dev sandbox has no network egress to `registration.bogazici.edu.tr` — any
  test/CLI path that tries a live portal call (e.g. term auto-discovery with no
  `--term` given) will fail here with a connection error. Not a code bug; don't
  chase it as one. CI (GitHub Actions) does have egress.
- Local dev sessions for this project sometimes run directly ON a production swarm
  node (this one runs on WorkHorse, the node hosting the `backend` service) — `ssh
  -i ~/.ssh/mac root@10.34.0.4` reaches the swarm manager (HakimBey) for
  `docker service` commands, which fail with "not a swarm manager" run locally on
  a worker node.
