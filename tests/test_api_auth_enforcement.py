"""Regression tests: unauthenticated requests must be rejected on protected v1 routes."""

import pytest
from httpx import ASGITransport, AsyncClient

from boun_scrape.api.app import create_app
from boun_scrape.config import Settings


@pytest.fixture
def app(tmp_path):
    db_file = tmp_path / "auth_enforcement_test.db"
    settings = Settings(
        db_path=str(db_file),
        admin_password_hash="$2b$12$AWoniBnnbFfjVI3tldX2wuOPEVNmik7mwrsM88M6C0ARftQv9WvvG",
        jwt_secret_key="test_secret_key_for_jwt_testing_purposes_only",
    )
    return create_app(settings)


@pytest.mark.asyncio
async def test_scraper_routes_require_auth(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/api/v1/scraper/trigger", json={})).status_code == 401
        assert (await client.get("/api/v1/scraper/status")).status_code == 401
        assert (await client.post("/api/v1/scraper/stop")).status_code == 401
        assert (await client.get("/api/v1/scraper/logs")).status_code == 401
        assert (await client.get("/api/v1/scraper/config")).status_code == 401
        assert (await client.post("/api/v1/scraper/config", json={"cookies": "x"})).status_code == 401


@pytest.mark.asyncio
async def test_quota_routes_require_auth(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/quota?abbr=CMPE&code=150")
        assert resp.status_code == 401

        resp = await client.post("/api/v1/quota/batch", json={"items": []})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limited_after_repeated_failures(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(5):
            resp = await client.post(
                "/api/v1/auth/login", data={"username": "admin", "password": "wrong"}
            )
            assert resp.status_code == 401

        resp = await client.post(
            "/api/v1/auth/login", data={"username": "admin", "password": "wrong"}
        )
        assert resp.status_code == 429


@pytest.mark.asyncio
async def test_auth_me_requires_auth(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_login_and_me_round_trip(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        fail_res = await client.post(
            "/api/v1/auth/login", data={"username": "admin", "password": "wrongpassword"}
        )
        assert fail_res.status_code == 401

        login_res = await client.post(
            "/api/v1/auth/login", data={"username": "admin", "password": "admin"}
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        me_res = await client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_login_rate_limiting_ip_spoofing_prevented(app) -> None:
    """Verify that prepending fake IPs to X-Forwarded-For does not bypass rate limiting."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Client tries sending distinct fake leftmost IPs, but actual upstream peer is 203.0.113.10
        for i in range(5):
            headers = {"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.10"}
            resp = await client.post(
                "/api/v1/auth/login",
                data={"username": "admin", "password": "wrong"},
                headers=headers,
            )
            assert resp.status_code == 401

        # 6th attempt with another spoofed IP prefix must be blocked because real client is 203.0.113.10
        headers = {"X-Forwarded-For": "10.0.0.99, 203.0.113.10"}
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "wrong"},
            headers=headers,
        )
        assert resp.status_code == 429

