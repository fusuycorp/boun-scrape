"""In-memory per-IP sliding-window rate limiting for unauthenticated endpoints.

Single-process only (no shared state across workers) — sufficient for this
service's single-worker deployment. Not a substitute for edge/WAF rate limiting.

Limiter instances are scoped per FastAPI app (stored on `app.state`, created in
`create_app()`), not module-level globals, so distinct app instances (e.g. one
per test) don't leak rate-limit state into each other.
"""

import time
from collections import deque

from fastapi import HTTPException, Request, status

TRUSTED_PROXIES = {"127.0.0.1", "::1", "localhost", "testclient"}


class RateLimiter:
    """Sliding-window rate limiter keyed by client IP."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def check(self, client_ip: str) -> None:
        now = time.monotonic()
        hits = self._hits.get(client_ip)
        if hits is not None:
            while hits and now - hits[0] > self.window_seconds:
                hits.popleft()
            if not hits:
                del self._hits[client_ip]
                hits = None

        if hits is not None and len(hits) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )

        if hits is None:
            hits = deque()
            self._hits[client_ip] = hits

        hits.append(now)


def _get_client_ip(request: Request) -> str:
    if request.client and request.client.host in TRUSTED_PROXIES:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
            if client_ip:
                return client_ip
    return request.client.host if request.client else "unknown"


_client_ip = _get_client_ip


def login_rate_limit_dep(request: Request) -> None:
    """FastAPI dependency: enforce the app's login rate limiter."""
    request.app.state.login_rate_limiter.check(_get_client_ip(request))


def quota_rate_limit_dep(request: Request) -> None:
    """FastAPI dependency: enforce the app's quota rate limiter."""
    request.app.state.quota_rate_limiter.check(_get_client_ip(request))
