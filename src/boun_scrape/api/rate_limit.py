"""In-memory per-IP sliding-window rate limiting for unauthenticated endpoints.

Single-process only (no shared state across workers) — sufficient for this
service's single-worker deployment. Not a substitute for edge/WAF rate limiting.

Limiter instances are scoped per FastAPI app (stored on `app.state`, created in
`create_app()`), not module-level globals, so distinct app instances (e.g. one
per test) don't leak rate-limit state into each other.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Sliding-window rate limiter keyed by client IP."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client_ip: str) -> None:
        now = time.monotonic()
        hits = self._hits[client_ip]
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()

        if len(hits) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )

        hits.append(now)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def login_rate_limit_dep(request: Request) -> None:
    """FastAPI dependency: enforce the app's login rate limiter."""
    request.app.state.login_rate_limiter.check(_client_ip(request))


def quota_rate_limit_dep(request: Request) -> None:
    """FastAPI dependency: enforce the app's quota rate limiter."""
    request.app.state.quota_rate_limiter.check(_client_ip(request))
