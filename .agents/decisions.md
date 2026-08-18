# Architecture Decisions (ADRs)

## Record Format
### [YYYY-MM-DD] ADR-Title
- **Context**: Why was this decision necessary?
- **Decision**: What was chosen?
- **Consequences**: What trade-offs or constraints follow?

---

### [2026-08-15] Remove all hardcoded secret defaults; fail fast outside development
- **Context**: `JWT_SECRET_KEY` and `ADMIN_PASSWORD_HASH` shipped with real,
  working defaults committed to git — the admin hash was literally bcrypt("admin"),
  and both were already leaked via git history.
- **Decision**: Both fields became `str | None = None`. A `model_validator` on
  `Settings` raises at construction time if either is `None` and `environment` is
  not one of {development,dev,test,testing,local}; in dev, ephemeral values are
  generated per-process with a logged warning (dev password is logged in plaintext
  once, on purpose, for local login convenience).
- **Consequences**: Production deployments MUST set both explicitly or the app
  refuses to start (loud failure, not silent misconfiguration). Local/test usage
  needs no config changes. The Dokploy-side rollout of this required a manual
  `compose.env`/`compose.update` push since Dokploy doesn't read this repo's
  `docker-compose.yml` directly (see memory.md gotchas).

### [2026-08-15] bcrypt-only password verification; drop multi-scheme fallback
- **Context**: `verify_password` accepted plaintext-equal, SHA-256, or bcrypt
  interchangeably, plus a hardcoded bypass (`password=="admin"` + hash containing
  `"admin"`/`"default_admin_hash"`).
- **Decision**: Single scheme — `bcrypt.checkpw` only. Everything else removed.
- **Consequences**: Any externally-stored hash that isn't a valid bcrypt hash now
  fails closed instead of silently matching via a weaker/backdoor path.

### [2026-08-17] CI redeploy step: single status-checked call, no format-fallback retry
- **Context**: The original redeploy step (`curl -s -X POST ...` with no `-f`/status
  check) silently no-op'd for an unknown stretch of pushes — CI showed green with
  zero actual Dokploy deployments. A first fix added a REST-then-tRPC-wrapped
  two-attempt retry (copied from a sibling service, `titirek`) reasoning it might be
  a payload-shape issue. Root-caused instead to a stale/invalid `DOKPLOY_API_KEY`
  at the org GitHub-secrets level (confirmed: both attempts returned identical
  401s; a manually-tested key succeeded on the first try with the plain payload).
- **Decision**: Simplified back to a single REST call with an explicit HTTP-status
  check and a loud `exit 1` + `::error::` on failure. Fixed the real problem
  (repo-level `DOKPLOY_API_KEY` secret override) instead of adding fallback
  complexity for a problem class (payload shape) that was never the actual cause.
- **Consequences**: A future genuine "wrong payload shape" failure would need its
  own diagnosis and fix, not a blind retry — this is intentional; retries should be
  added for problems we've evidenced, not speculatively.

### [2026-08-17] Real progress telemetry via existing scrape_term_pipeline callback
- **Context**: The ScraperControl frontend page's EXEC action appeared to return no
  telemetry. Root cause was two bugs: `legacy.py`'s `/scrape/status` read a
  nonexistent `is_cycle_running` key (real key: `is_scraping`) and always reported
  "idle" with hardcoded fake 50%/100% progress; separately, `execute_scrape_cycle`
  had zero `logger.info()` calls anywhere on its happy path, so the log-terminal
  UI (backed by `LogBuffer`) had nothing to display even once "idle" was fixed.
- **Decision**: Fixed the key mismatch; added `ScrapeScheduler._current_progress`
  (populated via `scrape_term_pipeline`'s existing `progress_callback` param — no
  new plumbing needed on the scraper side), exposed through `get_status()`; added
  `logger.info()` at each meaningful step of the cycle plus `logger.exception()` on
  failure.
- **Consequences**: Real per-department progress now flows to the UI instead of a
  fake linear 0/50/100 estimate. Left unaddressed: the 4 "phase" cards on that page
  don't correspond to real distinct pipeline stages (see memory.md) — a separate,
  larger UX decision, not fixed in this pass.

### [2026-08-17] Retire the legacy `/api/*` surface; frontend moves to `/api/v1/*` exclusively
- **Context**: Two parallel API surfaces existed — typed `/api/v1/*` (tested,
  correct DTOs) and a hand-rolled legacy `/api/*` compat layer that the frontend
  actually called exclusively. Auditing the legacy layer against its frontend
  consumers turned up widespread contract drift, most of it silently broken in
  production: `ScraperControl.jsx` read `logsRes.logs` on an endpoint that
  returned a bare array, so the log terminal never rendered anything;
  `QuotaMonitor.jsx` read `res.success`/`res.data` on another bare-array
  endpoint, so quota checks always displayed as failed even on success;
  `Dashboard.jsx` read `stats.total_departments`/`total_terms` while the backend
  sent `departments`/`terms`, so those cards always showed 0; `ConfigManager.jsx`
  read field names (`cookie_loaded`, `cookie_masked`) the backend never sent. The
  "seed HTML / response.html" config feature was accepted end-to-end (model
  field, textarea, status card) but never read by any scraper code path — pure
  dead weight. The v1 surface had no login endpoint and didn't expose
  `current_progress` on scraper status.
