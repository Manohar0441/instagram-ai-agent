from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str

    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    DATABASE_URL: str
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_RECYCLE_SECONDS: int = 1800

    # Not read by the app itself (DATABASE_URL is what's actually used) -
    # declared here only so docker-compose.prod.yml can share this same
    # .env file for its own ${POSTGRES_*} substitution without pydantic
    # rejecting them as unknown keys. Must stay in sync with DATABASE_URL.
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str | None = None

    REDIS_URL: str
    CACHE_TTL_SECONDS: int = 900

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.2

    # Caps how many agent <-> tool round-trips a single /ai/chat request may
    # take before LangGraph aborts the run, guarding against runaway loops.
    AI_RECURSION_LIMIT: int = 8

    INSTAGRAM_APP_ID: str | None = None
    INSTAGRAM_APP_SECRET: str | None = None
    INSTAGRAM_REDIRECT_URI: str | None = None
    INSTAGRAM_GRAPH_API_VERSION: str = "v21.0"

    TOKEN_ENCRYPTION_KEY: str

    META_ACCESS_TOKEN: str | None = None

    # Comma-separated list of allowed browser origins for CORS.
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"

    # slowapi rate-limit strings, e.g. "100/minute". STRICT applies to
    # expensive AI-backed endpoints, AUTH to login/register.
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_STRICT: str = "10/minute"
    RATE_LIMIT_AUTH: str = "5/minute"

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )

    @property
    def cors_origins(self) -> list[str]:
        """CORS_ALLOWED_ORIGINS parsed into a list of individual origins."""
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @model_validator(mode="after")
    def _validate_production_settings(self) -> "Settings":
        """Fail fast at startup if production is configured insecurely."""
        if not self.is_production:
            return self

        errors: list[str] = []
        if self.DEBUG:
            errors.append("DEBUG must be False when ENVIRONMENT=production.")
        if len(self.JWT_SECRET_KEY) < 32:
            errors.append("JWT_SECRET_KEY must be at least 32 characters when ENVIRONMENT=production.")
        if "*" in self.cors_origins:
            errors.append("CORS_ALLOWED_ORIGINS must not include '*' when ENVIRONMENT=production.")

        if errors:
            raise ValueError(" ".join(errors))

        return self


settings = Settings()
