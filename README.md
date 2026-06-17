# Ultimate BOUN Scraper & Administrative Dashboard

A fullstack application designed to discover, crawl, parse, and monitor course registration schedule database records from Bogazici University (BOUN) servers.

---

## 🏛️ System Architecture

The application is structured into three main layers:

```
                  ┌──────────────────────┐
                  │   Vite React SPA     │
                  │ (Tailwind v4 / HSL)  │
                  └──────────┬───────────┘
                             │ REST API & Live CORS Proxy
                             ▼
                  ┌──────────────────────┐
                  │   FastAPI Service    │
                  │   (Python / Uvicorn) │
                  └────┬────────────┬────┘
                       │            │
         Launches      │            │ Queries / Writes
         Subprocesses  ▼            ▼
   ┌──────────────────────┐   ┌─────────────┐
   │  Scraping Pipeline   │   │ SQLite DB   │
   │  (Stages 1 to 4)     │   │ (Shared)    │
   └──────────────────────┘   └─────────────┘
```

1. **Frontend (Vite / React)**: Implements a glowing glassmorphism theme, dynamic search filters, a stdout console terminal monitor, dynamic metadata parsing, and unmount-safe async handlers.
2. **Backend (FastAPI)**: Coordinates pipeline automation, exposes database statistics, and proxies CORS-restricted quota requests.
3. **Relational DB (SQLite)**: Stores semesters, courses, and slot timetables under a shared location mapped to `DB_PATH`.

---

## 📂 Directory Structure

* `/backend` - FastAPI application source, database schemas, and background pipeline script executables.
* `/frontend` - React web application source, custom design tokens, and components.
* `docker-compose.yml` - Multi-stage deployment coordinates.
* `.env.example` - Security credentials template.

---

## 🚀 Getting Started

### 1. Prerequisites
Install `docker` and `docker-compose` (for containerized deployment), or `uv` and `node` (for local development).

### 2. Configure Environment
Copy `.env.example` to `.env` and configure keys:
```bash
cp .env.example .env
```

### 3. Launching Containers
Start the backend and frontend services via Docker Compose:
```bash
docker compose up -d
```
The services will be active on:
* **Frontend**: `http://localhost:5173` (or port configured in compose)
* **Backend API Documentation**: `http://localhost:8000/docs`

---

## ⚙️ Scraping Pipeline Stages

The backend runner orchestrates background processes sequentially:
* **Stage 1 (`scraper.py`)**: Semesters discovery from index.
* **Stage 2 (`parse_responses.py`)**: Compiles unique departments metadata into `departments_all.json`.
* **Stage 3 (`scrape_all_schedules.py`)**: Crawls individual departments schedules in parallel (polite throttling applied).
* **Stage 4 (`parse_schedules_to_db.py`)**: Normalizes schedules and compiles data into SQLite.

---

## 🛠️ Summary of Refactoring Actions Applied

This project underwent a comprehensive review and rewrite to fix critical path issues, performance bottlenecks, stability risks, and visual alignment limitations:

1. **Synchronized DB Mappings**: Fixed pathing inconsistencies where the compiler script and the FastAPI endpoints target different directories. Both honor the `DB_PATH` environment parameter and fallback to a single root database location.
2. **Optimized DB Compilation**: Wrapped insertions in SQLite transactions (`BEGIN TRANSACTION`), preventing continuous disk I/O blocks, resulting in faster database compile cycles.
3. **Rate-Limiting Protection**: Lowered concurrent workers to 10 and added jitter sleep intervals (`random.uniform`) before scraping queries to prevent reCAPTCHA blocking.
4. **CORS Hardening**: Dynamically toggles credential checks off for wildcard hosts (`*`) and supports custom permitted list rules via `ALLOWED_ORIGINS` to satisfy modern browser CORS policies.
5. **Modernized Frontend**:
   * Removed hardcoded metadata dropdowns in favor of dynamic API fetches from `/api/departments/all`.
   * Replaced browser data URIs with `Blob` downloads for CSV exports.
   * Locked async states inside unmount-safe React hooks (`isMountedRef`) to prevent memory leaks.
   * Standardized backend dependencies mapping to `uv` with a local `uv.lock`.
