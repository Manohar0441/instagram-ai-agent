"""Startup configuration validation.

These guard the promise that a misconfigured production instance fails
loudly at boot rather than starting and being quietly unsafe.
"""
import pytest
from pydantic import ValidationError

from app.core.settings import _SAMPLE_SECRETS, Settings

pytestmark = pytest.mark.unit

VALID = {
    "APP_NAME": "Test App",
    "APP_VERSION": "1.0.0",
    "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/test",
    "JWT_SECRET_KEY": "a" * 64,
    "TOKEN_ENCRYPTION_KEY": "cX7aqLayA2jfaLdKAvzVWC0TirwwWbcVPkiKTwAkgE5=",
    "CORS_ALLOWED_ORIGINS": "https://app.example.com",
    "_env_file": None,  # ignore the developer's real .env
}


def build(**overrides) -> Settings:
    return Settings(**{**VALID, **overrides})


class TestDevelopmentIsPermissive:
    def test_defaults_are_accepted(self):
        assert build(ENVIRONMENT="development").ENVIRONMENT == "development"

    def test_wildcard_cors_is_allowed_locally(self):
        assert "*" in build(ENVIRONMENT="development", CORS_ALLOWED_ORIGINS="*").cors_origins

    def test_short_secret_is_allowed_locally(self):
        assert build(ENVIRONMENT="development", JWT_SECRET_KEY="short").JWT_SECRET_KEY == "short"

    @pytest.mark.parametrize("secret", sorted(_SAMPLE_SECRETS))
    def test_sample_secrets_are_allowed_locally(self, secret):
        """`cp .env.example .env` must give a runnable local setup."""
        assert build(ENVIRONMENT="development", JWT_SECRET_KEY=secret)


class TestProductionIsStrict:
    def test_a_correct_production_config_is_accepted(self):
        assert build(ENVIRONMENT="production").is_production

    def test_debug_must_be_off(self):
        with pytest.raises(ValidationError, match="DEBUG must be False"):
            build(ENVIRONMENT="production", DEBUG=True)

    def test_secret_must_be_long_enough(self):
        with pytest.raises(ValidationError, match="at least 32 characters"):
            build(ENVIRONMENT="production", JWT_SECRET_KEY="too-short")

    def test_wildcard_cors_is_rejected(self):
        with pytest.raises(ValidationError, match="must not include"):
            build(ENVIRONMENT="production", CORS_ALLOWED_ORIGINS="*")

    def test_wildcard_is_rejected_even_among_real_origins(self):
        with pytest.raises(ValidationError, match="must not include"):
            build(ENVIRONMENT="production", CORS_ALLOWED_ORIGINS="https://app.example.com,*")

    def test_sample_jwt_secret_is_rejected(self):
        """The sample secrets are committed to source control, so anyone can
        forge tokens against a production instance still using them."""
        sample = next(s for s in _SAMPLE_SECRETS if s.startswith("dev-only-"))
        with pytest.raises(ValidationError, match="public sample value"):
            build(ENVIRONMENT="production", JWT_SECRET_KEY=sample)

    def test_sample_encryption_key_is_rejected(self):
        sample = next(s for s in _SAMPLE_SECRETS if s.endswith("="))
        with pytest.raises(ValidationError, match="public sample value"):
            build(ENVIRONMENT="production", TOKEN_ENCRYPTION_KEY=sample)

    def test_every_problem_is_reported_at_once(self):
        """Reporting one error at a time turns deployment into whack-a-mole."""
        with pytest.raises(ValidationError) as exc:
            build(ENVIRONMENT="production", DEBUG=True, JWT_SECRET_KEY="short",
                  CORS_ALLOWED_ORIGINS="*")
        message = str(exc.value)
        assert "DEBUG" in message
        assert "at least 32 characters" in message
        assert "must not include" in message


class TestCorsParsing:
    def test_splits_and_strips(self):
        settings = build(CORS_ALLOWED_ORIGINS="https://a.com, https://b.com ,https://c.com")
        assert settings.cors_origins == ["https://a.com", "https://b.com", "https://c.com"]

    def test_ignores_empty_entries(self):
        assert build(CORS_ALLOWED_ORIGINS="https://a.com,,").cors_origins == ["https://a.com"]


class TestUnknownKeysAreRejected:
    def test_a_typo_is_caught_rather_than_silently_ignored(self):
        """Without this, `DATABSE_URL=...` in .env would be ignored and the
        app would quietly fall back to a different database."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            build(DATABSE_URL="postgresql://typo")
