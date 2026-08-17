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
