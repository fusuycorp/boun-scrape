"""Unit tests for configuration and environment loading."""

import os
from unittest.mock import patch

import pytest

from boun_scrape.config import Settings, get_settings


class TestConfig:
    """Tests for Pydantic application settings."""

    def test_default_settings(self) -> None:
        settings = Settings()
        assert settings.db_path == "schedules.db"
        assert settings.base_url == "https://registration.bogazici.edu.tr"
        assert settings.quota_url == "https://registration.boun.edu.tr"
        assert settings.cookies_path == "cookies.txt"
        assert settings.max_concurrency == 10
        assert settings.request_timeout == 15.0
        assert settings.min_jitter == 0.05
        assert settings.max_jitter == 0.2
        assert settings.admin_user == "admin"
        assert settings.webhook_secret == ""

    def test_env_override(self) -> None:
        env_vars = {
            "BOUN_DB_PATH": "test_schedules.db",
            "BOUN_MAX_CONCURRENCY": "25",
            "BOUN_REQUEST_TIMEOUT": "30.0",
            "BOUN_WEBHOOK_SECRET": "super-secret-key",
            "BOUN_ADMIN_USER": "superadmin",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()
            assert settings.db_path == "test_schedules.db"
            assert settings.max_concurrency == 25
            assert settings.request_timeout == 30.0
            assert settings.webhook_secret == "super-secret-key"
            assert settings.admin_user == "superadmin"

    def test_dokploy_unprefixed_env_override(self) -> None:
        env_vars = {
            "DB_PATH": "/data/schedules.db",
            "JWT_SECRET_KEY": "e830f54e4f50uaO9g7O7P2h6e5w4q3r2t1y0u9i8o7p6a5s4d3f2g1h",
            "ADMIN_USER": "admin",
            "ALLOWED_ORIGINS": "https://scraper.bountools.com",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()
            assert settings.db_path == "/data/schedules.db"
            assert settings.jwt_secret_key == "e830f54e4f50uaO9g7O7P2h6e5w4q3r2t1y0u9i8o7p6a5s4d3f2g1h"
            assert settings.admin_user == "admin"
            assert settings.allowed_origins == ["https://scraper.bountools.com"]

    def test_get_settings_singleton(self) -> None:
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_dev_default_generates_ephemeral_secrets(self) -> None:
        """environment defaults to development, so missing secrets are auto-generated, not hardcoded."""
        settings = Settings()
        assert settings.environment == "development"
        assert settings.jwt_secret_key
        assert settings.admin_password_hash
        assert settings.admin_password_hash.startswith("$2b$")

    def test_production_fails_fast_without_jwt_secret(self) -> None:
        env_vars = {"ENVIRONMENT": "production", "ADMIN_PASSWORD_HASH": "$2b$12$AWoniBnnbFfjVI3tldX2wuOPEVNmik7mwrsM88M6C0ARftQv9WvvG"}
        with patch.dict(os.environ, env_vars, clear=False):
            with pytest.raises(Exception, match="JWT_SECRET_KEY"):
                Settings(_env_file=None)

    def test_production_fails_fast_without_admin_password_hash(self) -> None:
        env_vars = {"ENVIRONMENT": "production", "JWT_SECRET_KEY": "a" * 32}
        with patch.dict(os.environ, env_vars, clear=False):
            with pytest.raises(Exception, match="ADMIN_PASSWORD_HASH"):
                Settings(_env_file=None)

    def test_production_succeeds_with_explicit_secrets(self) -> None:
        env_vars = {
            "ENVIRONMENT": "production",
            "JWT_SECRET_KEY": "a" * 32,
            "ADMIN_PASSWORD_HASH": "$2b$12$AWoniBnnbFfjVI3tldX2wuOPEVNmik7mwrsM88M6C0ARftQv9WvvG",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            settings = Settings(_env_file=None)
            assert settings.jwt_secret_key == "a" * 32
