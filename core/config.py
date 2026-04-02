from enum import Enum
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Project Name API"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/project_name"
    LOG_LEVEL: str = "info"
    RELOAD: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = "https://valsoft-library-frontend.vercel.app"
    METRICS_ENABLED: bool = False
    SENTRY_DSN: str | None = None
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str | None = None
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    # Max seconds to wait for Gemini generateContent (read); slow models/network need more.
    GEMINI_HTTP_TIMEOUT_SECONDS: float = 180.0
    # Retries for transient HTTP errors (429, 5xx). First attempt + up to this many retries.
    GEMINI_MAX_RETRIES: int = 5
    GEMINI_RETRY_BACKOFF_BASE_SECONDS: float = 1.0
    GEMINI_RETRY_BACKOFF_MAX_SECONDS: float = 60.0
    # Serialize Gemini HTTP calls per process (reduces concurrent rate-limit pressure).
    GEMINI_SERIALIZE_REQUESTS: bool = True
    OPEN_LIBRARY_BASE_URL: str = "https://openlibrary.org"
    # Open Library HTTP timeout for ISBN lookup before AI enrichment (seconds).
    ISBN_LOOKUP_TIMEOUT_SECONDS: float = 12.0

    @field_validator("SENTRY_DSN", mode="before")
    @classmethod
    def empty_sentry_dsn(cls, v: str | None) -> str | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("GEMINI_API_KEY", "GEMINI_MODEL", mode="before")
    @classmethod
    def empty_gemini_optional(cls, v: str | None) -> str | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("GEMINI_HTTP_TIMEOUT_SECONDS")
    @classmethod
    def validate_gemini_timeout(cls, v: float) -> float:
        if v < 30.0 or v > 600.0:
            raise ValueError("GEMINI_HTTP_TIMEOUT_SECONDS must be between 30 and 600")
        return v

    @field_validator("GEMINI_MAX_RETRIES")
    @classmethod
    def validate_gemini_max_retries(cls, v: int) -> int:
        if v < 0 or v > 20:
            raise ValueError("GEMINI_MAX_RETRIES must be between 0 and 20")
        return v

    @field_validator("GEMINI_RETRY_BACKOFF_BASE_SECONDS", "GEMINI_RETRY_BACKOFF_MAX_SECONDS")
    @classmethod
    def validate_gemini_backoff(cls, v: float) -> float:
        if v < 0.1 or v > 300.0:
            raise ValueError("Gemini backoff seconds must be between 0.1 and 300")
        return v

    @field_validator("ISBN_LOOKUP_TIMEOUT_SECONDS")
    @classmethod
    def validate_isbn_lookup_timeout(cls, v: float) -> float:
        if v < 1.0 or v > 60.0:
            raise ValueError("ISBN_LOOKUP_TIMEOUT_SECONDS must be between 1 and 60")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"debug", "info", "warning", "error", "critical"}
        if v.lower() not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}")
        return v.lower()

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if v.startswith("postgresql+psycopg://") or v.startswith("sqlite"):
            return v
        raise ValueError(
            "DATABASE_URL must use 'postgresql+psycopg://' or a 'sqlite' scheme"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
