# System Architecture Blueprint

This document details the software architecture, design principles, deployment topology, and security model of the **BOUN Scraper & Administrative Dashboard**.

---

## 1. Architectural Overview & System Context

The application provides automated web discovery, parallel crawling, HTML parsing, relational data compilation, interactive exploration, and real-time quota monitoring for Boğaziçi University (BOUN) course registration schedules.

### Key Architectural Characteristics
- **Decoupled Architecture**: Clear boundary between single-page frontend application (React 19) and backend API service (FastAPI).
- **Embedded Persistent Datastore**: Single-file relational database (SQLite) for low latency, zero-configuration persistence, and portability.
- **Asynchronous & Multi-process ETL Pipeline**: Scraping operations run out-of-band via background subprocesses managed by a thread-safe singleton manager (`ScraperManager`).
- **Live Proxy Layer**: Bypass CORS limitations on third-party BOUN servers by proxying client real-time quota lookups through FastAPI.
- **Containerized Orchestration**: Fully containerized environment using Docker Compose with Nginx as a reverse proxy for single-origin routing.

---

## 2. Container Diagram (C4 Model)

```
+-----------------------------------------------------------------------------------+
|                                  USER BROWSER                                     |
|  - React 19 SPA (Vite)                                                            |
|  - Modern HSL Dark Glassmorphic Design System                                     |
|  - Live terminal streaming & debounced dataset filtering                          |
+----------------------------------------+------------------------------------------+
                                         |
                                         | HTTP / REST Requests (Port 80)
                                         v
+-----------------------------------------------------------------------------------+
|                            FRONTEND CONTAINER (Nginx)                             |
|  - Serves compiled static JS/CSS assets                                           |
|  - Reverse-proxies /api/* to http://backend:8000/api                              |
+----------------------------------------+------------------------------------------+
                                         |
                                         | Internal Docker Bridge Network
                                         v
+-----------------------------------------------------------------------------------+
|                            BACKEND CONTAINER (FastAPI)                            |
|  - JWT OAuth2 Authentication & Password Verification                             |
|  - REST Data Endpoints (/api/courses, /api/stats, /api/terms, /api/departments)   |
|  - Real-time CORS Quota Proxy (/api/quota/check)                                  |
|  - Process Controller & Subprocess Log Streamer (ScraperManager)                  |
+-------------------+---------------------------------------+-----------------------+
                    |                                       |
  Reads/Writes Data |                                       | Spawns & Monitors
                    v                                       v
+-----------------------+               +-------------------------------------------+
| PERSISTENT VOLUME     |               | SCRAPING PIPELINE SUBPROCESSES            |
| - SQLite DB           |               | - Stage 1: scraper.py (Term discovery)    |
|   (/data/schedules.db)|               | - Stage 2: parse_responses.py (Depts)     |
+-----------------------+               | - Stage 3: scrape_all_schedules.py (Pool) |
                                        | - Stage 4: parse_schedules_to_db.py (DB)  |
                                        +-------------------+-----------------------+
                                                            |
                                                            | HTTP Crawling (Win-1254)
                                                            v
                                        +-------------------------------------------+
                                        | BOĞAZİÇİ UNIVERSITY SERVERS               |
                                        | registration.bogazici.edu.tr              |
                                        +-------------------------------------------+
```

---

## 3. Top-Level Component Decomposition

### 3.1 Frontend (`/frontend`)
- **Framework**: React 19 + Vite 8.
- **Routing**: React Router DOM v7 client-side SPA navigation with `ProtectedRoute` wrappers.
- **State Management**: React Context (`AuthContext`, `ToastContext`), local component states, and custom hooks (`useToast`).
- **Styling**: Tailwind CSS v4 + custom HSL design system (`index.css`) with neon ambient glows, glassmorphism, dynamic animations, and dark mode.
- **Key Modules**:
  - `Dashboard.jsx`: Overall database statistics and health monitors.
  - `ScraperControl.jsx`: Pipeline controller with live stdout terminal streaming.
  - `CourseData.jsx`: Searchable course grid with multi-filter debounced search and CSV export.
  - `QuotaMonitor.jsx`: Real-time watchlist and 10-second polling monitor for course capacity.
  - `ConfigManager.jsx`: Session cookie (`ASP.NET_SessionId`) and seed markup manager.

### 3.2 Backend (`/backend`)
- **Framework**: Python 3.11 + FastAPI + Uvicorn.
- **Dependency Management**: `uv` package manager (`pyproject.toml`, `uv.lock`).
- **Application Structure (`backend/app/`)**:
  - `main.py`: FastAPI app initialization, CORS middleware, and DB startup hook.
  - `routes.py`: API routes for Auth, Stats, Terms, Departments, Courses, Config, Scraping, and Quota.
  - `database.py`: SQLite connection factory, schema initialization, and parameterized search queries.
  - `auth.py`: JWT token creation, bcrypt password hashing, and OAuth2 bearer dependency.
  - `scraping.py`: Singleton process manager (`ScraperManager`) handling asynchronous script execution and stdout regex log parsing.
  - `quota.py`: Live scraper and HTML parser targeting BOUN quota scripts (`quotasearch.asp`).

### 3.3 Scraping Pipeline (`/backend/*.py`)
- **Stage 1 (`scraper.py`)**: Submits ASP.NET ViewState form requests to discover and download term index pages.
- **Stage 2 (`parse_responses.py`)**: Parses department links (`kisaadi`, `bolum`) into a canonical JSON catalog (`departments_all.json`).
- **Stage 3 (`scrape_all_schedules.py`)**: Multi-threaded downloader (`ThreadPoolExecutor` with 10 workers) fetching raw department HTML files.
- **Stage 4 (`parse_schedules_to_db.py`)**: Multi-process parser (`ProcessPoolExecutor`) converting HTML tables into relational SQLite records using batch transactions.

---

## 4. Security Architecture & Threat Model

1. **Authentication & Authorization**:
   - Administrative endpoints are protected via JWT tokens (HS256 signature, 24-hour expiration).
   - Passwords stored as salted `bcrypt` hashes. Authenticated state validated via `OAuth2PasswordBearer`.
2. **CORS Policy**:
   - FastAPI CORS middleware dynamically checks request origin against `ALLOWED_ORIGINS` environment list.
   - Disables `allow_credentials` if wildcard `*` is specified, preventing browser security violations.
3. **Nginx Reverse Proxy Security**:
   - Single-origin architecture hides FastAPI backend inside internal Docker bridge network (`backend:8000`).
   - Standard headers passed: `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`.
4. **Scraper Politeness & Rate-Limiting**:
   - Thread pool concurrency capped at 10 workers.
   - Jitter delays (`0.1s - 0.4s`) inserted before each HTTP request to reduce server stress and avoid reCAPTCHA triggers.

---

## 5. Persistence Strategy & Performance Optimization

- **Database**: Single SQLite database file mapped to container environment path `DB_PATH` (default: `/data/schedules.db`).
- **ETL Performance**:
  - `PRAGMA synchronous = OFF` and `PRAGMA journal_mode = MEMORY` applied during bulk insertion.
  - Single `BEGIN TRANSACTION` block wraps thousands of course and slot insertions, converting multi-minute I/O operations into sub-second writes.
- **Database Indexing**:
  - `idx_courses_term_dept` on `(term, department)`
  - `idx_courses_code` on `(course_code)`
  - `idx_slots_course_id` on `(course_id)`
  - `idx_slots_day_hour` on `(day, hour)`
