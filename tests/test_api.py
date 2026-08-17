"""Comprehensive API integration tests for all FastAPI endpoints."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient

from boun_scrape.api.app import create_app
from boun_scrape.api.auth import get_current_user
from boun_scrape.api.deps import (
    get_course_repo_dep,
    get_db_manager_dep,
    get_log_buffer_dep,
    get_quota_service_dep,
    get_scrape_scheduler_dep,
    get_scraper_client_dep,
    get_settings_dep,
)
from boun_scrape.api.logging_buffer import LogBuffer
from boun_scrape.config import Settings
from boun_scrape.domain.events import ChangeType, CourseDeltaEvent
from boun_scrape.domain.models import (
    Course,
    CourseSlot,
    Department,
    QuotaRecord,
    RunStatus,
    ScrapeRunSummary,
)
from boun_scrape.scheduler.runner import ScrapeAlreadyRunningError, ScrapeScheduler
from boun_scrape.scraper.client import BounScraperClient
from boun_scrape.scraper.quota import QuotaService
from boun_scrape.storage.database import DatabaseManager
from boun_scrape.storage.repository import CourseRepository


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Create test settings with isolated database and export directory."""
    db_file = tmp_path / "test_api.db"
    export_dir = tmp_path / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        db_path=str(db_file),
        export_dir=str(export_dir),
        cookies_path=str(tmp_path / "cookies.txt"),
        allowed_origins=["http://localhost:3000", "http://localhost:5173"],
    )


@pytest.fixture
def seeded_repo(test_settings: Settings) -> CourseRepository:
    """Initialize test database with sample courses, slots, departments, runs, and deltas."""
    db = DatabaseManager(test_settings.db_path)
    db.init_db()
    repo = CourseRepository(db)

    term = "2024/2025-1"
    depts = [
        Department(code="CMPE", name="Computer Engineering", bolum="BILGISAYAR MUHENDISLIGI"),
        Department(code="MATH", name="Mathematics", bolum="MATEMATIK"),
    ]
    repo.save_departments(term, depts)

    courses = [
        Course(
            term=term,
            department="CMPE",
            course_code="CMPE150",
            section="01",
            course_name="Introduction to Computing",
            instructor="Prof. Smith",
            credits=3.0,
            ects=6.0,
            slots=[
                CourseSlot(day="M", hour="12", room="NH101", slot_title="Lecture", instructor="Prof. Smith"),
                CourseSlot(day="W", hour="34", room="NH101", slot_title="Lecture", instructor="Prof. Smith"),
                CourseSlot(day="F", hour="56", room="LAB1", slot_title="PS", instructor="TA John"),
            ],
        ),
        Course(
            term=term,
            department="CMPE",
            course_code="CMPE250",
            section="01",
            course_name="Data Structures and Algorithms",
            instructor="Dr. Brown",
            credits=4.0,
            ects=7.0,
            slots=[
                CourseSlot(day="T", hour="12", room="KB433", slot_title="Lecture", instructor="Dr. Brown"),
                CourseSlot(day="Th", hour="12", room="KB433", slot_title="Lecture", instructor="Dr. Brown"),
            ],
        ),
        Course(
            term=term,
            department="MATH",
            course_code="MATH101",
            section="01",
            course_name="Calculus I",
            instructor="Dr. Taylor",
            credits=4.0,
            ects=7.0,
            slots=[
                CourseSlot(day="M", hour="34", room="M1100", slot_title="Lecture", instructor="Dr. Taylor"),
                CourseSlot(day="W", hour="12", room="M1100", slot_title="Lecture", instructor="Dr. Taylor"),
            ],
        ),
    ]
    repo.save_courses_and_slots(term, courses)

    # Scrape run
    run = ScrapeRunSummary(
        run_id="run_test_001",
        term=term,
        status=RunStatus.COMPLETED,
        total_departments=2,
        total_courses=3,
        total_slots=7,
        changes_detected=1,
        started_at="2026-08-15T01:00:00Z",
        completed_at="2026-08-15T01:05:00Z",
    )
    repo.save_scrape_run(run)

    # Delta
    delta = CourseDeltaEvent(
        change_type=ChangeType.MODIFIED,
        term=term,
        department="CMPE",
        course_code="CMPE150",
        section="01",
        timestamp="2026-08-15T01:02:00Z",
        old_value={"instructor": "Old Instructor"},
        new_value={"instructor": "Prof. Smith"},
        details='["instructor"]',
    )
    repo.save_deltas([delta], run_id="run_test_001")

    return repo


