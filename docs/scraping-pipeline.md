# Scraping Pipeline & Change Detection Specification

This document details how boun-scrape discovers terms and departments, scrapes and parses course schedules, detects changes, and proxies live quota lookups. All of this runs as native `asyncio` coroutines within a single process — there is no multi-stage subprocess pipeline and no on-disk intermediate HTML/JSON staging files.

---

## 1. Pipeline Flow

```
ScrapeScheduler.execute_scrape_cycle(term)
         |
         v
   discover_terms()  (only if term not given and no default_term configured)
   GET /buis/General/schedule.aspx?p=semester  ->  parse <select id=*ddlSemester*> options
         |
         v
   fetch_departments(term)
   GET  /buis/General/schedule.aspx?p=semester           (obtain __VIEWSTATE / __EVENTVALIDATION)
   POST /buis/General/schedule.aspx?p=semester            (submit ddlSemester=<term>)
   -> parse <a href="/scripts/sch.asp?kisaadi=...&bolum=...">  ->  list[Department]
         |
         v
   scrape_term_pipeline(client, term)
   asyncio.Semaphore(max_concurrency) bounds concurrent department fetches
         |
         +--> fetch_department_schedule(client, term, dept)  [one per department, concurrently]
         |         GET /scripts/sch.asp?donem=<term>&kisaadi=<dept>&bolum=<dept_name>
         |         -> parse_schedules_from_html()  ->  list[Course] (with nested CourseSlot rows)
         v
   aggregated list[Course] across all departments
         |
         v
   compute_deltas(previous_courses, current_courses)   (SHA-256 content hash diff)
         |
         v
   CourseRepository.save_courses_and_slots(term, courses)   (atomic replace, one transaction)
   CourseRepository.save_deltas(deltas, run_id)
         |
         +--> generate_all_exports(term, courses, deltas)   (if export=True: JSON, CSV, SQLite)
         +--> WebhookDispatcher.dispatch_deltas() / dispatch_run_summary()   (if dispatch_webhooks=True)
```

Entry points that trigger this flow:
- CLI: `boun-scrape scrape [--term ...] [--no-export] [--no-webhooks]` (one-off), `boun-scrape daemon [--interval N | --cron "expr"]` (repeats the same cycle on a schedule).
- API: `POST /api/v1/scraper/trigger`.

Nothing runs this automatically. The shipped `docker-compose.yml` backend service only serves the API; the scheduler's background loop is only started by explicitly running `boun-scrape daemon`.

---

## 2. Term & Department Discovery (`scraper/flow.py`, `scraper/parser.py`)

- **Target portal**: `registration.bogazici.edu.tr`, an ASP.NET Web Forms site. `SCHEDULE_SEMESTER_URL = "/buis/General/schedule.aspx?p=semester"`.
- **ViewState handling**: `parser.extract_viewstate_and_semesters(html)` parses the `__VIEWSTATE`, `__VIEWSTATEGENERATOR`, and `__EVENTVALIDATION` hidden `<input>` fields (by `id` or `name`) required for any subsequent form POST, plus the list of semester option values from the `<select id="*ddlSemester*">` dropdown.
- **Department discovery**: `fetch_departments(client, term)` first GETs the semester page for fresh ViewState tokens, then POSTs `{__VIEWSTATE, __VIEWSTATEGENERATOR, __EVENTVALIDATION, ctl00$cphMainContent$ddlSemester: term, ctl00$cphMainContent$btnSearch: "Go"}`. `parser.parse_departments_from_html` scans all `<a href="/scripts/sch.asp?...">` links in the response for `kisaadi` (department code) and `bolum` (full department name) query parameters, deduplicating by `(kisaadi, bolum)`.

---

## 3. Schedule Fetching & Parsing (`scraper/parser.py`, `scraper/slot_tokenizer.py`)

- **Target endpoint**: `GET /scripts/sch.asp?donem=<term>&kisaadi=<dept_code>&bolum=<dept_name>`.
- **Concurrency**: `scrape_term_pipeline` bounds concurrent department requests with `asyncio.Semaphore(concurrency)` (default 10, from `Settings.max_concurrency`). Failed department fetches are caught individually (`asyncio.gather(..., return_exceptions=True)`) and logged as a warning without aborting the whole cycle.
- **Row parsing** (`parse_schedules_from_html`): iterates `<tr class="schtd">` / `<tr class="schtd2">` rows. A row with a non-empty first cell (`code_sec`, e.g. `CMPE150.01`) starts a new `Course`; a row with an empty first cell is a **continuation row** (lab/problem-session/tutorial slot) and its parsed slots are appended to the previously-started course.
- **Slot tokenization** (`slot_tokenizer.py`):
  - `parse_days`: two-character lookahead over the day string to correctly split multi-letter day codes (`Th`, `St`, `Su`) from single-letter ones (`M`, `T`, `W`, `F`), or returns `["TBA"]`.
  - `parse_hours`: solves concatenated period digit strings algebraically — e.g. `"8910"` for 3 slots → `["8", "9", "10"]`. Two-digit periods (10–14) always trail single-digit periods in the source data, so the algorithm takes the leading single-digit periods first, then chunks the remainder into two-digit periods (a naive greedy left-to-right scan misparses cases like `"110"` for 2 slots).
  - `parse_rooms`: splits on `|`/newlines when present, replicates a single room across all slots when only one room is given for a multi-slot course, and pads missing rooms with empty strings.
