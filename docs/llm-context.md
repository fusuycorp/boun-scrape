# LLM Context Reference & Repo Map

> **Note for AI Coding Assistants & LLMs**: This file is a optimized single-file reference summarizing repository architecture, file maps, environment variables, core code signatures, and developer guidelines for `boun-scrape`. Use this context when reasoning about or modifying code in this codebase.

---

## 1. Core Repository Architecture & Tech Stack

- **Repository**: `boun-scrape` (Boğaziçi University course registration schedule crawler & administrative SPA)
- **Frontend Layer**: React 19 + Vite 8 + Tailwind CSS v4 (HSL glassmorphism design system). Located in `/frontend`.
- **Backend Layer**: FastAPI (Python 3.11) served via Uvicorn. Package manager is `uv` (`pyproject.toml`, `uv.lock`). Located in `/backend`.
- **Database Layer**: SQLite (`/data/schedules.db` or configured via `DB_PATH`).
- **Reverse Proxy**: Nginx Alpine container forwarding `/api/*` to `backend:8000`.

---

## 2. Directory Structure & Key Files Map

```
boun-scrape/
├── docker-compose.yml              # Container orchestration (frontend & backend services)
├── .env.example                    # Env var template (DB_PATH, JWT_SECRET_KEY, ALLOWED_ORIGINS)
│
├── docs/                           # Architectural & LLM Documentation Suite
│   ├── README.md                   # Documentation index
│   ├── architecture.md             # System architecture blueprint & C4 model
│   ├── backend-architecture.md     # FastAPI & python subprocess design
│   ├── frontend-architecture.md    # React 19 SPA & HSL design system
│   ├── scraping-pipeline.md        # 4-Stage ETL scraper specification
│   ├── api-reference.md            # Complete REST API documentation
│   ├── database-schema.md          # SQLite ERD, indexes, & transactional pragmas
│   └── llm-context.md              # THIS FILE: Single-file LLM context map
│
├── backend/                        # Backend Application & Pipeline Scripts
│   ├── Dockerfile                  # Python 3.11 slim image using uv
│   ├── pyproject.toml              # Dependencies (fastapi, uvicorn, requests, bs4, python-jose)
│   ├── scraper.py                  # Stage 1: ASP.NET ViewState term discovery poster
│   ├── parse_responses.py          # Stage 2: Department extraction -> departments_all.json
│   ├── scrape_all_schedules.py     # Stage 3: Multi-threaded schedule downloader (10 workers)
│   ├── parse_schedules_to_db.py    # Stage 4: Multi-process HTML parser -> SQLite transactional ETL
│   └── app/                        # FastAPI Web Application Package
│       ├── main.py                 # App factory, CORS middleware, DB startup hook
│       ├── routes.py               # REST Endpoints (Auth, Stats, Terms, Depts, Courses, Scraper, Quota)
│       ├── database.py             # SQLite connection helper, init_db(), query_courses()
│       ├── auth.py                 # JWT token generation, bcrypt password hashing, get_current_user
│       ├── scraping.py             # ScraperManager singleton (Popen launcher & regex log parser)
│       └── quota.py                # Real-time CORS proxy targeting BOUN quotasearch.asp
│
└── frontend/                       # React 19 Frontend SPA
    ├── Dockerfile                  # Multi-stage build (node:20-slim -> nginx:alpine)
    ├── nginx.conf                  # Nginx proxy config & SPA router fallback
    ├── package.json                # React 19, Vite 8, Tailwind v4, Lucide React
    ├── vite.config.js              # Vite config with /api proxy target to http://localhost:8000
    └── src/
        ├── App.jsx                 # Router setup, Providers (Auth, Toast), ProtectedRoute
        ├── index.css               # HSL color design system tokens & glass panel utilities
        ├── contexts/AuthContext.jsx # JWT session context & token validator
        ├── hooks/useToast.js       # Toast notification hook
        └── components/
            ├── Dashboard.jsx       # Analytics cards & system health flags
            ├── ScraperControl.jsx  # 4-Stage pipeline execution panel & terminal monitor
            ├── CourseData.jsx      # Paginated course database explorer & CSV exporter
            ├── QuotaMonitor.jsx    # Real-time course capacity watchlist & 10s polling monitor
            ├── ConfigManager.jsx   # ASP.NET session cookie & seed file manager
            ├── Login.jsx           # Admin login form
            ├── ConfirmDialog.jsx   # Accessible modal dialog
            └── Sidebar.jsx         # Responsive sidebar & mobile drawer
```

---

## 3. Environment Variables Reference

| Key | Default Value | Description |
|---|---|---|
| `DB_PATH` | `/data/schedules.db` | Path to SQLite database file. |
| `JWT_SECRET_KEY` | Hex secret string | Cryptographic key for signing JWT tokens. |
| `ADMIN_USER` | `admin` | Admin login username. |
| `ADMIN_PASSWORD_HASH` | Bcrypt hash | Hashed password for authentication. |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://localhost` | Permitted origins for FastAPI CORS middleware. |

---

## 4. Key Code Snippets & Interface Conventions

### Backend DB Query Interface (`backend/app/database.py`)
```python
def query_courses(term=None, department=None, search=None, day=None, page=1, limit=50):
    # Returns: {"courses": [...], "total": int, "page": int, "limit": int, "pages": int}
```

### Background Process Singleton (`backend/app/scraping.py`)
```python
class ScraperManager:
    # Singleton process runner
    def start_scraping(self, phase: str, force_refresh: bool = False) -> dict: ...
    def stop_scraping(self) -> bool: ...
    def get_status(self) -> dict: ... # returns {phase, status, progress, current_step, total_steps}
    def get_logs(self) -> list[str]: ...
```

### Unmount-Safe Polling Hook Pattern (React Frontend)
```javascript
const isMountedRef = useRef(true);
useEffect(() => {
  isMountedRef.current = true;
  const poll = async () => {
    const data = await fetchData();
    if (isMountedRef.current) setData(data);
  };
  return () => { isMountedRef.current = false; };
}, []);
```

---

## 5. Development & Testing Commands

### Backend Local Dev (with `uv`)
```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

### Frontend Local Dev (Vite)
```bash
cd frontend
npm run dev
```

### Full Containerized Deployment
```bash
docker compose up -d --build
```
- **Frontend SPA**: `http://localhost:5173` (or port 80 in Docker)
- **API Swagger Docs**: `http://localhost:8000/docs`
