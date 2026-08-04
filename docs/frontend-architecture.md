# Frontend Architecture Specification

This document details the single-page web application architecture, design system, component hierarchy, state management, and API proxy setup in `/home/devhax/projects/fusuyfusuy/boun-scrape/frontend`.

---

## 1. Overview & Framework Stack

The frontend is a responsive, high-performance Single Page Application (SPA) built using **React 19** and **Vite 8**. It features a modern dark-mode HSL design system with glassmorphic cards, glowing neon ambient radial backdrops, and interactive real-time controls.

### Technical Stack
- **Framework**: React `19.2.6`
- **Build Tool**: Vite `8.0.12` + `@vitejs/plugin-react` `6.0.1`
- **Styling**: Tailwind CSS `4.0.0` + custom HSL design tokens (`src/index.css`)
- **Routing**: React Router DOM `7.15.1`
- **Icons**: Lucide React `1.16.0`
- **Package Manager**: Bun / npm (`bun.lock` / `package.json`)
- **Production Web Server**: Nginx Alpine (`nginx.conf`)

---

## 2. Component Hierarchy & File Layout

```
src/
├── main.jsx                  # Entrypoint: React DOM root renderer
├── App.jsx                   # Router setup, global providers (Auth, Toast), ProtectedRoute
├── index.css                 # HSL theme variable declarations & Tailwind utilities
├── App.css                   # Layout overrides & custom scrollbars
├── assets/                   # Static images (hero illustrations, logos)
├── components/               # Page and UI component implementations
│   ├── Sidebar.jsx           # Responsive navigation sidebar & mobile drawer
│   ├── Dashboard.jsx         # System analytics overview dashboard
│   ├── ScraperControl.jsx    # Scraping pipeline controller & log monitor
│   ├── CourseData.jsx        # Searchable course schedule database grid
│   ├── QuotaMonitor.jsx      # Real-time course capacity watchlist
│   ├── ConfigManager.jsx     # ASP.NET session cookie & seed file manager
│   ├── Login.jsx             # Admin authentication form
│   ├── ConfirmDialog.jsx     # Reusable confirmation modal dialog
│   ├── EmptyState.jsx        # Reusable empty data callout
│   └── Toast.jsx             # Toast notification container
├── contexts/
│   └── AuthContext.jsx       # Authentication session provider
└── hooks/
    └── useToast.js           # Custom hook accessor for ToastContext
```

---

## 3. Design System & Styling Architecture (`src/index.css`)

The UI uses a custom **HSL (Hue, Saturation, Lightness)** color design system built on top of Tailwind CSS v4.

### Design Tokens & Color Palette
- **Primary Violet**: `hsl(265, 85%, 65%)`
- **Secondary Pink**: `hsl(325, 85%, 60%)`
- **Background Slate**: `hsl(225, 25%, 8%)`
- **Card Surface**: `hsla(225, 20%, 12%, 0.7)` with `backdrop-filter: blur(16px)`
- **Border Surface**: `hsla(225, 20%, 25%, 0.5)`

### Custom CSS Utilities
- `.glass-panel`: Glassmorphic container with backdrop blur, subtle borders, and soft shadows.
- `.glass-input`: Input fields with dark translucent background, focus glow, and smooth transition effects.
- `.bg-glow-violet` / `.bg-glow-pink`: Radial ambient gradient lights fixed behind cards for neon depth effects.
- `.btn-primary` / `.btn-secondary`: Custom gradient action buttons with scale transform micro-animations on click/hover.

---

## 4. Route Architecture & Navigation Model

Client-side routing is configured in `src/App.jsx` using React Router DOM.

```
/login (Public) --------> [Login.jsx]
                             | (Authenticates & stores JWT in localStorage)
                             v
/ (Protected) -----------> [Dashboard.jsx]      (Analytics & system health)
/scraper (Protected) ----> [ScraperControl.jsx] (Pipeline execution & logs)
/explorer (Protected) ---> [CourseData.jsx]     (Paginated DB search & CSV export)
/quota (Protected) ------> [QuotaMonitor.jsx]   (Live quota watchlist)
/config (Protected) -----> [ConfigManager.jsx]  (Session cookies & seed files)
```

### Route Guard Implementation
`ProtectedRoute` in `App.jsx` inspects `isAuthenticated` from `AuthContext`.
- If `authenticating` is true: Displays `<LoadingScreen />`.
- If `isAuthenticated` is false: Redirects to `/login` preserving the target path via `Location`.

---

## 5. Detailed Component Specifications

### 5.1 `ScraperControl.jsx` (Pipeline Management)
- **State**: `phase`, `status`, `progress`, `logs`, `terms`, `confirmModal`.
- **Pipeline Stage Triggering**: Calls `POST /api/scrape/start` with payload `{ phase, force_refresh }`.
- **Terminal Log Streamer**: Polls `GET /api/scrape/logs` every 1,500ms when a process is active. Rendered in a fixed-height monospace log container with auto-scroll lock.
- **Term Metadata Table**: Displays scraped terms, file counts, and last modified timestamps (`Xm ago`, `Xh ago`).

### 5.2 `CourseData.jsx` (Database Explorer)
- **Multi-filter Search**: Text search input with 250ms debouncing, semester dropdown, department dropdown, and meeting day filter buttons (`M`, `T`, `W`, `Th`, `F`, `St`).
- **Data Rendering**: Responsive sticky header table for desktop; expandable cards for mobile screens.
- **Expanded Course Detail**: Renders credits, ECTS, instructor, exam venue/date, special status (`SL`), target majors, and nested meeting slot timetables.
- **CSV Exporter**: Constructs raw CSV payload in memory and downloads via `Blob` object, inserting UTF-8 BOM (`\uFEFF`) to preserve Turkish character rendering in MS Excel.

### 5.3 `QuotaMonitor.jsx` (Real-Time Watchlist)
- **Watchlist Generator**: Add individual course sections or section ranges (e.g. `CMPE 150` Sec `1` to `5`).
- **Interval Timer**: 10-second automatic polling cycle querying `GET /api/quota/check`.
- **Status Badges**:
  - `badge-success`: Open slots available (`open`).
  - `badge-warning`: Consent required (`consent`).
  - `badge-info`: Unlimited capacity (`unlimited`).
  - `badge-danger`: Class full (`closed`).

### 5.4 `ConfigManager.jsx` (reCAPTCHA Session Config)
- Manages manual session injection for `ASP.NET_SessionId` cookies and raw HTML seed files (`response.html`).
- Displays string validation checks and sticky dirty-state save bar.

---

## 6. Resilience & Unmount Safety

Components featuring polling loops (`ScraperControl.jsx`, `QuotaMonitor.jsx`) enforce unmount safety using React `useRef`:

```javascript
const isMountedRef = useRef(true);

useEffect(() => {
  isMountedRef.current = true;
  const poll = async () => {
    const data = await fetchData();
    if (isMountedRef.current) {
      setData(data);
    }
  };
  return () => {
    isMountedRef.current = false;
  };
}, []);
```
This pattern prevents React state updates on unmounted components and eliminates memory leaks.