- **Numeric fields**: credits and ECTS are parsed with `_parse_float`, tolerating comma decimal separators and falling back to `0.0` on parse failure.

---

## 4. Change Detection (`pipeline/delta.py`)

Every scrape cycle diffs the freshly scraped courses for a term against what's currently persisted for that term, **before** persisting the new data:

1. **Content hash**: `compute_course_hash(course)` serializes a course (and its slots, sorted deterministically) to canonical JSON (`sort_keys=True`) and SHA-256 hashes it. Identical courses hash identically regardless of HTML row ordering.
2. **Added / Removed**: courses keyed by `(department, course_code, section)` present only in the new set are `ADDED`; present only in the old set are `REMOVED`.
3. **Modified courses** (same key, different hash) are further classified:
   - `INSTRUCTOR_CHANGED` if `instructor` differs.
   - `ROOM_CHANGED` if the sorted room list differs.
   - `SLOTS_CHANGED` if the sorted `(day, hour, slot_title)` tuples differ.
   - `MODIFIED` if any other tracked metadata field differs (`course_name`, `credits`, `ects`, `delivery_method`, `exam_location`, `exam_date`, `sl`, `required_for`, `departments`), or as a catch-all if the hash changed but none of the above specific checks fired.
   - A single course can emit multiple delta events in one cycle (e.g. both `INSTRUCTOR_CHANGED` and `ROOM_CHANGED`).
4. Each `CourseDeltaEvent` carries `old_value`/`new_value` dicts and a human-readable `details` string, and is persisted to `course_deltas` (see [database-schema.md](database-schema.md)) tagged with the triggering `run_id`.

---

## 5. Live Quota Lookup (`scraper/quota.py`)

Independent of the bulk scrape cycle — queried on demand.

```
[Client] --> GET /api/v1/quota?abbr=CMPE&code=150&section=01&term=2024/2025-1
                     |
                     v
        QuotaService.fetch_quota()  -- checks in-memory TTL cache (default 30s) first
                     |  (cache miss / bypass_cache=True)
                     v
        GET https://registration.boun.edu.tr/scripts/quotasearch.asp?donem=...&abbr=...&code=...&section=...
                     |
                     v
        parse_quota_from_html()  -- scans <tr class="schtd"|"schtd2"> rows across all <table> elements
                     |
                     v
        list[QuotaRecord]  ->  QuotaDTO JSON response
```

`QuotaRecord` fields: `department`, `status` (raw text), `quota`, `current` (raw text), `quota_numeric`/`current_numeric` (parsed ints where numeric), `is_consent`, `is_unlimited`, `available` (computed as `quota_numeric - current_numeric` only when neither consent nor unlimited). `QuotaService.fetch_batch_quotas` runs multiple lookups concurrently under an `asyncio.Semaphore`.

---

## 6. Resilience & Politeness (`scraper/client.py`)

- **Encoding**: every response is force-decoded as `windows-1254` (the registration portal's native encoding for Turkish characters) via `response.encoding = "windows-1254"`.
- **Jitter**: a random delay between `Settings.min_jitter` and `Settings.max_jitter` (default 0.05–0.2s) is applied before every GET/POST.
- **Retry**: up to 3 attempts per request, with exponential backoff (`0.5 * 2^(attempt-1)` seconds plus small random jitter) on `httpx.TransportError`, `httpx.TimeoutException`, and 5xx responses. 4xx responses are not retried and raise immediately.
- **reCAPTCHA detection**: every response body is checked for the marker string `"You could not pass the reCAPTCHA check"`; if found, `RecaptchaBlockedError` is raised immediately (not retried), signalling that the session cookies need refreshing (`cookies.txt` / `Settings.cookies_path`).
- **Cookies**: `parse_cookie_text`/`parse_cookie_file` accept Netscape cookie-file format, semicolon-separated `Cookie:` header format, or plain `key=value` lines.

---

## 7. Export Artifacts (`pipeline/exporter.py`)

When `export=True` (the default), `generate_all_exports(term, courses, deltas, output_dir)` writes, per term, into `Settings.export_dir` (default `exports/`):
- `courses_<safe_term>.json` — full course+slot list as JSON.
- `courses_<safe_term>.csv` — one row per course-slot (courses with no slots get one blank-slot row), UTF-8 BOM for Excel compatibility with Turkish characters.
- `courses_<safe_term>.db` — a standalone SQLite database containing just that term's courses/slots (WAL-checkpointed and truncated before delivery, so no dangling `-wal`/`-shm` sidecar files).
- `deltas_<safe_term>.json` — the delta events from that cycle, if any were passed in.

All writes are atomic: content is written to a temp file in the same directory (guaranteeing same-filesystem `os.replace`), then atomically renamed over the target path — a reader downloading via `GET /api/v1/feeds/exports/{term}/{format}` never observes a partially-written file.
