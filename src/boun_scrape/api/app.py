"""FastAPI application factory, CORS configuration, and exception handlers."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from boun_scrape.api.logging_buffer import setup_api_logging
from boun_scrape.api.routes import (
    courses_router,
    feeds_router,
    quota_router,
    scraper_router,
    legacy_router,
)
from boun_scrape.config import Settings, get_settings
from boun_scrape.domain.dto import HealthCheckDTO
from boun_scrape.scheduler.runner import (
    ScrapeAlreadyRunningError,
    ScrapeSchedulerError,
)
from boun_scrape.storage.database import DatabaseManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle context manager."""
    # Ensure database schema is initialized on startup
    settings: Settings = getattr(app.state, "settings", get_settings())
    db = DatabaseManager(settings.db_path)
    db.init_db()
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    cfg = settings or get_settings()

    # Setup buffered logging
    setup_api_logging()

    app = FastAPI(
        title="boun-scrape API",
        description="High-performance automated scraper, change detector, and feed provider for Boğaziçi University registration data.",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.state.settings = cfg

    # Configure CORS middleware
    origins = cfg.allowed_origins or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True if origins != ["*"] else False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint for Dokploy Swarm and Docker healthchecks
    @app.get(
        "/",
        response_model=HealthCheckDTO,
        summary="Service health check",
        tags=["Health"],
    )
    def health_check() -> HealthCheckDTO:
        """Return operational health status, service name, and version."""
        return HealthCheckDTO(
            status="ok",
            service="boun-scrape",
            version="0.2.0",
        )

    # Global exception handlers
    @app.exception_handler(ScrapeAlreadyRunningError)
    async def scrape_already_running_handler(
        request: Request, exc: ScrapeAlreadyRunningError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ScrapeSchedulerError)
    async def scrape_scheduler_error_handler(
        request: Request, exc: ScrapeSchedulerError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request, exc: ValueError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    # Mount API v1 route modules
    app.include_router(courses_router, prefix="/api/v1")
    app.include_router(quota_router, prefix="/api/v1")
    app.include_router(feeds_router, prefix="/api/v1")
    app.include_router(scraper_router, prefix="/api/v1")

    # Mount legacy compatibility router for existing frontend dashboard
    app.include_router(legacy_router, prefix="/api")

    return app
