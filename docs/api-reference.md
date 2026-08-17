# REST API Reference

boun-scrape exposes a single typed API surface from the FastAPI application (`boun_scrape.api.app:create_app`), mounted entirely under `/api/v1/*` (`auth`, `courses`, `quota`, `feeds`, `scraper` routers). Response models are pydantic DTOs and appear in the OpenAPI schema at `/docs`.

Interactive OpenAPI docs are available at `GET /docs` (and schema at `GET /openapi.json`) whenever the server is running.

---

## Authentication

### `POST /api/v1/auth/login`
Rate-limited to 5 requests per 60 seconds per client IP.

- **Content-Type**: `application/x-www-form-urlencoded`
- **Body**: `username`, `password` (OAuth2 password grant form fields)
- **200 OK**:
  ```json
  { "access_token": "<header>.<payload>.<signature>", "token_type": "bearer" }
  ```
  The token is a hand-rolled HS256 JWT (see `api/auth.py`) — structurally a standard JWT, but produced without a third-party JWT library. Default expiry: 1 day.
- **401 Unauthorized**: `{ "detail": "Incorrect username or password" }`

### `GET /api/v1/auth/me`
Requires `Authorization: Bearer <token>`.
- **200 OK**: `{ "username": "admin" }`

All other endpoints below that are marked **Auth required** expect the same `Authorization: Bearer <token>` header.

---

## Courses (`routes/courses.py`)

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

#### `GET /api/v1/stats`
No auth required. Aggregate database counts:
```json
{ "total_courses": 4250, "total_slots": 12800, "total_departments": 64, "total_terms": 8, "last_scraped": "2026-08-14T10:00:00+00:00" }
```

## Quota (`routes/quota.py`)

Both endpoints are rate-limited (30 requests/60s per IP) and require auth.

#### `GET /api/v1/quota`
Query params: `abbr` (required), `code` (required), `section` (optional), `term` (optional — resolves to latest DB term, or discovers from the portal, if omitted), `bypass_cache` (default `false`).
- **200 OK** — `list[QuotaDTO]`: `{ "department": "...", "status": "...", "quota": "120", "current": "115", "quota_numeric": 120, "current_numeric": 115, "is_consent": false, "is_unlimited": false, "available": 5 }`

#### `POST /api/v1/quota/batch`
Body: `{ "items": [{ "term": "...", "abbr": "...", "code": "...", "section": "..." }], "concurrency": 5, "bypass_cache": false }`
- **200 OK**: `dict[str, list[QuotaDTO]]` keyed by canonical course key (e.g. `"CMPE 150.01"`).

## Feeds (`routes/feeds.py`)

#### `GET /api/v1/feeds/deltas`
No auth required. Query params: `term`, `run_id`, `limit` (default 100, max 1000). Returns `list[DeltaEventDTO]` (see [scraping-pipeline.md](scraping-pipeline.md#4-change-detection-pipelinedeltapy) for `change_type` values).

#### `GET /api/v1/feeds/runs`
No auth required. Query params: `term`, `limit` (default 50, max 500). Returns `list[ScrapeRunDTO]` — run history with status, counts, timestamps.

#### `GET /api/v1/feeds/exports/{term}/{format}`
No auth required. `format` is one of `json`, `csv`, `sqlite`/`db`. Streams the export artifact for the given term, generating it on demand (from persisted courses) if not already present in `Settings.export_dir`. Returns `404` if no courses exist for the term.

## Scraper Control (`routes/scraper.py`)

All endpoints require auth.

#### `POST /api/v1/scraper/trigger`
Body (`ScrapeTriggerRequest`): `{ "term": null, "export": true, "dispatch_webhooks": true, "background": true }`.
- If `background: true` (default): starts the cycle via `scheduler.run_in_background()` and returns immediately: `{ "status": "triggered", "message": "...", "term": null }`.
- If `background: false`: awaits the full cycle and returns a `ScrapeRunDTO`.
- **409 Conflict** if a cycle is already running.

#### `GET /api/v1/scraper/status`
Returns `ScrapeStatusDTO`: `{ "is_running": bool, "is_scraping": bool, "interval_seconds": int, "cron_expression": str|null, "run_count": int, "last_run_time": str|null, "next_run_time": str|null, "last_run_summary": object|null, "current_progress": object|null }`. `is_running` reflects whether the interval/cron background loop is active (only true if `boun-scrape daemon` — or code that calls `scheduler.start()` — is running in this process); `is_scraping` reflects whether a cycle is executing right now, regardless of trigger source. `current_progress` is `{ "completed": int, "total": int, "department": "CMPE" }` while a cycle is running (populated via `scrape_term_pipeline`'s progress callback), or `null` when idle.

#### `POST /api/v1/scraper/stop`
Stops the background interval/cron loop (does **not** cancel an in-flight scrape cycle). Returns `{ "status": "stopped", "message": "..." }`.

#### `GET /api/v1/scraper/logs`
Query params: `limit` (default 100, max 1000), `level` (minimum level filter), `clear` (bool, default `false` — clears the buffer after reading). Returns `list[LogEntryDTO]` (`{ "timestamp": "...", "level": "INFO", "name": "...", "message": "..." }`) from the in-memory circular log buffer.

#### `GET /api/v1/scraper/config`
Reports whether a session cookie file is currently mounted (never returns the cookie value itself): `{ "cookie_loaded": bool }`.

#### `POST /api/v1/scraper/config`
Body: `{ "cookies": "ASP.NET_SessionId=..." }`. Overwrites `Settings.cookies_path` with the given string. Returns `{ "status": "ok", "message": "Cookie configuration updated." }`.

---

## Error Responses

- **400 Bad Request** — raised for `ValueError` (e.g. unsupported export format).
- **401 Unauthorized** — missing/invalid/expired Bearer token.
- **404 Not Found** — resource not found (course ID, export artifact).
- **409 Conflict** — a scrape cycle is already in progress (`ScrapeAlreadyRunningError`).
- **429 Too Many Requests** — rate limit exceeded (login: 5/60s, quota: 30/60s, per client IP).
- **500 Internal Server Error** — unhandled `ScrapeSchedulerError` or other server-side failure.

All error bodies follow FastAPI's default shape: `{ "detail": "..." }`.
