from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Secrets published in .env.example. They make a fresh checkout runnable
# immediately, and are rejected outright in production - see
# _validate_production_settings.
_SAMPLE_SECRETS = frozenset({
    "dev-only-276600405983050a586da0a46095b079b27f257678439047e52ff91c",
    "cX7aqLayA2jfaLdKAvzVWC0TirwwWbcVPkiKTwAkgE4=",
})


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

    DYNAMODB_CACHE_TABLE: str = "instalysis-cache"
    # Left unset in production so boto3 talks to the real AWS endpoint;
    # local dev/tests point this at a local DynamoDB instance instead.
    DYNAMODB_ENDPOINT_URL: str | None = None
    CACHE_TTL_SECONDS: int = 900

    # Not read by the app itself - boto3 picks these up directly from the
    # environment. Declared here only so local dev can put dummy credentials
    # for DynamoDB Local in the same .env file without pydantic rejecting
    # them as unknown keys. In production, Lambda's execution role supplies
    # real credentials automatically; these stay unset there.
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_DEFAULT_REGION: str | None = None

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # A long-lived refresh token is what actually keeps a device signed in -
    # the access token above stays short-lived regardless, refreshed
    # silently in the background (see app/utils/jwt.py, /auth/refresh).
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Google AI Studio API key (free tier) - https://aistudio.google.com/apikey
    GOOGLE_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TEMPERATURE: float = 0.2
    # Without a timeout, a flapping provider can retry internally for an
    # unbounded amount of wall-clock time (see build_llm). This bounds a
    # single call; a request making several sequential calls (e.g. the
    # full-report export) is bounded by a small multiple of this instead.
    GEMINI_TIMEOUT_SECONDS: int = 45

    # Caps how many agent <-> tool round-trips a single /ai/chat request may
    # take before LangGraph aborts the run, guarding against runaway loops.
    AI_RECURSION_LIMIT: int = 8

    # From the app's "Instagram > API setup with Instagram login" dashboard
    # page - a distinct Instagram App ID/Secret, not the main Facebook one.
    INSTAGRAM_APP_ID: str | None = None
    INSTAGRAM_APP_SECRET: str | None = None
    INSTAGRAM_REDIRECT_URI: str | None = None
    INSTAGRAM_GRAPH_API_VERSION: str = "v21.0"

    TOKEN_ENCRYPTION_KEY: str

    META_ACCESS_TOKEN: str | None = None

    # Shared secret CloudFront attaches to every request as a custom origin
    # header, checked by OriginVerifyMiddleware - see its docstring. Unset
    # locally, where nothing sits in front of the app.
    CLOUDFRONT_ORIGIN_VERIFY_SECRET: str | None = None

    # Comma-separated list of allowed browser origins for CORS.
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Base URL of the Instalysis frontend. The Instagram OAuth callback
    # redirects the browser back here, since returning JSON would dead-end
    # the user on a blank page. Must be one of CORS_ALLOWED_ORIGINS.
    FRONTEND_URL: str = "http://localhost:3000"

    # slowapi rate-limit strings, e.g. "100/minute". STRICT applies to
    # expensive AI-backed endpoints, AUTH to login/register. EXPORT is
    # deliberately much tighter than STRICT: the full-report export makes 3
    # sequential Gemini calls per request, so STRICT's 10/minute would let
    # one user drive up to 30 Gemini calls/minute through this endpoint
    # alone - well above the free tier's ~10 RPM.
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_STRICT: str = "10/minute"
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_EXPORT: str = "3/minute"

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

        # .env.example ships working sample secrets so that `cp .env.example
        # .env` yields a runnable local setup. They are in source control and
        # therefore public, so production must never start with them.
        if self.JWT_SECRET_KEY in _SAMPLE_SECRETS:
            errors.append(
                "JWT_SECRET_KEY is still the public sample value from .env.example. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if self.TOKEN_ENCRYPTION_KEY in _SAMPLE_SECRETS:
            errors.append(
                "TOKEN_ENCRYPTION_KEY is still the public sample value from .env.example. "
                "Generate one with: python -c "
                "\"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

        if errors:
            raise ValueError(" ".join(errors))

        return self


settings = Settings()
