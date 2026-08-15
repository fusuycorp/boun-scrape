"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration and environment settings."""

    db_path: str = "schedules.db"
    base_url: str = "https://registration.bogazici.edu.tr"
    quota_url: str = "https://registration.boun.edu.tr"
    cookies_path: str = "cookies.txt"
    max_concurrency: int = 10
    request_timeout: float = 15.0
    min_jitter: float = 0.05
    max_jitter: float = 0.2
    jwt_secret_key: str = "boun-scrape-default-jwt-secret-key-change-in-production"
    admin_user: str = "admin"
    admin_password_hash: str = "$2b$12$AWoniBnnbFfjVI3tldX2wuOPEVNmik7mwrsM88M6C0ARftQv9WvvG"
    webhook_secret: str = ""
    export_dir: str = "exports"
    allowed_origins: list[str] = ["*"]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("[") and v_str.endswith("]"):
                import json

                try:
                    parsed = json.loads(v_str)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    pass
            return [origin.strip() for origin in v_str.split(",") if origin.strip()]
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return ["*"]

    model_config = SettingsConfigDict(
        env_prefix="BOUN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
