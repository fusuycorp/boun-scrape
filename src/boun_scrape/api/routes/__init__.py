"""API route definitions."""

from boun_scrape.api.routes.courses import router as courses_router
from boun_scrape.api.routes.feeds import router as feeds_router
from boun_scrape.api.routes.quota import router as quota_router
from boun_scrape.api.routes.scraper import router as scraper_router
from boun_scrape.api.routes.legacy import router as legacy_router

__all__ = ["courses_router", "feeds_router", "quota_router", "scraper_router", "legacy_router"]
