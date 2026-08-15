# Frontend Architecture Specification

This document details the single-page web application in `frontend/` — a React 19 + Vite SPA with an 80s-cyberpunk terminal aesthetic, served by Nginx in production.

---

## 1. Overview & Framework Stack

- **Framework**: React `19.2.6`
- **Build tool**: Vite `8.0.12` + `@vitejs/plugin-react` `6.0.1`
- **Styling**: Tailwind CSS `4.0.0` + a custom terminal design system (`src/index.css`) — dark "void" backgrounds, phosphor-green/amber/pink/cyan neon accents, CRT scanline overlay, JetBrains Mono / Share Tech Mono monospace typography.
- **Routing**: React Router DOM `7.15.1`, client-side.
- **Icons**: Lucide React `1.16.0`.
- **Package manager**: Bun (`bun.lock`) or npm.
- **Production web server**: Nginx Alpine, reverse-proxying `/api` to the backend container.

The frontend talks exclusively to the **legacy** `/api/*` router (see [api-reference.md](api-reference.md)) — it does not use `/api/v1/*` at all. All requests go through a single client module (`src/api/client.js`).

---

## 2. Component Hierarchy & File Layout

```
src/
├── main.jsx                  # Entrypoint: React DOM root renderer
├── App.jsx                   # Router setup, providers (Auth, Toast), ProtectedRoute, status ticker bars
├── index.css                 # Terminal/cyberpunk design tokens & Tailwind utilities
├── App.css                   # Layout overrides
├── assets/                   # Static images
├── api/
│   └── client.js              # Centralized fetch wrapper: apiRequest(), api.{login,getStats,getCourses,...}
├── components/
│   ├── Sidebar.jsx            # Navigation sidebar
│   ├── Dashboard.jsx          # System stats overview (/api/stats)
│   ├── ScraperControl.jsx     # Scrape trigger, status polling, log viewer
│   ├── CourseData.jsx         # Searchable/filterable course grid, CSV export
│   ├── QuotaMonitor.jsx       # Live quota watchlist with interval polling
│   ├── ConfigManager.jsx      # Cookie / scraper config management
│   ├── Login.jsx              # Admin authentication form
│   ├── ConfirmDialog.jsx      # Reusable confirmation modal
│   ├── EmptyState.jsx         # Reusable empty-data callout
│   └── Toast.jsx              # Toast notification provider/container
├── contexts/
│   └── AuthContext.jsx        # AuthProvider: token state, session validation via GET /api/auth/me, login/logout
└── hooks/
    ├── useToast.js             # Toast context accessor hook
    └── useSafeAsync.js         # useMountedRef / useSafeCallback: guards against post-unmount state updates
```

---

## 3. Design System (`src/index.css`)

A dark, monospace, terminal-inspired design system (not the earlier HSL glassmorphism theme):

- **Backgrounds**: `--bg-void: #050508`, `--bg-primary`, `--bg-secondary`, `--bg-tertiary`, `--bg-surface` — layered near-black tones.
- **Neon accents**: `--neon-green: #00ff66`, `--neon-amber: #ffb000`, `--neon-pink: #ff0055`, `--neon-cyan: #00f0ff` (each with a `-dim` variant for backgrounds/borders).
- **Text**: `--text-primary`, `--text-secondary`, `--text-muted`.
- **Typography**: `--font-mono: 'JetBrains Mono', 'Share Tech Mono', 'Courier New', monospace`, loaded via Google Fonts import.
- **CRT overlay**: a fixed, full-viewport `.crt-overlay` div with a repeating linear-gradient scanline pattern and `mix-blend-mode: multiply`, rendered in `App.jsx`'s `MainLayout`.
- **Status ticker bars**: `App.jsx` renders fixed top/bottom bars (`StatusTicker`) with faux system status readouts (`[BOUN://SCRAPER_DAEMON v2.0]`, `[NODE: ISTANBUL_BOUN]`, a live clock, `[HEAP: ...]`, `[VIEWSTATE: BYPASSED]`) as thematic flavor text.

