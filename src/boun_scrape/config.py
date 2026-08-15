"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Any
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration and environment settings."""

    db_path: str = Field(default="schedules.db", validation_alias=AliasChoices("BOUN_DB_PATH", "DB_PATH", "db_path"))
    base_url: str = Field(default="https://registration.bogazici.edu.tr", validation_alias=AliasChoices("BOUN_BASE_URL", "BASE_URL", "base_url"))
    quota_url: str = Field(default="https://registration.boun.edu.tr", validation_alias=AliasChoices("BOUN_QUOTA_URL", "QUOTA_URL", "quota_url"))
    cookies_path: str = Field(default="cookies.txt", validation_alias=AliasChoices("BOUN_COOKIES_PATH", "COOKIES_PATH", "cookies_path"))
    max_concurrency: int = Field(default=10, validation_alias=AliasChoices("BOUN_MAX_CONCURRENCY", "MAX_CONCURRENCY", "max_concurrency"))
    request_timeout: float = Field(default=15.0, validation_alias=AliasChoices("BOUN_REQUEST_TIMEOUT", "REQUEST_TIMEOUT", "request_timeout"))
    min_jitter: float = Field(default=0.05, validation_alias=AliasChoices("BOUN_MIN_JITTER", "MIN_JITTER", "min_jitter"))
    max_jitter: float = Field(default=0.2, validation_alias=AliasChoices("BOUN_MAX_JITTER", "MAX_JITTER", "max_jitter"))
    jwt_secret_key: str = Field(default="boun-scrape-default-jwt-secret-key-change-in-production", validation_alias=AliasChoices("BOUN_JWT_SECRET_KEY", "JWT_SECRET_KEY", "jwt_secret_key"))
    admin_user: str = Field(default="admin", validation_alias=AliasChoices("BOUN_ADMIN_USER", "ADMIN_USER", "admin_user"))
    admin_password_hash: str = Field(default="$2b$12$AWoniBnnbFfjVI3tldX2wuOPEVNmik7mwrsM88M6C0ARftQv9WvvG", validation_alias=AliasChoices("BOUN_ADMIN_PASSWORD_HASH", "ADMIN_PASSWORD_HASH", "admin_password_hash"))
    webhook_secret: str = Field(default="", validation_alias=AliasChoices("BOUN_WEBHOOK_SECRET", "WEBHOOK_SECRET", "webhook_secret"))
    export_dir: str = Field(default="exports", validation_alias=AliasChoices("BOUN_EXPORT_DIR", "EXPORT_DIR", "export_dir"))
    allowed_origins: Any = Field(default=["*"], validation_alias=AliasChoices("BOUN_ALLOWED_ORIGINS", "ALLOWED_ORIGINS", "allowed_origins"))

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
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
