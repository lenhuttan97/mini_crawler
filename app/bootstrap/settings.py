"""Application settings with profile-aware validation (P00 Item 2)."""

from __future__ import annotations

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables.

    Profiles:
    - ``local``: relaxed defaults, secrets still required but defaultable.
    - ``test``: test defaults, debug enabled.
    - ``prod``: fail-fast when required secrets are missing.
    """

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    profile: str = "local"
    debug: bool = False
    port: int = 8000
    secret_key: SecretStr | None = None
    database_url: str = Field(
        default="postgresql+psycopg://minicrawler:devpassword@localhost:5432/minicrawler",
        validation_alias=AliasChoices("DATABASE_URL", "APP_DATABASE_URL"),
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS_URL", "APP_REDIS_URL"),
    )
    minio_endpoint: str = Field(
        default="http://localhost:9000",
        validation_alias=AliasChoices("MINIO_ENDPOINT", "APP_MINIO_ENDPOINT"),
    )
    minio_access_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("MINIO_ACCESS_KEY", "APP_MINIO_ACCESS_KEY"),
    )
    minio_secret_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("MINIO_SECRET_KEY", "APP_MINIO_SECRET_KEY"),
    )
    searxng_url: str = Field(
        default="http://localhost:8080",
        validation_alias=AliasChoices("SEARXNG_URL", "APP_SEARXNG_URL"),
    )

    @field_validator("profile")
    @classmethod
    def _normalize_profile(cls, value: str) -> str:
        return value.lower()

    @model_validator(mode="after")
    def _apply_profile_defaults(self) -> Settings:
        if self.profile == "test":
            self.debug = True
        if self.profile == "prod" and not self.secret_key:
            raise ValueError("APP_SECRET_KEY is required in the prod profile")
        return self
