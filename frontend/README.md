# Frontend Dashboard Web Client

Vite React administrative dashboard web app styled with glassmorphism visual designs and responsive widgets.

---

## 🎨 Design Tokens & Custom CSS

Styles utilize **Tailwind CSS v4** coupled with core custom design parameters in `src/index.css`:
* **HSL Color Map**: Custom dark background values (`--bg-primary`), primary purple neon accents (`--accent-primary`), pink overlays (`--accent-secondary`), and alert indicator values.
* **Glass Panels (`.glass-panel`)**: Uses backdrop filters and blur filters with slight border shadows to build glowing panel wrappers.
* **Interactive Badges**: Color-coded badges (`.badge-success`, `.badge-warning`, `.badge-danger`) mapping course quota status.

---

## 🛠️ Build and Development Scripts

Dependencies are managed using standard Node package scripts inside the container:

```bash
# Start Vite development server
npm run dev

# Compile production package bundles
npm run build

# Run formatting linter audits
npm run lint

# Preview built artifacts locally
npm run preview
```

---

## 🧩 Component Mappings

Key interactive dashboard sections:
1. **[Login.jsx](src/components/Login.jsx)**: Glowing administrative access panel with Caps Lock validation triggers.
2. **[Dashboard.jsx](src/components/Dashboard.jsx)**: System health charts and configuration indicators.
3. **[ScraperControl.jsx](src/components/ScraperControl.jsx)**: Logs stream terminal using customized font formatting, copy options, and async mount trackers.
4. **[CourseData.jsx](src/components/CourseData.jsx)**: Dynamically fetches lookup variables, handles memory-safe `Blob` CSV downloads, and renders responsive tables.
5. **[QuotaMonitor.jsx](src/components/QuotaMonitor.jsx)**: Controls auto-refresh countdown intervals safely and displays capacity indicators.
