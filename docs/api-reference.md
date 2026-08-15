# REST API Reference

boun-scrape exposes **two** API surfaces from the same FastAPI application (`boun_scrape.api.app:create_app`):

- **`/api/v1/*`** — the typed, documented surface (`courses`, `quota`, `feeds`, `scraper` routers). Response models are pydantic DTOs and appear in the OpenAPI schema at `/docs`.
- **`/api/*`** — a legacy compatibility router (`routes/legacy.py`) that the shipped React frontend actually calls. It predates the `/api/v1` surface and is kept for the existing dashboard; new integrations should prefer `/api/v1/*`.

Both are mounted by the same `create_app()` call — there's no separate legacy server.

Interactive OpenAPI docs are available at `GET /docs` (and schema at `GET /openapi.json`) whenever the server is running.

---

## Authentication

Auth is only defined on the legacy router: `POST /api/auth/login`. There is no `/api/v1/auth/*` — the `/api/v1/*` routers that require auth (`scraper`, `quota`, mutating `feeds` endpoints) validate the same Bearer token via `Depends(get_current_user)`.

### `POST /api/auth/login`
Rate-limited to 5 requests per 60 seconds per client IP.

- **Content-Type**: `application/x-www-form-urlencoded`
- **Body**: `username`, `password` (OAuth2 password grant form fields)
- **200 OK**:
  ```json
  { "access_token": "<header>.<payload>.<signature>", "token_type": "bearer" }
  ```
  The token is a hand-rolled HS256 JWT (see `api/auth.py`) — structurally a standard JWT, but produced without a third-party JWT library. Default expiry: 1 day.
- **401 Unauthorized**: `{ "detail": "Incorrect username or password" }`

### `GET /api/auth/me`
Requires `Authorization: Bearer <token>`.
- **200 OK**: `{ "username": "admin" }`

All other endpoints below that are marked **Auth required** expect the same `Authorization: Bearer <token>` header.

---

## `/api/v1/*` — Typed API

### Courses (`routes/courses.py`)

#### `GET /api/v1/courses`
No auth required. Query and filter courses with pagination.

Query parameters: `term`, `department`, `course_code`, `instructor`, `day` (`M`/`T`/`W`/`Th`/`F`/`St`/`Su`/`TBA`), `hour`, `room`, `slot_title`, `keyword` (fulltext across code/name/instructor/department), `page` (default 1), `size` (default 50, max 500).

- **200 OK** — `PaginatedResponse[CourseDTO]`:
  ```json
  {
    "items": [
      {
        "id": 102, "term": "2024/2025-1", "department": "CMPE",
        "course_code": "CMPE150", "section": "01", "course_name": "Intro to Computing",
        "instructor": "HALUK OĞUZ KAYA", "credits": 4.0, "ects": 7.0,
        "delivery_method": "Face to Face", "exam_location": "M1100", "exam_date": "2024-11-15 14:00",
        "sl": "N", "required_for": "CMPE, EE, IE", "departments": "ALL",
        "slots": [
          { "id": 401, "course_id": 102, "day": "M", "hour": "2", "room": "M1100", "slot_title": "CMPE150", "instructor": "HALUK OĞUZ KAYA" }
        ],
        "raw_code": "CMPE150.01"
      }
    ],
    "total": 1, "page": 1, "size": 50, "pages": 1
  }
  ```

#### `GET /api/v1/courses/{course_id}`
No auth required. Returns a single `CourseDTO` by primary key, or `404` if not found.

#### `GET /api/v1/departments`
No auth required. Optional `term` query param. Returns `list[DepartmentDTO]`: `{ "code": "CMPE", "name": "...", "bolum": "COMPUTER ENGINEERING", "url": "..." }`.

#### `GET /api/v1/terms`
No auth required. Returns `list[str]` of unique terms.

### Quota (`routes/quota.py`)

Both endpoints are rate-limited (30 requests/60s per IP) and require auth.