- **Decision**: Deleted `api/routes/legacy.py` outright. Extracted `/auth/login`
  and `/auth/me` into a new `api/routes/auth.py` mounted under `/api/v1`. Added
  the pieces v1 was missing: `GET /api/v1/stats`, `GET`/`POST
  /api/v1/scraper/config` (cookie-only — seed HTML dropped, not ported),
  `current_progress` on `ScrapeStatusDTO`, a `clear` param on `/scraper/logs`.
  Rewired every frontend component to the real v1 response shapes and fixed the
  contract-mismatch bugs above in the same pass rather than carrying them
  forward under new URLs.
- **Consequences**: One API surface, one set of DTOs, one place to keep in sync
  with the frontend. Several previously-broken dashboard features (log terminal,
  quota radar, connectivity/stat counts) now actually work. `courses.py` gained
  a `/stats` endpoint with no auth (matches the router's existing public
  convention for `courses`/`departments`/`terms`) — if stats ever need to expose
  something sensitive, that will need revisiting. Follow-up (2026-08-17, same
  day): all remaining docs (`README.md`, `docs/architecture.md`,
  `backend-architecture.md`, `frontend-architecture.md`, `llm-context.md`,
  `scraping-pipeline.md`, `database-schema.md`, `docs/README.md`) rewritten to
  drop the old two-surface framing and diagrams; `frontend/FRONTEND_SPECS.md`
  deleted outright — it was a design-critique/rewrite-proposal doc for the
  pre-2026-08-15-modernization frontend, entirely superseded (its "proposed
  redesign" was the neon/terminal aesthetic the app already has).

### [2026-08-17] Collapse the 4 fake "phase" cards to a single trigger control
- **Context**: Follow-up to the telemetry fix above. The 4 phase cards
  (STAGE_1-4: TERM_DISCOVERY/DEPARTMENT_CATALOG/SCHEDULE_CRAWLER/SQLITE_ETL) named
  legacy subprocess scripts deleted in the modernization rewrite. Every EXEC button
  fired the identical `execute_scrape_cycle()` regardless of which card was
  clicked — `ScrapeStartRequest.phase`/`force_refresh` were accepted by
  `POST /scrape/start` but never read anywhere in `scheduler/runner.py`. User chose
  "simplify to a single trigger control" over "make phases real" (the latter would
  require actual backend support for partial/resumable pipeline stages, which
  doesn't exist — `execute_scrape_cycle` is one atomic operation).
- **Decision**: Replaced the 4-card grid with one card / one EXEC action, described
  honestly as a full cycle (discover term -> crawl -> diff -> persist -> export ->
  webhooks). Also dropped the FORCE_REFRESH checkbox (equally inert — nothing read
  it either) and deleted `ScrapeStartRequest` + the request body from
  `POST /scrape/start` entirely, since nothing sends one anymore.
- **Consequences**: The controller page now accurately reflects backend behavior —
  no more UI implying capability (per-stage execution) that was never real. Any
  future "run just department discovery" feature needs real backend support added
  first, not just a UI card wired to the same generic trigger.

### [2026-08-18] Scoped department replacement in save_courses_and_slots (data-loss fix)
- **Context**: `save_courses_and_slots` deleted ALL of a term's courses before
  re-inserting them each cycle. If a department failed to scrape that run (network
  or captcha error), its previously-good courses were still deleted — permanent data
  loss on a transient failure. `scrape_term_pipeline` now tracks per-department
  success/failure.
- **Decision**: `save_courses_and_slots(term, courses, scraped_departments)`
  deletes+replaces rows only for the departments passed in `scraped_departments`;
  departments absent from that list (failed this run) keep their existing data.
  `None` = unconditional whole-term replace (old behavior; used by seeding and any
  non-pipeline write), `[]` = nothing succeeded, delete nothing.
- **Consequences**: A transient failure on one department no longer destroys its
  data. The term is no longer one atomic snapshot replace — it is a union of
  per-department snapshots that converge as retries succeed. A department that is
  genuinely removed/closed and stops appearing will not be cleaned up until it
  shows up missing in a successful scrape; exact "removed department" semantics
  may later need an explicit tombstone/cleanup path.

### [2026-08-18] Persist discovered departments each cycle (data completeness)
- **Context**: `save_departments` existed but had no callers; the pipeline
  enumerated departments only to drive scraping and discarded them, so
  `GET /api/v1/departments` and `/stats.total_departments` read an empty table.
- **Decision**: `TermScrapeResult` carries the fetched `Department` list;
  `execute_scrape_cycle` calls `save_departments(term, depts)` each run (idempotent
  upsert on `(code, term)`).
- **Consequences**: Department listing/stats are populated from real scrapes and
  renamed departments update in place on the next cycle.

### [2026-08-18] Keep storage<->pipeline imports acyclic at the package boundary
- **Context**: `pipeline/__init__.py` eagerly re-exported `exporter` (which imports
  `storage.repository`) while `storage.repository` imports `pipeline.delta`.
  Importing anything from package `storage` therefore pulled in `pipeline` →
  `exporter` → `storage.repository` while it was partially initialized — an
  import-order-dependent circular import that broke isolated test-file collection
  (it only seemed fine because alphabetical collection happened to init `repository`
  first).
- **Decision**: Package `__init__` files import only acyclic leaf modules.
  `pipeline/__init__` now imports only `delta`; the unused `exporter` re-exports
  (zero consumers) were dropped. Importers must use concrete submodules
  (`boun_scrape.pipeline.exporter`, `boun_scrape.storage.repository`, etc.).
- **Consequences**: Every test file collects and passes in isolation regardless of
  order. Rule: no eager cross-package re-exports in package `__init__`s.

### [2026-08-18] Quota snapshot capture: opt-in, best-effort, single-transaction bulk persist, bounded cache
- **Context**: `capture_quota` fetches a live quota reading per course-section —
  thousands of requests against a rate-limit/reCAPTCHA-sensitive portal. Risks:
  (a) thousands of per-section DB transactions (one fsync/commit each), (b) a quota
  failure could mark the whole run FAILED even though courses were already scraped
  and persisted, (c) the `QuotaService` in-memory cache grew unboundedly in a
  long-lived daemon.
- **Decision**: Quota capture is opt-in (`--capture-quota` / `capture_quota` flag).
  All of a term's quota rows are accumulated and persisted in ONE transaction
  (`save_quota_snapshots_bulk`). The capture block is wrapped best-effort
  (try/except), so it can never fail the run or delay completion. The `QuotaService`
  cache is bounded by `max_cache_size` (default 2000, evict-oldest-on-insert).
- **Consequences**: Quota snapshot coverage is not guaranteed on every run
  (best-effort) — consumers polling `/feeds/quota-snapshots` must tolerate gaps.
  The rate-limit sensitivity is precisely why capture is off by default.

### [2026-08-18] boun-archive integration: one-time backfill + current-term delta/quota polling
- **Context**: `boun-archive` (the historical/analytics platform) needs data from
  boun-scrape. A full-history resync is impossible — boun-scrape only ever scrapes
  the live current portal and holds none of boun-archive's 50+ years; boun-archive
  has zero write endpoints and no auth or push-receiver path. Both projects sit in
  the same Dokploy project (`boun-uni`) but no cross-stack Docker network exists
  between any two services in this homelab.
- **Decision**: One-time backfill pull of boun-scrape's existing export, then
  ongoing incremental current-term sync via boun-archive polling
  `GET /api/v1/feeds/deltas` and `GET /api/v1/feeds/quota-snapshots` using
  `after_timestamp` cursors. No push/webhook receiver, no new network wiring —
  boun-scrape's already-public feed API is the transport. A shared-secret
  gate for machine-to-machine polling is deliberately deferred.
- **Consequences**: boun-archive remains the puller. Feed endpoints stay public
  (matching the courses/departments/terms convention), with the deferred auth gate
  a known consideration if feed data ever becomes sensitive. The new quota-snapshots
  endpoint returns ASC order (cursor-friendly for sync), unlike deltas' DESC.
  Remaining work is entirely on the boun-archive side.

### [2026-08-18] Deferred decisions (explicitly documented known trade-offs, not acted on)
- **Snapshot-replace model → course-id churn**: `save_courses_and_slots`
  delete+reinserts all rows each cycle, so AUTOINCREMENT `courses.id` changes every
  run even when nothing changed. This breaks any external reference by course id
  across runs. Chosen transport avoids depending on stable ids today; revisit with
  an upsert-on-`(term,dept,code,section)` model (preserving ids) only if webhook
  consumers or boun-archive need stable ids.
- **reCAPTCHA 2-min TTL vs all-terms mode**: every term in `execute_all_terms_cycle`
  calls `fetch_departments` needing a fresh single-use token; if one term's scrape
  outlasts the ~2 min TTL, remaining terms get captcha-blocked. Current behavior
  fails departments silently; a future fix should hard-stop with an explicit
  "re-solve the token" message rather than burning the remaining terms.
