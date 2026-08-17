from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from boun_scrape.api.app import create_app
from boun_scrape.api.deps import get_scrape_scheduler_dep
from boun_scrape.config import Settings
from boun_scrape.domain.models import Course, CourseSlot, Department
from boun_scrape.scheduler.runner import ScrapeScheduler


@pytest.fixture
def legacy_app(tmp_path):
    db_file = tmp_path / "legacy_test.db"
    settings = Settings(
        db_path=str(db_file),
        admin_user="admin",
        admin_password_hash="$2b$12$AWoniBnnbFfjVI3tldX2wuOPEVNmik7mwrsM88M6C0ARftQv9WvvG",
        jwt_secret_key="test_secret_key_for_jwt_testing_purposes_only",
    )
    return create_app(settings)


@pytest.mark.asyncio
async def test_legacy_auth_and_protected_routes(legacy_app):
    transport = ASGITransport(app=legacy_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test failed login
        fail_res = await client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "wrongpassword"},
        )
        assert fail_res.status_code == 401

        # Test successful login (default test password hash is for 'admin' or direct test hash)
        login_res = await client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "admin"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test /api/auth/me
        me_res = await client.get("/api/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["username"] == "admin"

        # Test /api/stats
        stats_res = await client.get("/api/stats", headers=headers)
        assert stats_res.status_code == 200
        assert "total_courses" in stats_res.json()

        # Test /api/terms & /api/departments
        terms_res = await client.get("/api/terms", headers=headers)
        assert terms_res.status_code == 200
        assert isinstance(terms_res.json(), list)

        # Test /api/courses
        courses_res = await client.get("/api/courses", headers=headers)
        assert courses_res.status_code == 200
        assert "courses" in courses_res.json()

        # Test /api/scrape/status
        status_res = await client.get("/api/scrape/status", headers=headers)
        assert status_res.status_code == 200
        assert status_res.json()["status"] in ["idle", "running"]


@pytest.mark.asyncio
async def test_legacy_scrape_status_reflects_active_scraping(legacy_app):
    """Regression: /api/scrape/status previously read a dict key
    (`is_cycle_running`) that ScrapeScheduler.get_status() never sets
    (real key is `is_scraping`), so this endpoint always reported "idle"
    even mid-scrape. Also verifies real progress data now flows through
    instead of a hardcoded 50%."""
    mock_scheduler = MagicMock(spec=ScrapeScheduler)
    mock_scheduler.get_status.return_value = {
        "is_running": True,
        "is_scraping": True,
        "interval_seconds": 3600,
        "cron_expression": None,
        "run_count": 0,
        "last_run_time": None,
        "next_run_time": None,
        "last_run_summary": None,
        "current_progress": {"completed": 3, "total": 12, "department": "CMPE"},
    }
    legacy_app.dependency_overrides[get_scrape_scheduler_dep] = lambda: mock_scheduler

    transport = ASGITransport(app=legacy_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/login", data={"username": "admin", "password": "admin"}
        )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        status_res = await client.get("/api/scrape/status", headers=headers)
        assert status_res.status_code == 200
        body = status_res.json()
        assert body["status"] == "running"
        assert body["phase"] == "scraping"
        assert body["progress"] == {"total": 12, "current": 3, "percent": 25.0}

    legacy_app.dependency_overrides.pop(get_scrape_scheduler_dep, None)
