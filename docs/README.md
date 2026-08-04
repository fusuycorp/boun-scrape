# BOUN Scraper & Administrative Dashboard Documentation

Welcome to the architectural and technical documentation for the **BOUN Scraper & Administrative Dashboard** project. This documentation suite provides comprehensive architectural blueprints, component specifications, database schemas, API references, scraping pipeline details, and an LLM context reference for AI-assisted development.

---

## 📚 Documentation Index

| File | Description | Target Audience |
| :--- | :--- | :--- |
| 🏗️ [**`architecture.md`**](file:///home/devhax/projects/fusuyfusuy/boun-scrape/docs/architecture.md) | High-level system architecture, C4 container model, component interactions, security model, and infrastructure setup. | Architects, Lead Developers, LLMs |
| ⚡ [**`backend-architecture.md`**](file:///home/devhax/projects/fusuyfusuy/boun-scrape/docs/backend-architecture.md) | Backend FastAPI service structure, database query layer, authentication, process management, and background tasks. | Backend Engineers, API Integrators |
| 🎨 [**`frontend-architecture.md`**](file:///home/devhax/projects/fusuyfusuy/boun-scrape/docs/frontend-architecture.md) | Frontend React SPA architecture, Vite setup, HSL glassmorphism design system, state management, routes, and UI components. | Frontend Engineers, UI/UX Designers |
| 🕷️ [**`scraping-pipeline.md`**](file:///home/devhax/projects/fusuyfusuy/boun-scrape/docs/scraping-pipeline.md) | In-depth breakdown of the 4-stage automated scraping pipeline, ASP.NET ViewState handling, concurrency controls, and SQLite compilation. | Data Engineers, Automation Specialists |
| 🔌 [**`api-reference.md`**](file:///home/devhax/projects/fusuyfusuy/boun-scrape/docs/api-reference.md) | Complete OpenAPI/REST endpoint specification, request/response formats, authentication, and error codes. | Integration Engineers, API Clients |
| 🗄️ [**`database-schema.md`**](file:///home/devhax/projects/fusuyfusuy/boun-scrape/docs/database-schema.md) | Entity-relationship diagrams, SQLite table definitions (`courses`, `course_slots`), indexes, transaction handling, and performance tuning. | Database Administrators, Data Analysts |
| 🤖 [**`llm-context.md`**](file:///home/devhax/projects/fusuyfusuy/boun-scrape/docs/llm-context.md) | Concise single-file codebase context, repository map, code conventions, environment configuration, and quick reference for AI agents. | LLMs, AI Assistants |

---

## 🏛️ System Overview At A Glance

```
                                  +-----------------------+
                                  |   User Web Browser    |
                                  +-----------+-----------+
                                              |
                                              | HTTP / REST (Port 80)
                                              v
                                  +-----------------------+
                                  |     Nginx Proxy       |
                                  | (Frontend Container)  |
                                  +-----------+-----------+
                                              |
                                              | Reverse Proxy /api/*
                                              v
                                  +-----------------------+
                                  |   FastAPI Service     |
                                  | (Backend Container)   |
                                  +-----+-----------+-----+
                                        |           |
                     Spawns Process Pool|           | SQLite Queries
                                        v           v
                    +-----------------------+   +-------------------+
                    | 4-Stage Scraping Exec |   |   SQLite Database |
                    | (Python Subprocesses) |   | (/data/schedules.db)
                    +-----------+-----------+   +-------------------+
                                |
                                | HTTP Crawling & Quota Proxying
                                v
                    +-----------------------+
                    | Boğaziçi University   |
                    | (BOUN Web Servers)    |
                    +-----------------------+
```

---

## 🛠️ Quick Technology Summary

* **Frontend**: React 19, Vite 8, Tailwind CSS v4, Lucide Icons, React Router v7
* **Backend**: Python 3.11, FastAPI, Uvicorn, BeautifulSoup4, Requests, Python-JOSE, Passlib (bcrypt), UV Package Manager
* **Database**: SQLite3 with transactional batch compilation and indexed search queries
* **Deployment**: Docker Compose, Multi-stage Dockerfiles, Nginx Alpine reverse proxy
