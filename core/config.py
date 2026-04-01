from enum import Enum
from functools import lru_cache

from pydantic import AnyHttpUrl, PositiveFloat, conint, field_validator
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
        if not v.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use 'postgresql+psycopg://' scheme")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
