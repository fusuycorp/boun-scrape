"""Resilient HTTP client for Boğaziçi University registration portal."""

import asyncio
import os
import random
from pathlib import Path
from typing import Any, Self

import httpx

from boun_scrape.config import Settings, get_settings

DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

RECAPTCHA_ERROR_MARKER = "You could not pass the reCAPTCHA check"


class BounError(Exception):
    """Base exception for all boun-scrape errors."""


class RecaptchaBlockedError(BounError):
    """Raised when Boğaziçi registration server blocks the request with reCAPTCHA."""


class BounHttpError(BounError):
    """Raised on non-recoverable HTTP or transport errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class SessionExpiredError(BounError):
    """Raised when authentication session or cookies are expired."""


def parse_cookie_text(content: str) -> dict[str, str]:
    """Parse cookies from Netscape format, curl exports, or key=value lines."""
    cookies: dict[str, str] = {}
    if not content:
        return cookies

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        # Handle Netscape HTTP Cookie file format
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_") :]
        elif line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) >= 7:
            # Domain, flag, path, secure, expiration, name, value
            name = parts[5].strip()
            value = parts[6].strip()
            if name:
                cookies[name] = value
            continue

        # Handle semicolon separated key=val strings (e.g. cookie header)
        if ";" in line:
            for item in line.split(";"):
                if "=" in item:
                    k, v = item.strip().split("=", 1)
                    if k.strip():
                        cookies[k.strip()] = v.strip()
            continue

        # Handle single key=val per line
        if "=" in line:
            k, v = line.split("=", 1)
            if k.strip():
                cookies[k.strip()] = v.strip()

    return cookies


def parse_cookie_file(file_path: str | Path) -> dict[str, str]:
    """Load and parse cookies from a file path if it exists."""
    path = Path(file_path)
    if not path.is_file():
        return {}
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        return parse_cookie_text(content)
    except OSError:
        return {}


def decode_windows_1254(content: bytes) -> str:
    """Decode raw bytes into string using windows-1254 encoding."""
    return content.decode("windows-1254", errors="replace")


class BounScraperClient:
    """Asynchronous HTTP client tailored for Boğaziçi University portals."""

    def __init__(
        self,
        base_url: str | None = None,
        cookies_path: str | None = None,
        timeout: float | None = None,
        max_concurrency: int | None = None,
        min_jitter: float | None = None,
        max_jitter: float | None = None,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        cfg = settings or get_settings()

        self.base_url = (base_url or cfg.base_url).rstrip("/")
        self.cookies_path = cookies_path if cookies_path is not None else cfg.cookies_path
        self.timeout = timeout if timeout is not None else cfg.request_timeout
        self.max_concurrency = (
            max_concurrency if max_concurrency is not None else cfg.max_concurrency
        )
        self.min_jitter = min_jitter if min_jitter is not None else cfg.min_jitter
        self.max_jitter = max_jitter if max_jitter is not None else cfg.max_jitter

        # Parse initial cookies
        initial_cookies = parse_cookie_file(self.cookies_path) if self.cookies_path else {}

        if http_client is not None:
            self._client = http_client
            if initial_cookies:
                self._client.cookies.update(initial_cookies)
            self._owns_client = False
        else:
            limits = httpx.Limits(
                max_connections=self.max_concurrency * 2,
                max_keepalive_connections=self.max_concurrency,
            )
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=DEFAULT_HEADERS,
                cookies=initial_cookies,
                timeout=httpx.Timeout(self.timeout),
                limits=limits,
                follow_redirects=True,
            )
            self._owns_client = True

    @property
    def cookies(self) -> httpx.Cookies:
        """Access the client's cookie jar."""
        return self._client.cookies

    async def __aenter__(self) -> Self:
        """Async context manager enter."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client session."""
        if self._owns_client:
            await self._client.aclose()

    async def _apply_jitter(self) -> None:
        """Apply a slight randomized jitter to prevent burst hammering."""
        if self.max_jitter > 0 and self.max_jitter >= self.min_jitter:
            delay = random.uniform(self.min_jitter, self.max_jitter)
            if delay > 0:
                await asyncio.sleep(delay)

    def _process_response(self, response: httpx.Response) -> httpx.Response:
        """Validate response encoding and inspect for security challenges."""
        response.encoding = "windows-1254"
        text = response.text

        if RECAPTCHA_ERROR_MARKER in text:
            raise RecaptchaBlockedError(
                "Boğaziçi registration server blocked the request with reCAPTCHA. "
                "Please update cookies.txt with an active session."
            )

        return response

    async def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retries: int = 3,
    ) -> httpx.Response:
        """Perform a GET request with jitter, retries, and encoding handling."""
        last_exception: Exception | None = None

        for attempt in range(1, retries + 1):
            await self._apply_jitter()
            try:
                response = await self._client.get(url, params=params, headers=headers)
                if response.status_code >= 500:
                    raise BounHttpError(
                        f"Server error {response.status_code} requesting {url}",
                        status_code=response.status_code,
                    )
                if response.status_code >= 400:
                    raise BounHttpError(
                        f"HTTP {response.status_code} error requesting {url}",
                        status_code=response.status_code,
                    )
                return self._process_response(response)
            except RecaptchaBlockedError:
                raise
            except (httpx.TransportError, httpx.TimeoutException, BounHttpError) as err:
                last_exception = err
                if attempt < retries:
                    backoff = (2 ** (attempt - 1)) * 0.5 + random.uniform(0.05, 0.2)
                    await asyncio.sleep(backoff)
                else:
                    break

        if isinstance(last_exception, BounHttpError):
            raise last_exception
        raise BounHttpError(
            f"Failed GET request to {url} after {retries} attempts: {last_exception}"
        ) from last_exception

    async def post(
        self,
        url: str,
        *,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retries: int = 3,
    ) -> httpx.Response:
        """Perform a POST request with jitter, retries, and encoding handling."""
        last_exception: Exception | None = None

        for attempt in range(1, retries + 1):
            await self._apply_jitter()
            try:
                response = await self._client.post(
                    url, data=data, params=params, headers=headers
                )
                if response.status_code >= 500:
                    raise BounHttpError(
                        f"Server error {response.status_code} posting to {url}",
                        status_code=response.status_code,
                    )
                if response.status_code >= 400:
                    raise BounHttpError(
                        f"HTTP {response.status_code} error posting to {url}",
                        status_code=response.status_code,
                    )
                return self._process_response(response)
            except RecaptchaBlockedError:
                raise
            except (httpx.TransportError, httpx.TimeoutException, BounHttpError) as err:
                last_exception = err
                if attempt < retries:
                    backoff = (2 ** (attempt - 1)) * 0.5 + random.uniform(0.05, 0.2)
                    await asyncio.sleep(backoff)
                else:
                    break

        if isinstance(last_exception, BounHttpError):
            raise last_exception
        raise BounHttpError(
            f"Failed POST request to {url} after {retries} attempts: {last_exception}"
        ) from last_exception
