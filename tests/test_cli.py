"""Unit and integration tests for Typer CLI commands."""

import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from typer.testing import CliRunner

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from Rich-rendered --help output.

    Rich applies per-word/per-line styling to Typer's --help panels whenever
    it detects a CI environment (GitHub Actions always sets CI=true), which
    can inject escape codes between characters of a flag name and break a
    plain substring check even though the flag renders correctly on screen.
    """
    return _ANSI_RE.sub("", text)

from boun_scrape.cli.app import app
from boun_scrape.domain.models import (
    Course,
    CourseSlot,
    QuotaRecord,
    RunStatus,
    ScrapeRunSummary,
)
from boun_scrape.storage.database import DatabaseManager
from boun_scrape.storage.repository import CourseRepository

runner = CliRunner()


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    """Create a temporary initialized SQLite database with sample data."""
    db_file = tmp_path / "cli_test.db"
    db_mgr = DatabaseManager(str(db_file))
    db_mgr.init_db()
    repo = CourseRepository(db_mgr)

    term = "2024/2025-1"
    repo.save_courses_and_slots(
        term,
        [
            Course(
                term=term,
                department="CMPE",
                course_code="CMPE150",
                section="01",
                course_name="Intro",
                instructor="Prof. Smith",
                slots=[CourseSlot(day="M", hour="12", room="NH101")],
            )
        ],
    )
    return str(db_file)


class TestCliApp:
    """Test suite for CLI command dispatching and output formatting."""

    def test_cli_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        stdout = _strip_ansi(result.stdout)
        assert "scrape" in stdout
        assert "serve" in stdout
        assert "daemon" in stdout
        assert "export" in stdout
        assert "quota" in stdout

    def test_scrape_help(self) -> None:
        result = runner.invoke(app, ["scrape", "--help"])
        assert result.exit_code == 0
        stdout = _strip_ansi(result.stdout)
        assert "--term" in stdout
        assert "--all-terms" in stdout
        assert "--no-export" in stdout
        assert "--no-webhooks" in stdout
        assert "--capture-quota" in stdout

    def test_scrape_command_success(self, temp_db: str) -> None:
        mock_summary = ScrapeRunSummary(
            run_id="run_cli_123",
            term="2024/2025-1",
            status=RunStatus.COMPLETED,
            total_departments=1,
            total_courses=1,
            total_slots=1,
            changes_detected=0,
            started_at="2026-08-15T00:00:00Z",
            completed_at="2026-08-15T00:01:00Z",
        )

        with patch("boun_scrape.cli.app.ScrapeScheduler") as mock_sched_cls:
            instance = mock_sched_cls.return_value
            instance.execute_scrape_cycle = AsyncMock(return_value=mock_summary)
            instance.aclose = AsyncMock()

            result = runner.invoke(
                app,
                ["scrape", "--term", "2024/2025-1", "--no-export", "--no-webhooks", "--db", temp_db],
            )
            assert result.exit_code == 0
            assert "Scrape cycle completed successfully" in result.stdout
            assert "run_cli_123" in result.stdout
            instance.execute_scrape_cycle.assert_called_once_with(
                term="2024/2025-1",
                export=False,
                dispatch_webhooks=False,
                capture_quota=False,
            )

    def test_serve_command(self) -> None:
        with patch("boun_scrape.cli.app.uvicorn.run") as mock_uvicorn:
            result = runner.invoke(app, ["serve", "--host", "127.0.0.1", "--port", "9000", "--reload"])
            assert result.exit_code == 0
            mock_uvicorn.assert_called_once_with(
                "boun_scrape.api.app:create_app",
                factory=True,
                host="127.0.0.1",
                port=9000,
                reload=True,
            )

    def test_daemon_help(self) -> None:
        result = runner.invoke(app, ["daemon", "--help"])
        assert result.exit_code == 0
        stdout = _strip_ansi(result.stdout)
        assert "--interval" in stdout
        assert "--cron" in stdout
        assert "--term" in stdout

    def test_daemon_command_invocation(self, temp_db: str) -> None:
        with patch("boun_scrape.cli.app.ScrapeScheduler") as mock_sched_cls:
            instance = mock_sched_cls.return_value
            instance.start = MagicMock()
            instance.aclose = AsyncMock()

            def _close_coro(coro: Any) -> None:
                coro.close()

            with patch("boun_scrape.cli.app.asyncio.run", side_effect=_close_coro) as mock_asyncio_run:
                result = runner.invoke(
                    app,
                    ["daemon", "--interval", "1800", "--term", "2024/2025-1", "--db", temp_db],
                )
                assert result.exit_code == 0
                assert "Starting scheduler daemon" in result.stdout
                mock_sched_cls.assert_called_once()
                call_kwargs = mock_sched_cls.call_args.kwargs
                assert call_kwargs["interval_seconds"] == 1800
                assert call_kwargs["default_term"] == "2024/2025-1"
                mock_asyncio_run.assert_called_once()

    def test_export_command_all_success(self, temp_db: str, tmp_path: Path) -> None:
        out_dir = tmp_path / "exports"
        result = runner.invoke(
            app,
            ["export", "--term", "2024/2025-1", "--format", "all", "--output-dir", str(out_dir), "--db", temp_db],
        )
        assert result.exit_code == 0
        assert "Exported all artifacts" in result.stdout
        assert (out_dir / "courses_2024_2025-1.json").exists()
        assert (out_dir / "courses_2024_2025-1.csv").exists()
        assert (out_dir / "courses_2024_2025-1.db").exists()

    def test_export_command_individual_formats(self, temp_db: str, tmp_path: Path) -> None:
        out_dir = tmp_path / "exports"

        # JSON
        res_json = runner.invoke(
            app,
            ["export", "--term", "2024/2025-1", "--format", "json", "--output-dir", str(out_dir), "--db", temp_db],
        )
        assert res_json.exit_code == 0
        assert "Exported JSON" in res_json.stdout

        # CSV
        res_csv = runner.invoke(
            app,
            ["export", "--term", "2024/2025-1", "--format", "csv", "--output-dir", str(out_dir), "--db", temp_db],
        )
        assert res_csv.exit_code == 0
        assert "Exported CSV" in res_csv.stdout

        # SQLite
        res_sqlite = runner.invoke(
            app,
            ["export", "--term", "2024/2025-1", "--format", "sqlite", "--output-dir", str(out_dir), "--db", temp_db],
        )
        assert res_sqlite.exit_code == 0
        assert "Exported SQLite" in res_sqlite.stdout

    def test_export_command_no_courses(self, temp_db: str, tmp_path: Path) -> None:
        out_dir = tmp_path / "exports"
        result = runner.invoke(
            app,
            ["export", "--term", "1999/2000-1", "--output-dir", str(out_dir), "--db", temp_db],
        )
        assert result.exit_code == 1
        assert "No courses found in database" in result.stdout

    def test_export_command_invalid_format(self, temp_db: str, tmp_path: Path) -> None:
        out_dir = tmp_path / "exports"
        result = runner.invoke(
            app,
            ["export", "--term", "2024/2025-1", "--format", "yaml", "--output-dir", str(out_dir), "--db", temp_db],
        )
        assert result.exit_code == 1
        assert "Invalid format 'yaml'" in result.stdout

    def test_quota_command_success(self) -> None:
        records = [
            QuotaRecord(
                department="CMPE",
                status="Open",
                quota="60",
                current="50",
                quota_numeric=60,
                current_numeric=50,
                is_consent=False,
                is_unlimited=False,
                available=10,
            )
        ]

        with patch("boun_scrape.cli.app.QuotaService") as mock_quota_cls:
            instance = mock_quota_cls.return_value
            instance.fetch_quota = AsyncMock(return_value=records)
            instance.aclose = AsyncMock()

            result = runner.invoke(
                app,
                ["quota", "--abbr", "CMPE", "--code", "150", "--section", "01", "--term", "2024/2025-1"],
            )
            assert result.exit_code == 0
            assert "Quota records for CMPE 150" in result.stdout
            assert "Open" in result.stdout
            assert "10" in result.stdout

    def test_quota_command_no_records(self) -> None:
        with patch("boun_scrape.cli.app.QuotaService") as mock_quota_cls:
            instance = mock_quota_cls.return_value
            instance.fetch_quota = AsyncMock(return_value=[])
            instance.aclose = AsyncMock()

            result = runner.invoke(
                app,
                ["quota", "--abbr", "PHYS", "--code", "101", "--section", "01"],
            )
            assert result.exit_code == 0
            assert "No quota records returned" in result.stdout
