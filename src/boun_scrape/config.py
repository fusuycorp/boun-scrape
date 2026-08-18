"""Application configuration using Pydantic Settings."""

import logging
import secrets
from functools import lru_cache
from typing import Annotated, Any
import bcrypt
from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

logger = logging.getLogger(__name__)

_DEV_ENVIRONMENTS = {"development", "dev", "test", "testing", "local"}


class Settings(BaseSettings):
    """Application configuration and environment settings."""

    environment: str = Field(default="development", validation_alias=AliasChoices("BOUN_ENVIRONMENT", "ENVIRONMENT", "environment"))
    db_path: str = Field(default="schedules.db", validation_alias=AliasChoices("BOUN_DB_PATH", "DB_PATH", "db_path"))
    base_url: str = Field(default="https://registration.bogazici.edu.tr", validation_alias=AliasChoices("BOUN_BASE_URL", "BASE_URL", "base_url"))
    quota_url: str = Field(default="https://registration.boun.edu.tr", validation_alias=AliasChoices("BOUN_QUOTA_URL", "QUOTA_URL", "quota_url"))
    cookies_path: str = Field(default="cookies.txt", validation_alias=AliasChoices("BOUN_COOKIES_PATH", "COOKIES_PATH", "cookies_path"))
    recaptcha_token_path: str = Field(default="recaptcha_token.txt", validation_alias=AliasChoices("BOUN_RECAPTCHA_TOKEN_PATH", "RECAPTCHA_TOKEN_PATH", "recaptcha_token_path"))
    max_concurrency: int = Field(default=10, validation_alias=AliasChoices("BOUN_MAX_CONCURRENCY", "MAX_CONCURRENCY", "max_concurrency"))
    request_timeout: float = Field(default=15.0, validation_alias=AliasChoices("BOUN_REQUEST_TIMEOUT", "REQUEST_TIMEOUT", "request_timeout"))
    min_jitter: float = Field(default=0.05, validation_alias=AliasChoices("BOUN_MIN_JITTER", "MIN_JITTER", "min_jitter"))
    max_jitter: float = Field(default=0.2, validation_alias=AliasChoices("BOUN_MAX_JITTER", "MAX_JITTER", "max_jitter"))
    jwt_secret_key: str | None = Field(default=None, validation_alias=AliasChoices("BOUN_JWT_SECRET_KEY", "JWT_SECRET_KEY", "jwt_secret_key"))
    admin_user: str = Field(default="admin", validation_alias=AliasChoices("BOUN_ADMIN_USER", "ADMIN_USER", "admin_user"))
    admin_password_hash: str | None = Field(default=None, validation_alias=AliasChoices("BOUN_ADMIN_PASSWORD_HASH", "ADMIN_PASSWORD_HASH", "admin_password_hash"))
    webhook_secret: str = Field(default="", validation_alias=AliasChoices("BOUN_WEBHOOK_SECRET", "WEBHOOK_SECRET", "webhook_secret"))
    export_dir: str = Field(default="exports", validation_alias=AliasChoices("BOUN_EXPORT_DIR", "EXPORT_DIR", "export_dir"))
    allowed_origins: Annotated[list[str], NoDecode] = Field(default=["*"], validation_alias=AliasChoices("BOUN_ALLOWED_ORIGINS", "ALLOWED_ORIGINS", "allowed_origins"))

    @model_validator(mode="after")
    def _resolve_secrets(self) -> "Settings":
        """Fail fast on missing secrets outside development; generate ephemeral dev-only values otherwise."""
        is_dev = self.environment.strip().lower() in _DEV_ENVIRONMENTS

        if self.jwt_secret_key is None:
            if not is_dev:
                raise ValueError(
                    "JWT_SECRET_KEY must be set explicitly when ENVIRONMENT is not development "
                    "(generate one with: python -c \"import secrets; print(secrets.token_hex(32))\")"
                )
            self.jwt_secret_key = secrets.token_hex(32)
            logger.warning(
                "JWT_SECRET_KEY not set; generated an ephemeral development-only secret. "
                "Tokens will be invalidated on restart. Set JWT_SECRET_KEY explicitly in production."
            )

        if self.admin_password_hash is None:
            if not is_dev:
                raise ValueError(
                    "ADMIN_PASSWORD_HASH must be set explicitly when ENVIRONMENT is not development "
                    "(generate one with: python -c \"import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())\")"
                )
            dev_password = secrets.token_urlsafe(12)
            self.admin_password_hash = bcrypt.hashpw(dev_password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
            logger.warning(
                "ADMIN_PASSWORD_HASH not set; generated an ephemeral development-only admin password: %s "
                "(user=%s). Set ADMIN_PASSWORD_HASH explicitly in production.",
                dev_password,
                self.admin_user,
            )

        return self

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