---

## 4. Routing & Auth Guard

Configured in `src/App.jsx`:

```
/login (public)     -> Login.jsx        (posts credentials, stores JWT in localStorage under 'token')
/ (protected)        -> Dashboard.jsx    (stats overview)
/scraper (protected) -> ScraperControl.jsx (trigger scrape, poll status/logs)
/explorer (protected)-> CourseData.jsx   (paginated search + CSV export)
/quota (protected)   -> QuotaMonitor.jsx (live quota watchlist)
/config (protected)  -> ConfigManager.jsx (cookie / config management)
* (protected)        -> redirects to /
```

`ProtectedRoute` (in `App.jsx`) reads `isAuthenticated`/`authenticating` from `AuthContext`: shows a loading indicator while `authenticating`, redirects to `/login` (preserving the origin location in router state) if not authenticated, otherwise renders the child route inside `MainLayout` (sidebar + status bars + CRT overlay).

---

## 5. Auth Flow (`contexts/AuthContext.jsx`, `api/client.js`)

- `AuthProvider` initializes `token` from `localStorage.getItem('token')`. On mount (and whenever `token` changes), it calls `GET /api/auth/me` to validate the session; a failed call clears the token and user state.
- `login(username, password)` posts form-encoded credentials to `POST /api/auth/login`, stores the returned `access_token` in `localStorage`, and re-validates via `/api/auth/me`.
- `api/client.js`'s `apiRequest()` attaches `Authorization: Bearer <token>` to every request automatically, and on a `401` response clears the stored token and redirects to `/login`.
- `isAuthenticated` is derived as `!!user` (i.e. a stored token alone isn't sufficient — the session must have been validated against `/api/auth/me`).

---

## 6. Key Component Behaviors

### `ScraperControl.jsx`
Triggers `POST /api/scrape/start`, polls `GET /api/scrape/status` and `GET /api/scrape/logs` while a cycle is active, and renders buffered log lines in a terminal-style scroll container.

### `CourseData.jsx`
Debounced text search plus term/department/day filters against `GET /api/courses`. Builds a CSV client-side from the fetched rows and downloads it as a `Blob` with a UTF-8 BOM prefix, to preserve Turkish characters when opened in Excel.

### `QuotaMonitor.jsx`
Maintains a client-side watchlist of course sections. When `pollingActive`, runs `pollAllQuotas()` immediately and then on a `setInterval` timer, calling `GET /api/quota/check` for each watched section. Uses `useMountedRef` (from `hooks/useSafeAsync.js`) to guard against setting state after unmount.

### `ConfigManager.jsx`
Reads/writes scraper configuration (currently just session cookies) via `GET`/`POST /api/config`.

### `Dashboard.jsx`
Renders aggregate counts from `GET /api/stats` (`total_courses`, `total_slots`, `departments`, `terms`, `last_scraped`).

---

## 7. Unmount-Safety Pattern

Components with polling loops (`ScraperControl.jsx`, `QuotaMonitor.jsx`) use the shared `useMountedRef` hook rather than duplicating a local `isMountedRef`:

```javascript
import { useMountedRef } from '../hooks/useSafeAsync';

function SomeComponent() {
  const isMountedRef = useMountedRef();

  const poll = async () => {
    const data = await fetchData();
    if (isMountedRef.current) setData(data);
  };
  // ...
}
```

This prevents React state updates on unmounted components (e.g. if a user navigates away from `/scraper` or `/quota` mid-poll).

---

## 8. Deployment

`frontend/Dockerfile` is a multi-stage build (Node build stage → `nginx:alpine` runtime). `frontend/nginx.conf` serves the built static assets, falls back to `index.html` for client-side routing, and reverse-proxies `/api` to `http://backend:8000/api` with standard forwarding headers (`X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`). In `docker-compose.yml`, the frontend container is published on host port `5173` and depends on the `backend` service.
