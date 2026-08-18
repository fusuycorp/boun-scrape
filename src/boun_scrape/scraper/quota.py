"""Live quota scraper service with in-memory TTL caching and concurrent batch fetching."""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Self

logger = logging.getLogger(__name__)

from boun_scrape.config import Settings, get_settings
from boun_scrape.domain.models import QuotaRecord
from boun_scrape.scraper.client import BounScraperClient
from boun_scrape.scraper.parser import parse_quota_from_html


def format_course_key(abbr: str, code: str, section: str) -> str:
    """Format a canonical composite course identifier (e.g. 'CMPE 150.01')."""
    abbr_clean = abbr.strip().upper()
    code_clean = code.strip().upper()
    sec_clean = section.strip()

    if code_clean.startswith(abbr_clean):
        base = code_clean
    else:
        base = f"{abbr_clean} {code_clean}".strip()

    if sec_clean:
        return f"{base}.{sec_clean}"
    return base


@dataclass(slots=True, kw_only=True)
class _QuotaCacheEntry:
    """Internal cache entry with timestamp and parsed quota records."""

    timestamp: float
    records: list[QuotaRecord]


class QuotaService:
    """Service for fetching real-time course quota information with TTL caching."""

    def __init__(
        self,
        client: BounScraperClient | None = None,
        ttl_seconds: float = 30.0,
        quota_url: str | None = None,
        max_cache_size: int = 2000,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self.ttl_seconds = ttl_seconds
        self.max_cache_size = max_cache_size
        self.quota_url = quota_url or f"{cfg.quota_url.rstrip('/')}/scripts/quotasearch.asp"

        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = BounScraperClient(settings=cfg)
            self._owns_client = True

        self._cache: dict[str, _QuotaCacheEntry] = {}
        self._lock = asyncio.Lock()

    @property
    def client(self) -> BounScraperClient:
        """Access the underlying scraper client."""
        return self._client

    @property
    def cache_size(self) -> int:
        """Return the count of distinct cached quota queries."""
        return len(self._cache)

    def clear_cache(self) -> None:
        """Purge all cached quota records."""
        self._cache.clear()

    def _make_cache_key(self, term: str, abbr: str, code: str, section: str) -> str:
        return f"{term.strip()}:{abbr.strip().upper()}:{code.strip().upper()}:{section.strip()}"

    async def fetch_quota(
        self,
        term: str,
        abbr: str,
        code: str,
        section: str,
        bypass_cache: bool = False,
    ) -> list[QuotaRecord]:
        """Fetch quota records for a specific course section.

        Args:
            term: Academic term string (e.g. '2024/2025-1').
            abbr: Department abbreviation (e.g. 'CMPE').
            code: Course code (e.g. '150' or 'CMPE 150').
            section: Course section (e.g. '01').
            bypass_cache: If True, bypass cache and query the registration portal directly.

        Returns:
            List of QuotaRecord entities parsed from server response.
        """
        cache_key = self._make_cache_key(term, abbr, code, section)
        now = time.monotonic()

        if not bypass_cache:
            async with self._lock:
                entry = self._cache.get(cache_key)
                if entry is not None and (now - entry.timestamp) < self.ttl_seconds:
                    return list(entry.records)

        # Normalize query parameters for quotasearch.asp
        query_code = code.strip().upper()
        clean_abbr = abbr.strip().upper()
        if query_code.startswith(clean_abbr):
            query_code = query_code[len(clean_abbr) :].strip()

        params = {
            "donem": term.strip(),
            "abbr": clean_abbr,
            "code": query_code,
            "section": section.strip(),
        }

        response = await self._client.get(self.quota_url, params=params)
        records = parse_quota_from_html(response.text)

        async with self._lock:
            # Bound cache growth in a long-lived daemon: evict the oldest entry once
            # the cap is exceeded. O(cache) eviction runs only when at capacity, which
            # is rare compared to the TTL-hit fast path. ponytail: linear eviction;
            # upgrade to a heap/OrderedDict if the cap ever grows into the tens of
            # thousands of live entries.
            if (
                self.max_cache_size
                and len(self._cache) >= self.max_cache_size
                and cache_key not in self._cache
            ):
                oldest = min(self._cache, key=lambda k: self._cache[k].timestamp)
                del self._cache[oldest]
            self._cache[cache_key] = _QuotaCacheEntry(
                timestamp=time.monotonic(),
                records=records,
            )

        return records

    async def fetch_batch_quotas(
        self,
        items: list[tuple[str, str, str, str]],
        concurrency: int = 5,
        bypass_cache: bool = False,
    ) -> dict[str, list[QuotaRecord]]:
        """Fetch quota records for multiple courses concurrently.

        Args:
            items: List of (term, abbr, code, section) tuples.
            concurrency: Maximum number of concurrent network requests.
            bypass_cache: If True, bypass in-memory cache.

        Returns:
            Dictionary mapping canonical course key (e.g. 'CMPE 150.01') to quota records.
        """
        if not items:
            return {}

        sem = asyncio.Semaphore(max(1, concurrency))

        async def _fetch_single(
            term: str, abbr: str, code: str, section: str
        ) -> list[QuotaRecord]:
            async with sem:
                return await self.fetch_quota(
                    term=term,
                    abbr=abbr,
                    code=code,
                    section=section,
                    bypass_cache=bypass_cache,
                )

        keys = [format_course_key(a, c, s) for _, a, c, s in items]
        results = await asyncio.gather(
            *[_fetch_single(t, a, c, s) for t, a, c, s in items],
            return_exceptions=True,
        )

        output: dict[str, list[QuotaRecord]] = {}
        for key, result in zip(keys, results):
            if isinstance(result, BaseException):
                logger.warning("Batch quota lookup failed for %s: %s", key, result)
                output[key] = []
                continue
            output[key] = result
        return output

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
        """Close underlying HTTP client if owned by this service."""
        if self._owns_client:
            await self._client.aclose()
