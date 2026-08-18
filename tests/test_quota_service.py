"""Unit tests for QuotaService with in-memory TTL caching and concurrent batch fetching."""

from pathlib import Path
import asyncio
import time
import httpx
import pytest

from boun_scrape.domain.models import QuotaRecord
from boun_scrape.scraper.client import BounScraperClient
from boun_scrape.scraper.quota import QuotaService, format_course_key

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def quota_html() -> str:
    with open(FIXTURES_DIR / "sample_quota.html", "r", encoding="utf-8") as f:
        return f.read()


class TestCourseKeyFormatter:
    """Tests for canonical course key formatting."""

    def test_format_course_key_standard(self) -> None:
        assert format_course_key("CMPE", "150", "01") == "CMPE 150.01"
        assert format_course_key("cmpe", "150", "02") == "CMPE 150.02"

    def test_format_course_key_with_full_code(self) -> None:
        assert format_course_key("CMPE", "CMPE 150", "01") == "CMPE 150.01"

    def test_format_course_key_no_section(self) -> None:
        assert format_course_key("MATH", "101", "") == "MATH 101"
        assert format_course_key("MATH", "MATH 101", "") == "MATH 101"


class TestQuotaService:
    """Tests for live QuotaService query handling and caching."""

    @pytest.mark.asyncio
    async def test_fetch_quota_success(self, quota_html: str) -> None:
        request_count = 0
        requested_params: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count, requested_params
            request_count += 1
            requested_params = dict(request.url.params)
            return httpx.Response(
                200,
                content=quota_html.encode("windows-1254"),
                headers={"Content-Type": "text/html; charset=windows-1254"},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            scraper_client = BounScraperClient(http_client=http_client, min_jitter=0, max_jitter=0)
            service = QuotaService(client=scraper_client, ttl_seconds=10.0)

            records = await service.fetch_quota(
                term="2024/2025-1",
                abbr="CMPE",
                code="150",
                section="01",
            )

            assert len(records) == 5
            assert records[0].department == "CMPE"
            assert records[0].available == 15
            assert request_count == 1
            assert requested_params == {
                "donem": "2024/2025-1",
                "abbr": "CMPE",
                "code": "150",
                "section": "01",
            }
            assert service.cache_size == 1

    @pytest.mark.asyncio
    async def test_fetch_quota_caching_and_bypass(self, quota_html: str) -> None:
        request_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            return httpx.Response(200, content=quota_html.encode("windows-1254"))

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            scraper_client = BounScraperClient(http_client=http_client, min_jitter=0, max_jitter=0)
            service = QuotaService(client=scraper_client, ttl_seconds=2.0)

            # 1st request -> hits network
            res1 = await service.fetch_quota("2024/2025-1", "CMPE", "150", "01")
            assert len(res1) == 5
            assert request_count == 1

            # 2nd request -> cached, no network hit
            res2 = await service.fetch_quota("2024/2025-1", "CMPE", "150", "01")
            assert len(res2) == 5
            assert request_count == 1

            # 3rd request with bypass_cache=True -> hits network
            res3 = await service.fetch_quota("2024/2025-1", "CMPE", "150", "01", bypass_cache=True)
            assert len(res3) == 5
            assert request_count == 2

            # Clear cache
            service.clear_cache()
            assert service.cache_size == 0

            # 4th request after clear -> hits network
            res4 = await service.fetch_quota("2024/2025-1", "CMPE", "150", "01")
            assert len(res4) == 5
            assert request_count == 3

    @pytest.mark.asyncio
    async def test_fetch_quota_ttl_expiration(self, quota_html: str) -> None:
        request_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            return httpx.Response(200, content=quota_html.encode("windows-1254"))

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            scraper_client = BounScraperClient(http_client=http_client, min_jitter=0, max_jitter=0)
            # Very short TTL of 50ms
            service = QuotaService(client=scraper_client, ttl_seconds=0.05)

            await service.fetch_quota("2024/2025-1", "EE", "212", "01")
            assert request_count == 1

            # Wait for TTL to expire
            await asyncio.sleep(0.06)

            await service.fetch_quota("2024/2025-1", "EE", "212", "01")
            assert request_count == 2

    @pytest.mark.asyncio
    async def test_fetch_batch_quotas(self, quota_html: str) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            abbr = request.url.params.get("abbr", "")
            code = request.url.params.get("code", "")
            sec = request.url.params.get("section", "")
            calls.append(f"{abbr}{code}.{sec}")
            return httpx.Response(200, content=quota_html.encode("windows-1254"))

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            scraper_client = BounScraperClient(http_client=http_client, min_jitter=0, max_jitter=0)
            service = QuotaService(client=scraper_client)

            items = [
                ("2024/2025-1", "CMPE", "150", "01"),
                ("2024/2025-1", "CMPE", "160", "01"),
                ("2024/2025-1", "EE", "212", "01"),
            ]

            results = await service.fetch_batch_quotas(items, concurrency=2)

            assert len(results) == 3
            assert "CMPE 150.01" in results
            assert "CMPE 160.01" in results
            assert "EE 212.01" in results
            assert len(results["CMPE 150.01"]) == 5
            assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_fetch_batch_quotas_empty(self) -> None:
        service = QuotaService()
        res = await service.fetch_batch_quotas([])
        assert res == {}
        await service.aclose()

    @pytest.mark.asyncio
    async def test_cache_is_bounded(self, quota_html: str) -> None:
        request_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            return httpx.Response(200, content=quota_html.encode("windows-1254"))

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            scraper_client = BounScraperClient(http_client=http_client, min_jitter=0, max_jitter=0)
            service = QuotaService(client=scraper_client, max_cache_size=2)

            for code in ("150", "250", "350"):
                await service.fetch_quota("2024/2025-1", "CMPE", code, "01")

            # Cap holds the cache to max_cache_size entries, evicting oldest.
            assert service.cache_size == 2

            # The oldest entry (code 150) was evicted, so re-querying it must
            # hit the network again (request_count increments past the 3 above).
            before = request_count
            await service.fetch_quota("2024/2025-1", "CMPE", "150", "01")
            assert request_count == before + 1
            await service.aclose()

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        async with QuotaService() as service:
            assert service.cache_size == 0
            assert service.client is not None
