"""Unit and integration tests for HMAC-signed webhook dispatcher."""

import asyncio
import hashlib
import hmac
import json
import httpx
import pytest

from boun_scrape.domain.events import ChangeType, CourseDeltaEvent
from boun_scrape.domain.models import RunStatus, ScrapeRunSummary
from boun_scrape.feeds.webhooks import (
    WebhookDeliveryResult,
    WebhookDispatcher,
    compute_hmac_signature,
    serialize_webhook_payload,
)


@pytest.fixture
def sample_delta() -> CourseDeltaEvent:
    return CourseDeltaEvent(
        change_type=ChangeType.MODIFIED,
        term="2024/2025-1",
        department="CMPE",
        course_code="CMPE 150",
        section="01",
        timestamp="2025-01-15T12:00:00Z",
        old_value={"instructor": "OLD INSTRUCTOR"},
        new_value={"instructor": "NEW INSTRUCTOR"},
        details="Instructor changed.",
    )


@pytest.fixture
def sample_summary() -> ScrapeRunSummary:
    return ScrapeRunSummary(
        run_id="run_123",
        term="2024/2025-1",
        status=RunStatus.COMPLETED,
        total_departments=30,
        total_courses=1200,
        total_slots=3500,
        changes_detected=5,
        started_at="2025-01-15T12:00:00Z",
        completed_at="2025-01-15T12:02:00Z",
    )


class TestWebhookPayloadAndHmac:
    """Tests for HMAC signature generation and payload serialization."""

    def test_compute_hmac_signature(self) -> None:
        secret = "super_secret_webhook_key"
        payload = b'{"hello": "world"}'
        sig = compute_hmac_signature(secret, payload)

        expected = hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()
        assert sig == expected
        assert len(sig) == 64

    def test_serialize_course_delta_event(
        self, sample_delta: CourseDeltaEvent
    ) -> None:
        raw_bytes = serialize_webhook_payload(sample_delta)
        data = json.loads(raw_bytes.decode("utf-8"))
        assert data["change_type"] == "MODIFIED"
        assert data["course_code"] == "CMPE 150"
        assert data["new_value"]["instructor"] == "NEW INSTRUCTOR"

    def test_serialize_scrape_run_summary(
        self, sample_summary: ScrapeRunSummary
    ) -> None:
        raw_bytes = serialize_webhook_payload(sample_summary)
        data = json.loads(raw_bytes.decode("utf-8"))
        assert data["run_id"] == "run_123"
        assert data["status"] == "completed"
        assert data["total_courses"] == 1200


class TestWebhookDispatcher:
    """Tests for asynchronous webhook dispatching with signatures and retries."""

    @pytest.mark.asyncio
    async def test_dispatch_with_hmac_signature(
        self, sample_delta: CourseDeltaEvent
    ) -> None:
        received_headers: dict[str, str] = {}
        received_body: bytes = b""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal received_headers, received_body
            received_headers = dict(request.headers)
            received_body = request.read()
            return httpx.Response(200, json={"status": "ok"})

        transport = httpx.MockTransport(handler)
        secret = "boun_secret_token"
        async with httpx.AsyncClient(transport=transport) as http_client:
            dispatcher = WebhookDispatcher(
                urls=["https://example.com/webhook"],
                webhook_secret=secret,
                http_client=http_client,
            )

            results = await dispatcher.dispatch(sample_delta)

            assert len(results) == 1
            assert results[0].success is True
            assert results[0].status_code == 200
            assert results[0].attempts == 1

            # Validate HMAC signature header
            assert "x-boun-signature" in received_headers
            sig_header = received_headers["x-boun-signature"]
            assert sig_header.startswith("sha256=")
            expected_sig = compute_hmac_signature(secret, received_body)
            assert sig_header == f"sha256={expected_sig}"

    @pytest.mark.asyncio
    async def test_dispatch_without_secret(
        self, sample_delta: CourseDeltaEvent
    ) -> None:
        received_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal received_headers
            received_headers = dict(request.headers)
            return httpx.Response(200)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            dispatcher = WebhookDispatcher(
                urls=["https://example.com/webhook"],
                webhook_secret="",
                http_client=http_client,
            )

            results = await dispatcher.dispatch(sample_delta)
            assert len(results) == 1
            assert results[0].success is True
            assert "x-boun-signature" not in received_headers

    @pytest.mark.asyncio
    async def test_dispatch_retry_backoff_on_failure(self) -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                return httpx.Response(500, text="Internal Server Error")
            return httpx.Response(200, json={"status": "recovered"})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            dispatcher = WebhookDispatcher(
                urls=["https://example.com/retry-test"],
                max_retries=3,
                backoff_factor=0.01,
                http_client=http_client,
            )

            results = await dispatcher.dispatch({"test": "data"})
            assert len(results) == 1
            assert results[0].success is True
            assert results[0].attempts == 3
            assert results[0].status_code == 200

    @pytest.mark.asyncio
    async def test_dispatch_permanent_failure(self) -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(503, text="Service Unavailable")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            dispatcher = WebhookDispatcher(
                urls=["https://example.com/fail-test"],
                max_retries=2,
                backoff_factor=0.01,
                http_client=http_client,
            )

            results = await dispatcher.dispatch({"test": "data"})
            assert len(results) == 1
            assert results[0].success is False
            assert results[0].attempts == 2
            assert results[0].status_code == 503
            assert "503" in (results[0].error_message or "")

    @pytest.mark.asyncio
    async def test_dispatch_multiple_urls_concurrently(self) -> None:
        requested_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested_urls.append(str(request.url))
            return httpx.Response(200)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            dispatcher = WebhookDispatcher(
                urls=[
                    "https://service-a.com/hook",
                    "https://service-b.com/hook",
                ],
                http_client=http_client,
            )

            results = await dispatcher.dispatch({"event": "test"})
            assert len(results) == 2
            assert all(r.success for r in results)
            assert "https://service-a.com/hook" in requested_urls
            assert "https://service-b.com/hook" in requested_urls

    @pytest.mark.asyncio
    async def test_dispatch_deltas_and_summary(
        self,
        sample_delta: CourseDeltaEvent,
        sample_summary: ScrapeRunSummary,
    ) -> None:
        payloads: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            payloads.append(json.loads(request.read()))
            return httpx.Response(200)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            dispatcher = WebhookDispatcher(
                urls=["https://example.com/hook"],
                http_client=http_client,
            )

            # Test dispatch_deltas
            res1 = await dispatcher.dispatch_deltas([sample_delta])
            assert len(res1) == 1
            assert payloads[-1]["event"] == "courses.deltas"
            assert payloads[-1]["count"] == 1

            # Test dispatch_run_summary
            res2 = await dispatcher.dispatch_run_summary(sample_summary)
            assert len(res2) == 1
            assert payloads[-1]["event"] == "scrape.summary"
            assert payloads[-1]["total_courses"] == 1200

    @pytest.mark.asyncio
    async def test_dispatch_empty_urls_or_deltas(self) -> None:
        dispatcher = WebhookDispatcher(urls=[])
        assert await dispatcher.dispatch({"test": "data"}) == []
        assert await dispatcher.dispatch_deltas([]) == []
        assert await dispatcher.dispatch_run_summary(
            ScrapeRunSummary(run_id="1", term="2024/2025-1")
        ) == []
        await dispatcher.aclose()
