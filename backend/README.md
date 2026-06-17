# Backend API & Scraper Service

FastAPI service and script pipeline for discovery, caching, and parsing registration course databases.

---

## 🛠️ Environment Configuration

Managed via **`uv`**. Lock file coordinates can be found in `uv.lock`.

### Dependencies:
* `fastapi` - API route handlers.
* `beautifulsoup4` - BeautifulSoup parser.
* `requests` - HTTP request loader.
* `python-jose` - JWT token encryption.
* `passlib` - bcrypt password validator.
* `uvicorn` - API runtime server.

### Local Virtual Environment Setup:
Initialize virtualenv and synchronize package versions:
```bash
uv sync
```

---

## 🗄️ Database Schemas

SQLite database holds two normalized relations (`courses` and `course_slots`):

### 1. `courses`
* Holds course metadata rows.
* Columns: `term`, `department`, `course_code`, `section`, `course_name`, `instructor`, `credits`, `ects`, `delivery_method`, `exam_location`, `exam_date`, `sl`, `required_for`, `departments`.

### 2. `course_slots`
* Holds individual hourly schedule meetings linked to `courses`.
* Columns: `course_id` (foreign key), `day`, `hour`, `room`, `slot_title` (e.g. LAB, PS), `instructor`.

---

## ⚙️ Running Scripts Manually

If you prefer to bypass the FastAPI dashboard controls, you can run individual scraping modules using `uv run`:

```bash
# Stage 1: Discovers terms & lists departments
uv run scraper.py

# Stage 2: Deduplicates departments lists
uv run parse_responses.py

# Stage 3: Downloads all schedules HTML files in parallel
uv run scrape_all_schedules.py

# Stage 4: Compiles all downloaded schedules into schedules.db database
uv run parse_schedules_to_db.py
```

---

## 🌐 API Routes Reference

Key REST API endpoints:
* `POST /api/auth/login` - Validates admin credentials and generates bearer JWT token.
* `GET /api/stats` - Retreives database stats.
* `GET /api/terms` - Retrieves unique semesters list from DB.
* `GET /api/departments` - Retrieves list of scraped department keys from DB.
* `GET /api/departments/all` - Retrieves full catalog metadata (`name`, `kisaadi`, `bolum`) from `departments_all.json`.
* `GET /api/courses` - Paginated query explorer supporting term, department, keyword, and meeting day filters.
* `GET /api/quota/check` - Real-time CORS proxy checker hitting the registration portal `/scripts/quotasearch.asp` directly.
* `POST /api/scrape/start` - Launches subprocess background scraping jobs.
* `GET /api/scrape/logs` - Streams scraper process outputs.