@pytest.fixture
def mock_quota_service() -> QuotaService:
    """Mock QuotaService for predictable responses."""
    svc = MagicMock(spec=QuotaService)
    svc.fetch_quota = AsyncMock(
        return_value=[
            QuotaRecord(
                department="CMPE",
                status="Open",
                quota="50",
                current="45",
                quota_numeric=50,
                current_numeric=45,
                is_consent=False,
                is_unlimited=False,
                available=5,
            )
        ]
    )
    svc.fetch_batch_quotas = AsyncMock(
        return_value={
            "CMPE 150.01": [
                QuotaRecord(
                    department="CMPE",
                    status="Open",
                    quota="50",
                    current="45",
                    quota_numeric=50,
                    current_numeric=45,
                    is_consent=False,
                    is_unlimited=False,
                    available=5,
                )
            ]
        }
    )
    return svc


@pytest.fixture
def mock_scheduler(seeded_repo: CourseRepository, test_settings: Settings) -> ScrapeScheduler:
    """Mock ScrapeScheduler for trigger and status endpoints."""
    sched = MagicMock(spec=ScrapeScheduler)
    sched.is_scraping = False
    sched.is_running = True
    sched.get_status.return_value = {
        "is_running": True,
        "is_scraping": False,
        "interval_seconds": 3600,
        "cron_expression": None,
        "run_count": 1,
        "last_run_time": "2026-08-15T01:05:00Z",
        "next_run_time": "2026-08-15T02:05:00Z",
        "last_run_summary": {
            "run_id": "run_test_001",
            "term": "2024/2025-1",
            "status": "completed",
            "total_departments": 2,
            "total_courses": 3,
            "total_slots": 7,
            "changes_detected": 1,
            "started_at": "2026-08-15T01:00:00Z",
            "completed_at": "2026-08-15T01:05:00Z",
            "error_message": None,
        },
        "current_progress": {"completed": 3, "total": 12, "department": "CMPE"},
    }
    sched.execute_scrape_cycle = AsyncMock(
        return_value=ScrapeRunSummary(
            run_id="run_sync_001",
            term="2024/2025-1",
            status=RunStatus.COMPLETED,
            total_departments=2,
            total_courses=3,
            total_slots=7,
            changes_detected=0,
            started_at="2026-08-15T02:00:00Z",
            completed_at="2026-08-15T02:02:00Z",
        )
    )
    sched.stop = AsyncMock()
    return sched


@pytest.fixture
def test_log_buffer() -> LogBuffer:
    """Pre-populated LogBuffer fixture."""
    buf = LogBuffer(capacity=100)
    buf.add("INFO", "boun_scrape.scraper", "Scraping started")
    buf.add("WARNING", "boun_scrape.flow", "Minor rate limit delay")
    buf.add("ERROR", "boun_scrape.parser", "Parser failed on test item")
    return buf


