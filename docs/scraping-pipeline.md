# Scraping Pipeline & ETL Specification

This document provides a technical blueprint of the 4-stage automated scraping pipeline, ASP.NET ViewState handling, reCAPTCHA bypass mechanics, concurrency controls, and database compilation ETL.

---

## 1. Pipeline Architectural Flow

```
[Seed File: response.html]
         |
         | Phase 1: scraper.py
         v
[responses/<term>.html] (ASP.NET Form POST / Terms discovery)
         |
         | Phase 2: parse_responses.py
         v
[departments_all.json / .csv] (Department code catalog extraction)
         |
         | Phase 3: scrape_all_schedules.py
         v
[schedules/<term>/<dept>.html] (Multi-threaded HTTP pool crawling)
         |
         | Phase 4: parse_schedules_to_db.py
         v
[SQLite DB: /data/schedules.db] (Multi-process transactional ETL)
```

---

## 2. Stage Breakdown & Operational Details

### Stage 1: Term Discovery (`scraper.py`)
- **Target Portal**: `https://registration.bogazici.edu.tr/buis/General/schedule.aspx?p=semester`
- **Session & Security State**:
  - ASP.NET Web Forms utilize hidden token fields for security verification.
  - `scraper.py` parses `__VIEWSTATE`, `__VIEWSTATEGENERATOR`, and `__EVENTVALIDATION` from the seed file `response.html` using `BeautifulSoup`.
  - Session cookies (`ASP.NET_SessionId`) are attached to request headers from `cookies.txt`.
- **Execution Workflow**:
  1. Extracts all available term values from the `<select name="DropDownList1">` element.
  2. Iterates over active terms, issuing HTTP POST requests containing form data: `__VIEWSTATE`, `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION`, and `DropDownList1=<term_value>`.
  3. Decodes response using `Windows-1254` character encoding.
  4. Detects bot detection pages (looking for `"reCAPTCHA"` or `"Access Denied"` strings).
  5. Saves valid response HTML files to `responses/<term_clean>.html`.

---

### Stage 2: Department Extraction (`parse_responses.py`)
- **Source**: `responses/*.html` files downloaded in Stage 1.
- **Parser Mechanics**:
  - Scans HTML documents for anchor links matching department query parameters: `kisaadi=<code` and `bolum=<full_name>`.
  - Normalizes department short codes (e.g. `CMPE`, `MATH`, `EC`, `EE`).
  - Deduplicates entries across all semesters.
- **Output Artifacts**:
  - `departments_all.json`: Structured array of objects `[{"kisaadi": "CMPE", "bolum": "COMPUTER ENGINEERING"}, ...]`.
  - `departments_all.csv`: Exported CSV list.

---

### Stage 3: Multi-Threaded Schedule Crawler (`scrape_all_schedules.py`)
- **Target Endpoint**: `https://registration.bogazici.edu.tr/scripts/sch.asp?donem=<term>&kisaadi=<dept>&bolum=<dept_full>`
- **Concurrency Model**:
  - `concurrent.futures.ThreadPoolExecutor(max_workers=10)`.
  - Uses `threading.local()` to maintain separate `requests.Session()` objects per worker thread, enabling HTTP connection pooling.
- **Polite Crawling & Anti-Bot Protection**:
  - Inserts random jitter sleep intervals (`random.uniform(0.1, 0.4)` seconds) prior to every HTTP GET call.
  - Implements automatic retry logic with exponential backoff on transient network errors.
- **Output Directory Structure**:
  - Writes schedule HTML files to disk under directory path: `schedules/<term_folder>/<dept_code>.html`.

---

### Stage 4: Parallel Database Compiler & ETL (`parse_schedules_to_db.py`)
- **Concurrency Model**:
  - `concurrent.futures.ProcessPoolExecutor()` mapping across all available CPU cores.
  - Parallelizes parsing of raw HTML files into standardized Python dictionaries.

#### Custom Parsing Algorithms
1. **Multi-Character Day Codes**: Detects standard BOUN day combinations:
   - `M` -> Monday
   - `T` -> Tuesday
   - `W` -> Wednesday
   - `Th` -> Thursday
   - `F` -> Friday
   - `St` -> Saturday
   - `Su` -> Sunday
2. **Multi-Digit Period Matching**: Correctly handles single and multi-digit class period slots (Periods `1` through `14`).
3. **Room & Slot Alignment**: Correlates split classroom locations (e.g., `ETA A2 / NH 101`) to corresponding slot hours.

#### Transactional SQLite Compilation
To eliminate I/O disk bottlenecks:
- Applies PRAGMA configurations:
  ```sql
  PRAGMA synchronous = OFF;
  PRAGMA journal_mode = MEMORY;
  ```
- Executes bulk insertions inside a single transaction wrapper:
  ```sql
  BEGIN TRANSACTION;
  -- Insert courses
  -- Insert course_slots
  COMMIT;
  ```
- Exported SQLite DB file is written to `DB_PATH` (default `/data/schedules.db`).
- Generates fallback CSV export `schedules.csv`.

---

## 3. Real-Time Quota Proxy Pipeline (`app/quota.py`)

In addition to scheduled bulk ETL, the system provides on-demand live quota scraping targeting `/scripts/quotasearch.asp`.

```
[User UI] ---> GET /api/quota/check?abbr=CMPE&code=150&section=01&donem=2024/2025-1
                     |
                     v
       [FastAPI app/quota.py Scraper]
                     |
                     | HTTP GET (Windows-1254)
                     v
   [https://registration.boun.edu.tr/scripts/quotasearch.asp]
                     |
                     | Parse schtd / schtd2 HTML tables
                     v
       [JSON Response to Client Browser]
```

### Returned Data Schema
```json
{
  "abbr": "CMPE",
  "code": "150",
  "section": "01",
  "donem": "2024/2025-1",
  "quota": 120,
  "enrolled": 115,
  "consent": 0,
  "open_slots": 5,
  "status": "open"
}
```
Status options: `open`, `closed`, `consent`, `unlimited`.
