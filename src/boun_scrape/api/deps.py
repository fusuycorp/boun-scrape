"""Dependency injection providers for FastAPI endpoints."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from boun_scrape.api.logging_buffer import LogBuffer, get_global_log_buffer
from boun_scrape.config import Settings, get_settings
from boun_scrape.feeds.webhooks import WebhookDispatcher
from boun_scrape.scheduler.runner import ScrapeScheduler
from boun_scrape.scraper.client import BounScraperClient
from boun_scrape.scraper.quota import QuotaService
from boun_scrape.storage.database import DatabaseManager
from boun_scrape.storage.repository import CourseRepository


def get_settings_dep(request: Request) -> Settings:
    """Provide application settings, checking app.state first."""
    if hasattr(request, "app") and hasattr(request.app.state, "settings") and request.app.state.settings is not None:
        return request.app.state.settings
    return get_settings()


@lru_cache
def _get_shared_db_manager(db_path: str) -> DatabaseManager:
    """Internal singleton DatabaseManager factory."""
    db = DatabaseManager(db_path)
    db.init_db()
    return db


def get_db_manager_dep(
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> DatabaseManager:
    """Provide initialized DatabaseManager."""
    return _get_shared_db_manager(settings.db_path)


def get_course_repo_dep(
    db: Annotated[DatabaseManager, Depends(get_db_manager_dep)],
) -> CourseRepository:
    """Provide CourseRepository instance."""
    return CourseRepository(db)


@lru_cache
def _get_shared_scraper_client() -> BounScraperClient:
    """Internal singleton BounScraperClient factory."""
    return BounScraperClient(settings=get_settings())


def get_scraper_client_dep(
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> BounScraperClient:
    """Provide BounScraperClient instance."""
    return _get_shared_scraper_client()


@lru_cache
def _get_shared_quota_service() -> QuotaService:
    """Internal singleton QuotaService factory."""
    client = _get_shared_scraper_client()
    return QuotaService(client=client, settings=get_settings())


def get_quota_service_dep(
    client: Annotated[BounScraperClient, Depends(get_scraper_client_dep)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> QuotaService:
    """Provide QuotaService instance."""
    return _get_shared_quota_service()


@lru_cache
def _get_shared_webhook_dispatcher() -> WebhookDispatcher:
    """Internal singleton WebhookDispatcher factory."""
    return WebhookDispatcher(settings=get_settings())


def get_webhook_dispatcher_dep(
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> WebhookDispatcher:
    """Provide WebhookDispatcher instance."""
    return _get_shared_webhook_dispatcher()


@lru_cache
def _get_shared_scheduler() -> ScrapeScheduler:
    """Internal singleton ScrapeScheduler factory."""
    settings = get_settings()
    db = _get_shared_db_manager(settings.db_path)
    repo = CourseRepository(db)
    client = _get_shared_scraper_client()
    dispatcher = _get_shared_webhook_dispatcher()
    return ScrapeScheduler(
        client=client,
        repository=repo,
        webhook_dispatcher=dispatcher,
        export_dir=settings.export_dir,
        settings=settings,
    )


def get_scrape_scheduler_dep(
    client: Annotated[BounScraperClient, Depends(get_scraper_client_dep)],
    repo: Annotated[CourseRepository, Depends(get_course_repo_dep)],
    dispatcher: Annotated[WebhookDispatcher, Depends(get_webhook_dispatcher_dep)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> ScrapeScheduler:
    """Provide ScrapeScheduler instance."""
    return _get_shared_scheduler()


def get_log_buffer_dep() -> LogBuffer:
    """Provide LogBuffer instance."""
    return get_global_log_buffer()


# Aliases for convenience
get_repository = get_course_repo_dep
get_db_manager = get_db_manager_dep
get_quota_service = get_quota_service_dep
get_scheduler = get_scrape_scheduler_dep
get_log_buffer = get_log_buffer_dep
get_scraper_client = get_scraper_client_dep
get_webhook_dispatcher = get_webhook_dispatcher_dep