#### `GET /api/v1/quota`
Query params: `abbr` (required), `code` (required), `section` (optional), `term` (optional — resolves to latest DB term, or discovers from the portal, if omitted), `bypass_cache` (default `false`).
- **200 OK** — `list[QuotaDTO]`: `{ "department": "...", "status": "...", "quota": "120", "current": "115", "quota_numeric": 120, "current_numeric": 115, "is_consent": false, "is_unlimited": false, "available": 5 }`

#### `POST /api/v1/quota/batch`
Body: `{ "items": [{ "term": "...", "abbr": "...", "code": "...", "section": "..." }], "concurrency": 5, "bypass_cache": false }`
- **200 OK**: `dict[str, list[QuotaDTO]]` keyed by canonical course key (e.g. `"CMPE 150.01"`).

### Feeds (`routes/feeds.py`)

#### `GET /api/v1/feeds/deltas`
No auth required. Query params: `term`, `run_id`, `limit` (default 100, max 1000). Returns `list[DeltaEventDTO]` (see [scraping-pipeline.md](scraping-pipeline.md#4-change-detection-pipelinedeltapy) for `change_type` values).

#### `GET /api/v1/feeds/runs`
No auth required. Query params: `term`, `limit` (default 50, max 500). Returns `list[ScrapeRunDTO]` — run history with status, counts, timestamps.

#### `GET /api/v1/feeds/exports/{term}/{format}`
No auth required. `format` is one of `json`, `csv`, `sqlite`/`db`. Streams the export artifact for the given term, generating it on demand (from persisted courses) if not already present in `Settings.export_dir`. Returns `404` if no courses exist for the term.

### Scraper Control (`routes/scraper.py`)

All endpoints require auth.

#### `POST /api/v1/scraper/trigger`
Body (`ScrapeTriggerRequest`): `{ "term": null, "export": true, "dispatch_webhooks": true, "background": true }`.
- If `background: true` (default): starts the cycle via `scheduler.run_in_background()` and returns immediately: `{ "status": "triggered", "message": "...", "term": null }`.
- If `background: false`: awaits the full cycle and returns a `ScrapeRunDTO`.
- **409 Conflict** if a cycle is already running.

#### `GET /api/v1/scraper/status`
Returns `ScrapeStatusDTO`: `{ "is_running": bool, "is_scraping": bool, "interval_seconds": int, "cron_expression": str|null, "run_count": int, "last_run_time": str|null, "next_run_time": str|null, "last_run_summary": object|null }`. `is_running` reflects whether the interval/cron background loop is active (only true if `boun-scrape daemon` — or code that calls `scheduler.start()` — is running in this process); `is_scraping` reflects whether a cycle is executing right now, regardless of trigger source.

#### `POST /api/v1/scraper/stop`
Stops the background interval/cron loop (does **not** cancel an in-flight scrape cycle). Returns `{ "status": "stopped", "message": "..." }`.

#### `GET /api/v1/scraper/logs`
Query params: `limit` (default 100, max 1000), `level` (minimum level filter). Returns `list[LogEntryDTO]` from the in-memory circular log buffer.

---

## `/api/*` — Legacy Compatibility API

This is the surface the shipped `frontend/` calls (`frontend/src/api/client.js`). Shapes differ slightly from `/api/v1/*` (plain dicts rather than typed DTOs, different field/route names) for backward compatibility with the original dashboard.

### `GET /api/stats`
Auth required.
```json
{ "total_courses": 4250, "total_slots": 12800, "departments": 64, "terms": 8, "last_scraped": "2026-08-14T10:00:00+00:00" }
```

### `GET /api/terms`
Auth required. Returns `list[str]`.

### `GET /api/departments`
Auth required. Returns `list[str]` of department codes.

### `GET /api/departments/all`
Auth required. Returns `[{ "kisaadi": "CMPE", "bolum": "COMPUTER ENGINEERING" }, ...]`.

### `GET /api/courses`
Auth required. Query params: `term`, `department`, `course_code`, `instructor`, `day`, `search` (keyword), `page` (default 1), `limit` (default 50, max 500).
```json
{
  "total": 1, "page": 1, "limit": 50,
  "courses": [
    {
      "id": 102, "term": "2024/2025-1", "department": "CMPE", "course_code": "CMPE150",
      "section": "01", "course_name": "...", "instructor": "...",
      "credits": "4.0", "ects": "7.0", "delivery_method": "...", "exam_location": "...",
      "exam_date": "...", "sl": "N", "required_for": "...", "departments": "ALL",
      "slots": [ { "id": 401, "day": "M", "hour": "2", "room": "M1100", "slot_title": "...", "instructor": "..." } ]
    }
  ]
}
```
Note: `credits`/`ects` are serialized as strings here (unlike the numeric `float` fields on `/api/v1/courses`).

### `GET /api/config` / `POST /api/config`
Auth required.
- `GET`: `{ "has_cookies": bool, "cookies_path": "...", "has_response_html": true, "db_path": "..." }`.
- `POST` body: `{ "cookies": "...", "response_html": null }` — writes `cookies` verbatim to `Settings.cookies_path` if provided. `response_html` is accepted in the request model but not currently persisted anywhere (no seed-HTML file mechanism exists in this codebase).

### `POST /api/scrape/start`
Auth required. Body: `{ "phase": "all", "force_refresh": false }`. `phase` and `force_refresh` are accepted for backward compatibility but ignored — there are no separate phases anymore; this always triggers a full `execute_scrape_cycle()` in the background. Returns `{ "status": "ok", "message": "Scraping cycle initiated in background" }`.

### `POST /api/scrape/stop`
Auth required. Stops the scheduler's background interval/cron loop (same as `/api/v1/scraper/stop`). Returns `{ "status": "ok", "message": "Scraper stopped" }`.

### `GET /api/scrape/status`
Auth required. Coarse-grained status derived from `scheduler.get_status()`:
```json
{ "phase": "scraping" | null, "status": "running" | "idle", "progress": { "total": 100, "current": 50, "percent": 50.0 } }
```
Progress is a fixed 0/50/100 approximation, not a true percentage — there's no per-department progress counter surfaced through this endpoint (the underlying scrape has no fixed "steps" concept the way the old subprocess pipeline did).

### `GET /api/scrape/terms`
Auth required. Alias for `CourseRepository.get_terms()` — returns `list[str]` of terms present in the database (not, as an older version of this API implied, a scan of on-disk response/schedule cache files — there are none).

### `GET /api/scrape/logs`
Auth required. Query param: `clear` (bool). Returns `list[str]` of formatted log lines (`"[HH:MM:SS] [LEVEL] message\n"`) from the in-memory log buffer; clears the buffer if `clear=true`.

### `GET /api/quota/check`
Auth required. Query params: `abbr`, `code`, `section`, `donem` (term). Returns:
```json
[ { "department": "CMPE", "status": "Open", "quota": "120", "current": "115", "available": "5" } ]
```
Note the field name is `donem` here (matching the original portal's query parameter name) vs. `term` on `/api/v1/quota`, and `quota`/`current`/`available` are strings rather than the richer numeric+flag breakdown `/api/v1/quota` provides.

---

## Error Responses

- **400 Bad Request** — raised for `ValueError` (e.g. unsupported export format).
- **401 Unauthorized** — missing/invalid/expired Bearer token.
- **404 Not Found** — resource not found (course ID, export artifact).
- **409 Conflict** — a scrape cycle is already in progress (`ScrapeAlreadyRunningError`).
- **429 Too Many Requests** — rate limit exceeded (login: 5/60s, quota: 30/60s, per client IP).
- **500 Internal Server Error** — unhandled `ScrapeSchedulerError` or other server-side failure.

All error bodies follow FastAPI's default shape: `{ "detail": "..." }`.
