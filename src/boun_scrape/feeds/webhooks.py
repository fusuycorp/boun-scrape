"""HMAC-signed asynchronous webhook dispatcher for downstream consumers."""

import asyncio
import hashlib
import hmac
import json
import logging
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from typing import Any, Self

import httpx
from pydantic import BaseModel

from boun_scrape.config import Settings, get_settings
from boun_scrape.domain.events import CourseDeltaEvent
from boun_scrape.domain.models import ScrapeRunSummary

logger = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class WebhookDeliveryResult:
    """Result of a webhook delivery attempt to a target endpoint."""

    url: str
    success: bool
    status_code: int | None = None
    attempts: int = 1
    error_message: str | None = None


def compute_hmac_signature(secret: str, payload_bytes: bytes) -> str:
    """Compute HMAC-SHA256 signature for webhook payload."""
    h = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256)
    return h.hexdigest()


def serialize_webhook_payload(payload: Any) -> bytes:
    """Deterministic JSON byte serialization for webhook payloads."""
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    if isinstance(payload, BaseModel):
        return payload.model_dump_json().encode("utf-8")
    if isinstance(payload, CourseDeltaEvent):
        data = {
            "change_type": payload.change_type.value if hasattr(payload.change_type, "value") else str(payload.change_type),
            "term": payload.term,
            "department": payload.department,
            "course_code": payload.course_code,
            "section": payload.section,
            "timestamp": payload.timestamp,
            "old_value": payload.old_value,
            "new_value": payload.new_value,
            "details": payload.details,
        }
        return json.dumps(data, ensure_ascii=False).encode("utf-8")
    if isinstance(payload, ScrapeRunSummary):
        data = {
            "run_id": payload.run_id,
            "term": payload.term,
            "status": payload.status.value if hasattr(payload.status, "value") else str(payload.status),
            "total_departments": payload.total_departments,
            "total_courses": payload.total_courses,
            "total_slots": payload.total_slots,
            "changes_detected": payload.changes_detected,
            "started_at": payload.started_at,
            "completed_at": payload.completed_at,
            "error_message": payload.error_message,
        }
        return json.dumps(data, ensure_ascii=False).encode("utf-8")
    if is_dataclass(payload) and not isinstance(payload, type):
        return json.dumps(asdict(payload), ensure_ascii=False).encode("utf-8")
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")

    return json.dumps(str(payload)).encode("utf-8")


class WebhookDispatcher:
    """Asynchronous HTTP dispatcher with HMAC-SHA256 signing and retry backoff."""

    def __init__(
        self,
        urls: list[str] | str | None = None,
        webhook_secret: str | None = None,
        max_retries: int = 3,
        timeout: float = 10.0,
        backoff_factor: float = 0.5,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        cfg = settings or get_settings()

        if urls is None:
            self.urls: list[str] = []
        elif isinstance(urls, str):
            self.urls = [u.strip() for u in urls.split(",") if u.strip()]
        else:
            self.urls = list(urls)

        self.webhook_secret = (
            webhook_secret if webhook_secret is not None else cfg.webhook_secret
        )
        self.max_retries = max(1, max_retries)
        self.timeout = timeout
        self.backoff_factor = backoff_factor

        if http_client is not None:
            self._client = http_client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
            self._owns_client = True

    async def _send_to_single_url(
        self,
        url: str,
        payload_bytes: bytes,
        headers: dict[str, str],
    ) -> WebhookDeliveryResult:
        """Send payload to a single URL with exponential backoff retry."""
        last_error: str | None = None
        last_status_code: int | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self._client.post(
                    url,
                    content=payload_bytes,
                    headers=headers,
                )
                last_status_code = response.status_code
                if response.status_code < 400:
                    return WebhookDeliveryResult(
                        url=url,
                        success=True,
                        status_code=response.status_code,
                        attempts=attempt,
                    )

                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = f"{type(exc).__name__}: {str(exc)}"

            if attempt < self.max_retries:
                delay = self.backoff_factor * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        return WebhookDeliveryResult(
            url=url,
            success=False,
            status_code=last_status_code,
            attempts=self.max_retries,
            error_message=last_error,
        )

    async def dispatch(
        self,
        payload: Any,
        event_type: str = "custom",
    ) -> list[WebhookDeliveryResult]:
        """Dispatch payload to all configured webhook endpoints concurrently.

        Args:
            payload: Data payload to deliver (CourseDeltaEvent, ScrapeRunSummary, dict, etc.).
            event_type: Event type identifier sent in headers / envelope.

        Returns:
            List of WebhookDeliveryResult outcomes.
        """
        if not self.urls:
            return []

        payload_bytes = serialize_webhook_payload(payload)

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": "boun-scrape-webhook-dispatcher/0.2.0",
            "X-Boun-Event": event_type,
            "X-Boun-Timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self.webhook_secret:
            sig = compute_hmac_signature(self.webhook_secret, payload_bytes)
            headers["X-Boun-Signature"] = f"sha256={sig}"
        else:
            logger.warning(
                "Dispatching webhook(s) to %d URL(s) without WEBHOOK_SECRET set — "
                "payloads will be unsigned. Set WEBHOOK_SECRET to enable integrity verification.",
                len(self.urls),
            )

        tasks = [
            self._send_to_single_url(url, payload_bytes, headers)
            for url in self.urls
        ]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def dispatch_deltas(
        self,
        deltas: list[CourseDeltaEvent],
        term: str | None = None,
    ) -> list[WebhookDeliveryResult]:
        """Dispatch detected course changes envelope to webhooks."""
        if not deltas or not self.urls:
            return []

        envelope = {
            "event": "courses.deltas",
            "term": term or (deltas[0].term if deltas else ""),
            "count": len(deltas),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "deltas": [
                {
                    "change_type": d.change_type.value if hasattr(d.change_type, "value") else str(d.change_type),
                    "term": d.term,
                    "department": d.department,
                    "course_code": d.course_code,
                    "section": d.section,
                    "timestamp": d.timestamp,
                    "old_value": d.old_value,
                    "new_value": d.new_value,
                    "details": d.details,
                }
                for d in deltas
            ],
        }
        return await self.dispatch(envelope, event_type="courses.deltas")

    async def dispatch_run_summary(
        self,
        summary: ScrapeRunSummary,
    ) -> list[WebhookDeliveryResult]:
        """Dispatch scrape execution summary envelope to webhooks."""
        if not self.urls:
            return []

        envelope = {
            "event": "scrape.summary",
            "run_id": summary.run_id,
            "term": summary.term,
            "status": summary.status.value if hasattr(summary.status, "value") else str(summary.status),
            "total_courses": summary.total_courses,
            "total_slots": summary.total_slots,
            "changes_detected": summary.changes_detected,
            "started_at": summary.started_at,
            "completed_at": summary.completed_at,
            "error_message": summary.error_message,
        }
        return await self.dispatch(envelope, event_type="scrape.summary")

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close underlying HTTP client if owned by this dispatcher."""
        if self._owns_client:
            await self._client.aclose()
