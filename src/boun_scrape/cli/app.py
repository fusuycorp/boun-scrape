"""Typer Command Line Interface for boun-scrape."""

import asyncio
from pathlib import Path
import signal
from typing import Annotated

import typer
import uvicorn

from boun_scrape.config import Settings, get_settings
from boun_scrape.domain.models import RunStatus
from boun_scrape.feeds.webhooks import WebhookDispatcher
from boun_scrape.pipeline.exporter import (
    _sanitize_term,
    export_courses_csv,
    export_courses_json,
    export_courses_sqlite,
    generate_all_exports,
)
from boun_scrape.scheduler.runner import ScrapeScheduler
from boun_scrape.scraper.client import BounScraperClient
from boun_scrape.scraper.flow import discover_terms
from boun_scrape.scraper.quota import QuotaService
from boun_scrape.storage.database import DatabaseManager
from boun_scrape.storage.repository import CourseRepository

app = typer.Typer(
    name="boun-scrape",
    help="High-performance automated scraper, change detector, and feed provider for Boğaziçi University registration data.",
    add_completion=False,
)


@app.command(name="scrape")
def scrape_command(
    term: Annotated[
        str | None,
        typer.Option("--term", "-t", help="Academic term identifier (e.g. '2024/2025-1')"),
    ] = None,
    no_export: Annotated[
        bool,
        typer.Option("--no-export", help="Disable generation of JSON, CSV, and SQLite artifacts"),
    ] = False,
    no_webhooks: Annotated[
        bool,
        typer.Option("--no-webhooks", help="Disable outbound webhook notifications"),
    ] = False,
    db_path: Annotated[
        str | None,
        typer.Option("--db", help="Override SQLite database path"),
    ] = None,
) -> None:
    """Execute an immediate full scrape cycle for the specified term."""
    cfg = get_settings()
    actual_db = db_path or cfg.db_path
    db_mgr = DatabaseManager(actual_db)
    db_mgr.init_db()
    repo = CourseRepository(db_mgr)
    client = BounScraperClient(settings=cfg)
    dispatcher = WebhookDispatcher(settings=cfg) if not no_webhooks else None

    scheduler = ScrapeScheduler(
        client=client,
        repository=repo,
        webhook_dispatcher=dispatcher,
        export_dir=cfg.export_dir,
        settings=cfg,
    )

    typer.secho("Initiating scraping cycle...", fg=typer.colors.CYAN)

    async def _run() -> None:
        try:
            summary = await scheduler.execute_scrape_cycle(
                term=term,
                export=not no_export,
                dispatch_webhooks=not no_webhooks,
            )
            typer.secho(f"\nScrape cycle completed successfully! [Run: {summary.run_id}]", fg=typer.colors.GREEN, bold=True)
            typer.echo(f"  Term:                {summary.term}")
            typer.echo(f"  Status:              {summary.status.value if isinstance(summary.status, RunStatus) else summary.status}")
            typer.echo(f"  Total Courses:       {summary.total_courses}")
            typer.echo(f"  Total Slots:         {summary.total_slots}")
            typer.echo(f"  Changes Detected:    {summary.changes_detected}")
            typer.echo(f"  Started At:          {summary.started_at}")
            typer.echo(f"  Completed At:        {summary.completed_at}")
        finally:
            await scheduler.aclose()

    asyncio.run(_run())


@app.command(name="serve")
def serve_command(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host interface to bind to"),
    ] = "0.0.0.0",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port number to listen on"),
    ] = 8000,
    reload: Annotated[
        bool,
        typer.Option("--reload", "-r", help="Enable auto-reload on code modifications"),
    ] = False,
) -> None:
    """Run the FastAPI REST API server."""
    typer.secho(f"Starting boun-scrape API server on http://{host}:{port}", fg=typer.colors.CYAN, bold=True)
    uvicorn.run(
        "boun_scrape.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )


@app.command(name="daemon")
def daemon_command(
    interval: Annotated[
        int,
        typer.Option("--interval", "-i", help="Interval seconds between scrape runs"),
    ] = 3600,
    cron: Annotated[
        str | None,
        typer.Option("--cron", "-c", help="Cron schedule expression (e.g. '0 */2 * * *')"),
    ] = None,
    term: Annotated[
        str | None,
        typer.Option("--term", "-t", help="Fixed academic term to scrape"),
    ] = None,
    db_path: Annotated[
        str | None,
        typer.Option("--db", help="Override SQLite database path"),
    ] = None,
) -> None:
    """Run the background scheduler daemon for periodic scraping and change feeds."""
    cfg = get_settings()
    actual_db = db_path or cfg.db_path
    db_mgr = DatabaseManager(actual_db)
    db_mgr.init_db()
    repo = CourseRepository(db_mgr)
    client = BounScraperClient(settings=cfg)
    dispatcher = WebhookDispatcher(settings=cfg)

    scheduler = ScrapeScheduler(
        interval_seconds=interval,
        cron_expression=cron,
        client=client,
        repository=repo,
        webhook_dispatcher=dispatcher,
        export_dir=cfg.export_dir,
        default_term=term,
        settings=cfg,
    )

    typer.secho(
        f"Starting scheduler daemon (interval={interval}s, cron={cron}, term={term})...",
        fg=typer.colors.CYAN,
        bold=True,
    )

    async def _daemon_loop() -> None:
        scheduler.start()
        stop_event = asyncio.Event()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop_event.set)
            except NotImplementedError:
                # Signal handlers not implemented on Windows
                pass

        try:
            await stop_event.wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            typer.secho("\nShutting down scheduler daemon...", fg=typer.colors.YELLOW)
            await scheduler.aclose()

    try:
        asyncio.run(_daemon_loop())
    except KeyboardInterrupt:
        typer.secho("\nScheduler daemon stopped.", fg=typer.colors.YELLOW)


