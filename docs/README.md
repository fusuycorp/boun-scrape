# boun-scrape Documentation

Welcome to the architectural and technical documentation for **boun-scrape** — an asynchronous scraping, change-detection, and REST API service for Boğaziçi University course registration data, with a React admin dashboard on top.

---

## Documentation Index

| File | Description | Target Audience |
| :--- | :--- | :--- |
| [**`architecture.md`**](architecture.md) | System architecture, container diagram, component decomposition, security model, deployment topology. | Architects, lead developers, LLMs |
| [**`backend-architecture.md`**](backend-architecture.md) | Module-by-module breakdown of `src/boun_scrape/` — domain, scraper, storage, pipeline, feeds, scheduler, api, cli. | Backend engineers, API integrators |
| [**`frontend-architecture.md`**](frontend-architecture.md) | React 19 SPA structure, terminal/cyberpunk design system, routes, auth flow, key components. | Frontend engineers |
| [**`scraping-pipeline.md`**](scraping-pipeline.md) | Term/department discovery, schedule parsing, slot tokenization, SHA-256 change detection, live quota proxy. | Data engineers |
| [**`api-reference.md`**](api-reference.md) | Complete REST endpoint reference — both `/api/v1/*` (typed) and legacy `/api/*` (frontend-facing) surfaces. | Integration engineers, API clients |
| [**`database-schema.md`**](database-schema.md) | SQLite table definitions, indexes, PRAGMAs, atomic write path, query patterns. | Database-curious engineers |
| [**`llm-context.md`**](llm-context.md) | Condensed single-file repo map, env vars, and key code signatures for AI coding assistants. | LLMs, AI assistants |

---

## System Overview

```
                        +-----------------------+
                        |   User Web Browser     |
                        +-----------+-----------+
                                    |
                                    | HTTP
                                    v
                        +-----------------------+
                        |     Nginx (Frontend)   |
                        +-----------+-----------+
                                    |
                                    | Reverse proxy /api/*
                                    v
                        +-----------------------+
                        |  FastAPI (Backend)     |
                        |  /api/v1/* + /api/*    |
                        +-----+-----------+-----+
                              |           |
                  Reads/Writes|           | Triggers on demand
                              v           v
                +-----------------+  +-------------------------+
                | SQLite (WAL)    |  | ScrapeScheduler          |
                | /data/schedules.db|  | scrape -> diff -> save   |
                +-----------------+  | -> export -> webhook     |
                                     +------------+-------------+
                                                  |
                                                  | httpx (async)
                                                  v
                                     +-------------------------+
                                     | Boğaziçi University      |
                                     | registration servers     |
                                     +-------------------------+
```

Scraping is triggered on demand (API call or CLI), or on a schedule only if you explicitly run `boun-scrape daemon`. It is **not** automatic in the shipped Docker Compose deployment — see [architecture.md](architecture.md) for details.

---

## Technology Summary

- **Backend**: Python 3.12+, FastAPI, Uvicorn, httpx (async), BeautifulSoup4, bcrypt, hand-rolled JWT, `uv` package manager, SQLite (WAL mode).
- **Frontend**: React 19, Vite 8, Tailwind CSS v4, React Router v7, Lucide Icons.
- **Deployment**: Docker Compose (backend + frontend services), multi-stage Dockerfiles, Nginx Alpine reverse proxy, GitHub Actions CI (test-gated build/push/Dokploy-redeploy).
