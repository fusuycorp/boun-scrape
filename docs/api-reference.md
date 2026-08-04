# REST API Reference Specification

This document provides a complete REST API reference for the **BOUN Scraper FastAPI Backend** service.

All administrative routes require HTTP Bearer authentication via a JWT access token returned from `POST /api/auth/login`.

---

## 1. Authentication & Session Endpoints

### 1.1 `POST /api/auth/login`
Authenticates administrative credentials and returns a JWT access token.

- **Request Headers**: `Content-Type: application/x-www-form-urlencoded`
- **Request Body Parameters**:
  - `username` (string, required): Admin username.
  - `password` (string, required): Admin password.
- **Success Response (`200 OK`)**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
  ```
- **Error Response (`401 Unauthorized`)**:
  ```json
  {
    "detail": "Incorrect username or password"
  }
  ```

---

### 1.2 `GET /api/auth/me`
Validates active JWT Bearer token and returns current user details.

- **Security**: Bearer token required.
- **Success Response (`200 OK`)**:
  ```json
  {
    "username": "admin"
  }
  ```

---

## 2. Analytics & Database Explorer Endpoints

### 2.1 `GET /api/stats`
Returns aggregated count statistics from the SQLite database.

- **Security**: Bearer token required.
- **Success Response (`200 OK`)**:
  ```json
  {
    "total_courses": 4250,
    "total_slots": 12800,
    "total_departments": 64,
    "total_terms": 8
  }
  ```

---

### 2.2 `GET /api/terms`
Returns a sorted list of unique terms stored in the database.

- **Security**: Bearer token required.
- **Success Response (`200 OK`)**:
  ```json
  [
    "2024/2025-1",
    "2023/2024-2",
    "2023/2024-1"
  ]
  ```

---

### 2.3 `GET /api/departments`
Returns a sorted list of active department short codes present in DB records.

- **Security**: Bearer token required.
- **Success Response (`200 OK`)**:
  ```json
  ["AD", "ASIA", "BIS", "BM", "CET", "CHEM", "CMPE", "EE", "IE", "MATH", "PHYS"]
  ```

---

### 2.4 `GET /api/departments/all`
Returns the master catalog of all departments extracted during pipeline Stage 2.

- **Security**: Bearer token required.
- **Success Response (`200 OK`)**:
  ```json
  [
    {
      "kisaadi": "CMPE",
      "bolum": "COMPUTER ENGINEERING"
    },
    {
      "kisaadi": "MATH",
      "bolum": "MATHEMATICS"
    }
  ]
  ```

---

### 2.5 `GET /api/courses`
Multi-filter paginated course query engine.

- **Security**: Bearer token required.
- **Query Parameters**:
  - `term` (string, optional): Filter by academic term (e.g. `2024/2025-1`).
  - `department` (string, optional): Filter by department code (e.g. `CMPE`).
  - `search` (string, optional): Keyword search matching course code, name, or instructor.
  - `day` (string, optional): Filter by day code (`M`, `T`, `W`, `Th`, `F`, `St`, `Su`).
  - `page` (integer, default `1`): Target page number.
  - `limit` (integer, default `50`): Items per page.
- **Success Response (`200 OK`)**:
  ```json
  {
    "courses": [
      {
        "id": 102,
        "term": "2024/2025-1",
        "department": "CMPE",
        "course_code": "CMPE 150",
        "section": "01",
        "course_name": "Introduction to Computing",
        "instructor": "HALUK OĞUZ KAYA",
        "credits": "4",
        "ects": "7",
        "delivery_method": "Face to Face",
        "exam_location": "M1100 / M2180",
        "exam_date": "2024-11-15 14:00",
        "sl": "N",
        "required_for": "CMPE, EE, IE",
        "departments": "ALL",
        "slots": [
          {
            "id": 401,
            "day": "M",
            "hour": "2",
            "room": "M1100",
            "slot_title": "CMPE 150",
            "instructor": "HALUK OĞUZ KAYA"
          },
          {
            "id": 402,
            "day": "W",
            "hour": "3",
            "room": "M1100",
            "slot_title": "CMPE 150",
            "instructor": "HALUK OĞUZ KAYA"
          }
        ]
      }
    ],
    "total": 1,
    "page": 1,
    "limit": 50,
    "pages": 1
  }
  ```

---

## 3. Scraper Control & Monitoring Endpoints

### 3.1 `POST /api/scrape/start`
Triggers background execution of a scraping pipeline phase.

- **Security**: Bearer token required.
- **Request Body**:
  ```json
  {
    "phase": "phase1",
    "force_refresh": false
  }
  ```
  *Phases*: `phase1` (Term discovery), `phase2` (Extract Depts), `phase3` (Crawl Schedules), `phase4` (DB Compile).
- **Success Response (`200 OK`)**:
  ```json
  {
    "message": "Scraping process phase1 started successfully",
    "phase": "phase1"
  }
  ```

---

### 3.2 `POST /api/scrape/stop`
Terminates the actively running background scraper process.

- **Security**: Bearer token required.
- **Success Response (`200 OK`)**:
  ```json
  {
    "message": "Scraping process terminated"
  }
  ```

---

### 3.3 `GET /api/scrape/status`
Polls state and execution metrics of the scraper orchestrator.

- **Security**: Bearer token required.
- **Success Response (`200 OK`)**:
  ```json
  {
    "phase": "phase3",
    "status": "running",
    "progress": 43.75,
    "current_step": 140,
    "total_steps": 320,
    "message": "Scraping department schedules: 140/320"
  }
  ```

---

### 3.4 `GET /api/scrape/logs`
Returns or clears buffered stdout terminal log lines from the background runner.

- **Security**: Bearer token required.
- **Query Parameters**:
  - `clear` (boolean, optional): If `true`, resets the in-memory log buffer.
- **Success Response (`200 OK`)**:
  ```json
  {
    "logs": [
      "[INFO] Starting Phase 3: Crawling department schedules...",
      "[INFO] Worker 2 downloading CMPE...",
      "[INFO] Progress: 140/320"
    ]
  }
  ```

---

### 3.5 `GET /api/scrape/terms`
Scans file storage locations (`responses/` and `schedules/`) for last modified timestamps.

- **Security**: Bearer token required.
- **Success Response (`200 OK`)**:
  ```json
  [
    {
      "term": "2024/2025-1",
      "response_exists": true,
      "schedules_count": 64,
      "last_modified": "2026-08-04T09:30:00Z"
    }
  ]
  ```

---

## 4. Quota Proxy & Configuration Endpoints

### 4.1 `GET /api/quota/check`
Proxies real-time course quota lookups directly to Boğaziçi servers.

- **Security**: Bearer token required.
- **Query Parameters**:
  - `abbr` (string, required): Department code (e.g. `CMPE`).
  - `code` (string, required): Course number (e.g. `150`).
  - `section` (string, required): Section number (e.g. `01`).
  - `donem` (string, required): Term code (e.g. `2024/2025-1`).
- **Success Response (`200 OK`)**:
  ```json
  {
    "abbr": "CMPE",
    "code": "150",
    "section": "01",
    "donem": "2024/2025-1",
    "quota": 120,
    "enrolled": 118,
    "consent": 0,
    "open_slots": 2,
    "status": "open"
  }
  ```

---

### 4.2 `GET /api/config` & `POST /api/config`
Reads or updates ASP.NET session cookies and seed HTML markup (`response.html`).

- **Security**: Bearer token required.
- **POST Request Body**:
  ```json
  {
    "cookies": "ASP.NET_SessionId=abcdef123456...",
    "seed_html": "<html>...</html>"
  }
  ```
