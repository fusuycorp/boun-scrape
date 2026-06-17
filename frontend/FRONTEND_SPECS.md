# Ultimate BOUN Frontend Specifications & Design Review

This document contains the functional and technical specifications for the Frontend of the Bogazici University Scraper & Dashboard Suite, along with a code review, critique of the current design, and a detailed plan for a complete rewrite.

---

## 1. Functional Specifications

The frontend is a React single-page application (SPA) acting as the administrative dashboard for the scraper. It contains the following modules:

### A. Authentication & Session Security ([Login.jsx](file:///home/devhax/projects/fusuyfusuy/boun-scrape/frontend/src/components/Login.jsx))
* **Username & Password Login**: Direct auth validation utilizing OAuth2 password forms.
* **Session Persistence**: Stores JWT tokens in `localStorage` under `AuthContext`.
* **State Detection**: Includes pre-auth check, automated session timeout validation, and input utilities like Caps Lock warnings.

### B. Scraping Pipeline Controls ([ScraperControl.jsx](file:///home/devhax/projects/fusuyfusuy/boun-scrape/frontend/src/components/ScraperControl.jsx))
* **Multi-Stage Dashboard**: Shows the four pipeline stages (stages 1-4).
* **Live Server Terminal**: Polls `/api/scrape/logs` to display stdout from subprocess runs inside a stylized console component.
* **Auto-Scrolling Terminal**: Automatically scrolls stdout logs down as new logs arrive.
* **Discovered Terms Cache Table**: Shows each academic term, count of scraped files, and last-craped timestamp retrieved via `/api/scrape/terms`.

### C. Course Database Explorer ([CourseData.jsx](file:///home/devhax/projects/fusuyfusuy/boun-scrape/frontend/src/components/CourseData.jsx))
* **Database Explorer Grid**: Displays parsed schedule course records.
* **Live Filtering System**: Users can search by course code, department, days, and search phrases (debounced search input).
* **Client-Side Sorting**: Supports ascending/descending sorting on course code, course name, instructor, and department.
* **Export Utility**: Exports filtered rows to a formatted CSV file.
* **BOUN Link Generator**: Builds links to BOUN’s registration server schedule endpoint `/scripts/sch.asp` using current filter variables.

### D. Quota Monitor ([QuotaMonitor.jsx](file:///home/devhax/projects/fusuyfusuy/boun-scrape/frontend/src/components/QuotaMonitor.jsx))
* **Enrollment Watchlist**: Tracks specific course departments, codes, and sections.
* **Countdown Refresher**: Periodically requests live course quota details directly from the BOUN registration servers bypassing CORS restrictions using the backend CORS proxy.
* **Capacity Analytics**: Visualizes filled capacity vs total capacity in clean progress indicators.

---

## 2. Technical Specifications

- **Framework**: React 19.x with Vite 8.x (bundler).
- **Routing**: React Router DOM (v7).
- **Styling**: Tailwind CSS v4 using `@import "tailwindcss";` in combination with vanilla CSS variables mapped to specific HSL color values.
- **Icon Library**: `lucide-react` (SVG icons).
- **CORS handling**: Requests route through standard relative paths (relying on Vite proxy or container reverse proxy config).

---

## 3. Frontend Code Critique & Architectural Analysis

The current frontend implementation works but suffers from several design smells, anti-patterns, and visual limitations:

### A. Code Layout & Architecture Critique
1. **Hardcoded Metadata (`BOLUM_ARRAY`)**:
   * **Problem**: In [CourseData.jsx](file:///home/devhax/projects/fusuyfusuy/boun-scrape/frontend/src/components/CourseData.jsx#L25), the application hardcodes the department metadata structure (`BOLUM_ARRAY`).
   * **Critique**: The backend dynamic `/api/departments` list is fetched on mount but ignored for link generation. If a new department is added to the university, the link builder fails or requires code changes.
2. **Brittle Export DOM Manipulation**:
   * **Problem**: In `handleExportCSV`, the code creates an `<a>` element, sets the CSV payload as a raw URI, appends it to the document body, triggers click, and removes it.
   * **Critique**: Standard browser restrictions on URI length (usually 2MB limits) will crash the browser for larger datasets. We should use `Blob` and `URL.createObjectURL(blob)` instead.
3. **Countdown Interval / Cleanup Hazards**:
   * **Problem**: In [QuotaMonitor.jsx](file:///home/devhax/projects/fusuyfusuy/boun-scrape/frontend/src/components/QuotaMonitor.jsx), state intervals are set dynamically.
   * **Critique**: If components unmount quickly during countdown actions, intervals continue executing, resulting in React state update warnings on unmounted components and memory leaks.
4. **Poor Mobile Responsiveness**:
   * **Problem**: The explorer uses HTML `<table>` elements with fixed widths.
   * **Critique**: On mobile viewports, tables overflow and horizontal scrolling is clumsy. We should display collapsible flex grid card items on mobile screens.

### B. Visual & UX Critique (The "Bad Looking" Aspect)
1. **Dull Table Layouts**:
   * **Problem**: Tables use default styles with generic borders, lacking visual depth.
   * **Critique**: Use high-contrast headers, row hover states with subtle animations, and tag elements for delivery methods (e.g. online, hybrid, face-to-face).
2. **Console Styling**:
   * **Problem**: The scraper console log uses a basic dark container with monospaced text.
   * **Critique**: Give it a realistic terminal feel (acrylic glass blur, console header, copy to clipboard shortcuts, terminal line highlights).
3. **Hard-to-read Quota Progress**:
   * **Problem**: Quota indicators are plain numbers or simple progress bars.
   * **Critique**: Use vibrant status badges (e.g., Green for Open, Red for Full, Yellow for Restricted/Consent) and smooth visual animations.

---

## 4. Proposed Redesign & Rewrite Strategy

If we rewrite the frontend, we should focus on:
1. **Dynamic Data Integration**: Eliminate hardcoded metadata mapping and fetch everything dynamically from the API.
2. **Premium Acrylic (Glassmorphic) Design System**:
   * Use CSS backdrop-filters, neon gradients, and Outfit/Inter fonts to create a high-end dashboard style.
   * Build clean, animated hover transitions for all cards, forms, and tables.
3. **Modern Data Grids**:
   * Implement card-based responsive views for tablets and mobile devices.
   * Add proper column resize handles, multi-field query builders, and robust `Blob`-based export systems.
4. **Resilient Watchlist Sync**:
   * Synchronize the watchlist cache with a backend database table (instead of pure local storage) so users can access their watchlist from any device.