@app.command(name="export")
def export_command(
    term: Annotated[
        str,
        typer.Option("--term", "-t", help="Academic term identifier (e.g. '2024/2025-1')"),
    ],
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="Export format: json, csv, sqlite, or all"),
    ] = "all",
    output_dir: Annotated[
        str,
        typer.Option("--output-dir", "-o", help="Destination output directory"),
    ] = "exports",
    db_path: Annotated[
        str | None,
        typer.Option("--db", help="Override SQLite database path"),
    ] = None,
) -> None:
    """Export persisted course schedules into structured data artifacts."""
    cfg = get_settings()
    actual_db = db_path or cfg.db_path
    db_mgr = DatabaseManager(actual_db)
    db_mgr.init_db()
    repo = CourseRepository(db_mgr)

    courses = repo.get_courses_by_term(term)
    if not courses:
        typer.secho(
            f"No courses found in database for term '{term}'. Run `boun-scrape scrape --term {term}` first.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    fmt = format.lower().strip()
    safe_term = _sanitize_term(term)

    if fmt == "json":
        p = export_courses_json(courses, out_path / f"courses_{safe_term}.json")
        typer.secho(f"Exported JSON: {p}", fg=typer.colors.GREEN)
    elif fmt == "csv":
        p = export_courses_csv(courses, out_path / f"courses_{safe_term}.csv")
        typer.secho(f"Exported CSV: {p}", fg=typer.colors.GREEN)
    elif fmt in ("sqlite", "db"):
        p = export_courses_sqlite(term, courses, out_path / f"courses_{safe_term}.db")
        typer.secho(f"Exported SQLite: {p}", fg=typer.colors.GREEN)
    elif fmt == "all":
        exported = generate_all_exports(term=term, courses=courses, output_dir=out_path)
        typer.secho("Exported all artifacts:", fg=typer.colors.GREEN, bold=True)
        for key, p in exported.items():
            typer.echo(f"  - {key.upper()}: {p}")
    else:
        typer.secho(
            f"Invalid format '{format}'. Supported formats: json, csv, sqlite, all",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


@app.command(name="quota")
def quota_command(
    abbr: Annotated[
        str,
        typer.Option("--abbr", "-a", help="Department abbreviation (e.g. 'CMPE')"),
    ],
    code: Annotated[
        str,
        typer.Option("--code", "-c", help="Course code (e.g. '150' or 'CMPE 150')"),
    ] = "",
    section: Annotated[
        str,
        typer.Option("--section", "-s", help="Course section (e.g. '01')"),
    ] = "",
    term: Annotated[
        str | None,
        typer.Option("--term", "-t", help="Academic term (defaults to latest available)"),
    ] = None,
    bypass_cache: Annotated[
        bool,
        typer.Option("--bypass-cache", help="Bypass cached quota values"),
    ] = False,
) -> None:
    """Fetch live course quota capacity from the registration portal."""
    cfg = get_settings()
    client = BounScraperClient(settings=cfg)
    quota_service = QuotaService(client=client, settings=cfg)

    async def _fetch() -> None:
        try:
            target_term = term
            if not target_term:
                discovered = await discover_terms(client)
                target_term = discovered[0] if discovered else "current"

            records = await quota_service.fetch_quota(
                term=target_term,
                abbr=abbr,
                code=code,
                section=section,
                bypass_cache=bypass_cache,
            )

            if not records:
                typer.secho(
                    f"No quota records returned for {abbr} {code} sec {section} (term: {target_term}).",
                    fg=typer.colors.YELLOW,
                )
                return

            typer.secho(f"\nQuota records for {abbr} {code} (Section: {section or 'ALL'}, Term: {target_term}):", fg=typer.colors.CYAN, bold=True)
            typer.echo(f"{'Department':<35} | {'Status':<10} | {'Quota':<10} | {'Current':<10} | {'Available':<10}")
            typer.echo("-" * 85)
            for r in records:
                avail_str = str(r.available) if r.available is not None else ("Unlimited" if r.is_unlimited else ("Consent" if r.is_consent else "N/A"))
                typer.echo(f"{r.department:<35} | {r.status:<10} | {r.quota:<10} | {r.current:<10} | {avail_str:<10}")
        finally:
            await quota_service.aclose()

    asyncio.run(_fetch())


def main() -> None:
    """CLI entrypoint callable."""
    app()
