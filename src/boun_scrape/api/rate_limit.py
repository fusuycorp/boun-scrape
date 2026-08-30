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
        self._last_pruned: float = time.monotonic()

    def _prune_expired(self, now: float) -> None:
        """Purge stale deques for inactive clients to prevent memory leaks."""
        expired_ips = [
            ip for ip, queue in self._hits.items()
            if not queue or now - queue[-1] > self.window_seconds
        ]
        for ip in expired_ips:
            self._hits.pop(ip, None)
        self._last_pruned = now

    def check(self, client_ip: str) -> None:
        now = time.monotonic()

        # Periodically prune stale inactive IPs
        if now - self._last_pruned > max(10.0, self.window_seconds) or len(self._hits) > 500:
            self._prune_expired(now)

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
    """Extract real client IP, parsing proxy chains right-to-left if peer is trusted."""
    if not request.client:
        return "unknown"

    peer_host = request.client.host
    if peer_host not in TRUSTED_PROXIES:
        return peer_host

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Split into list of IPs in proxy traversal order: [client, proxy1, proxy2]
        ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        # Walk right-to-left: discard trusted reverse proxies from the end of the chain
        for ip in reversed(ips):
            if ip not in TRUSTED_PROXIES:
                return ip

    return peer_host


_client_ip = _get_client_ip


def login_rate_limit_dep(request: Request) -> None:
    """FastAPI dependency: enforce the app's login rate limiter."""
    request.app.state.login_rate_limiter.check(_get_client_ip(request))


def quota_rate_limit_dep(request: Request) -> None:
    """FastAPI dependency: enforce the app's quota rate limiter."""
    request.app.state.quota_rate_limiter.check(_get_client_ip(request))