@pytest.fixture
async def async_client(
    test_settings: Settings,
    seeded_repo: CourseRepository,
    mock_quota_service: QuotaService,
    mock_scheduler: ScrapeScheduler,
    test_log_buffer: LogBuffer,
) -> AsyncClient:
    """Build test client with all dependency overrides wired."""
    app = create_app(settings=test_settings)

    db_mgr = DatabaseManager(test_settings.db_path)
    mock_client = MagicMock(spec=BounScraperClient)

    app.dependency_overrides[get_settings_dep] = lambda: test_settings
    app.dependency_overrides[get_db_manager_dep] = lambda: db_mgr
    app.dependency_overrides[get_course_repo_dep] = lambda: seeded_repo
    app.dependency_overrides[get_scraper_client_dep] = lambda: mock_client
    app.dependency_overrides[get_quota_service_dep] = lambda: mock_quota_service
    app.dependency_overrides[get_scrape_scheduler_dep] = lambda: mock_scheduler
    app.dependency_overrides[get_log_buffer_dep] = lambda: test_log_buffer
    app.dependency_overrides[get_current_user] = lambda: "admin"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestApiEndpoints:
    """Test suite covering all FastAPI routes and middleware."""

    @pytest.mark.asyncio
    async def test_health_check(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "status": "ok",
            "service": "boun-scrape",
            "version": "0.2.0",
        }

    @pytest.mark.asyncio
    async def test_cors_headers(self, async_client: AsyncClient) -> None:
        headers = {"Origin": "http://localhost:3000"}
        response = await async_client.get("/", headers=headers)
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    @pytest.mark.asyncio
    async def test_get_terms(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/terms")
        assert response.status_code == 200
        terms = response.json()
        assert "2024/2025-1" in terms

    @pytest.mark.asyncio
    async def test_get_departments(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/departments")
        assert response.status_code == 200
        depts = response.json()
        codes = [d["code"] for d in depts]
        assert "CMPE" in codes
        assert "MATH" in codes

    @pytest.mark.asyncio
    async def test_get_departments_with_term_filter(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/departments?term=2024/2025-1")
        assert response.status_code == 200
        depts = response.json()
        assert len(depts) == 2

    @pytest.mark.asyncio
    async def test_get_stats(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 3
        assert data["total_departments"] == 2
        assert data["total_terms"] == 1
        assert data["total_slots"] == 7
        assert data["last_scraped"] == "2026-08-15T01:05:00Z"

    @pytest.mark.asyncio
    async def test_get_courses_pagination(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/courses?page=1&size=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["size"] == 2
        assert data["pages"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_get_courses_filter_by_department(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/courses?department=CMPE")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["department"] == "CMPE"

    @pytest.mark.asyncio
    async def test_get_courses_filter_by_code(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/courses?course_code=150")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["course_code"] == "CMPE150"

    @pytest.mark.asyncio
    async def test_get_courses_filter_by_instructor(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/courses?instructor=Smith")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["instructor"] == "Prof. Smith"

    @pytest.mark.asyncio
    async def test_get_courses_filter_by_day_and_room(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/courses?day=M&room=NH101")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["course_code"] == "CMPE150"

    @pytest.mark.asyncio
    async def test_get_courses_filter_by_hour_and_slot_title(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/courses?hour=56&slot_title=PS")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["course_code"] == "CMPE150"

    @pytest.mark.asyncio
    async def test_get_courses_keyword_search(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/courses?keyword=Calculus")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["course_code"] == "MATH101"

    @pytest.mark.asyncio
    async def test_get_course_by_id_found(self, async_client: AsyncClient, seeded_repo: CourseRepository) -> None:
        courses = seeded_repo.get_courses_by_term("2024/2025-1")
        target_id = courses[0].id
        response = await async_client.get(f"/api/v1/courses/{target_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == target_id
        assert len(data["slots"]) > 0

    @pytest.mark.asyncio
    async def test_get_course_by_id_not_found(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/courses/999999")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_quota(self, async_client: AsyncClient, mock_quota_service: QuotaService) -> None:
        response = await async_client.get("/api/v1/quota?abbr=CMPE&code=150&section=01")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["department"] == "CMPE"
        assert data[0]["available"] == 5
        mock_quota_service.fetch_quota.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_quota_batch(self, async_client: AsyncClient, mock_quota_service: QuotaService) -> None:
        payload = {
            "items": [
                {"term": "2024/2025-1", "abbr": "CMPE", "code": "150", "section": "01"}
            ],
            "concurrency": 3,
            "bypass_cache": True,
        }
        response = await async_client.post("/api/v1/quota/batch", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "CMPE 150.01" in data
        assert len(data["CMPE 150.01"]) == 1
        mock_quota_service.fetch_batch_quotas.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_deltas(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/feeds/deltas?term=2024/2025-1")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["course_code"] == "CMPE150"
        assert data[0]["change_type"] == "MODIFIED"

    @pytest.mark.asyncio
    async def test_get_scrape_runs(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/feeds/runs?term=2024/2025-1")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["run_id"] == "run_test_001"
        assert data[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_download_export_json(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/feeds/exports/2024_2025-1/json")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        assert len(response.json()) == 3

    @pytest.mark.asyncio
    async def test_download_export_csv(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/feeds/exports/2024_2025-1/csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "course_code" in response.text

    @pytest.mark.asyncio
    async def test_download_export_sqlite(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/feeds/exports/2024_2025-1/sqlite")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.sqlite3"
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_download_export_invalid_format(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/feeds/exports/2024_2025-1/xml")
        assert response.status_code == 400
        assert "unsupported format" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_download_export_nonexistent_term(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/feeds/exports/1990_1991-1/json")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_trigger_scrape_background(self, async_client: AsyncClient) -> None:
        payload = {"term": "2024/2025-1", "background": True}
        response = await async_client.post("/api/v1/scraper/trigger", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "triggered"

    @pytest.mark.asyncio
    async def test_trigger_scrape_sync(self, async_client: AsyncClient) -> None:
        payload = {"term": "2024/2025-1", "background": False}
        response = await async_client.post("/api/v1/scraper/trigger", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "run_sync_001"
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_trigger_scrape_conflict(self, async_client: AsyncClient, mock_scheduler: ScrapeScheduler) -> None:
        mock_scheduler.is_scraping = True
        payload = {"term": "2024/2025-1", "background": True}
        response = await async_client.post("/api/v1/scraper/trigger", json=payload)
        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_scraper_status(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/scraper/status")
        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is True
        assert data["run_count"] == 1
        assert data["current_progress"] == {"completed": 3, "total": 12, "department": "CMPE"}

    @pytest.mark.asyncio
    async def test_scraper_stop(self, async_client: AsyncClient, mock_scheduler: ScrapeScheduler) -> None:
        response = await async_client.post("/api/v1/scraper/stop")
        assert response.status_code == 200
        assert response.json()["status"] == "stopped"
        mock_scheduler.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_scraper_logs(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/scraper/logs?limit=10")
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) == 3

        # Filter by ERROR level
        err_resp = await async_client.get("/api/v1/scraper/logs?level=ERROR")
        assert err_resp.status_code == 200
        err_logs = err_resp.json()
        assert len(err_logs) == 1
        assert err_logs[0]["level"] == "ERROR"

    @pytest.mark.asyncio
    async def test_scraper_logs_clear(self, async_client: AsyncClient, test_log_buffer: LogBuffer) -> None:
        response = await async_client.get("/api/v1/scraper/logs?clear=true")
        assert response.status_code == 200
        assert len(response.json()) == 3
        assert len(test_log_buffer) == 0

        second_response = await async_client.get("/api/v1/scraper/logs")
        assert second_response.json() == []

    @pytest.mark.asyncio
    async def test_scraper_config_round_trip(self, async_client: AsyncClient, test_settings: Settings) -> None:
        empty_response = await async_client.get("/api/v1/scraper/config")
        assert empty_response.status_code == 200
        assert empty_response.json() == {"cookie_loaded": False}

        update_response = await async_client.post(
            "/api/v1/scraper/config", json={"cookies": "ASP.NET_SessionId=abc123"}
        )
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "ok"
        assert Path(test_settings.cookies_path).read_text() == "ASP.NET_SessionId=abc123"

        loaded_response = await async_client.get("/api/v1/scraper/config")
        assert loaded_response.json() == {"cookie_loaded": True}
