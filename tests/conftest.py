"""Shared pytest fixtures.

Tests run against an in-memory SQLite database, a moto-mocked DynamoDB, and
stubbed LLM/Graph API clients - no external services, no network, no API
spend. Every external boundary the app depends on is replaced here rather
than in individual tests, so tests stay focused on behavior.
"""
from datetime import datetime, timedelta, timezone

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.integrations.dynamodb_client as dynamodb_client_module
import app.services.ai_credential_service as credential_module
import app.services.insights_service as insights_module
import app.services.recommendation_service as recommendation_module
import app.services.report_service as report_module
from app.core.rate_limit import limiter
from app.core.settings import settings
from app.database.base import Base
from app.dependencies.database import get_db
from app.main import app
from app.models.account_insight import AccountInsight
from app.models.deal import Deal
from app.models.instagram_account import InstagramAccount
from app.models.instagram_media import InstagramMedia
from app.models.media_insight import MediaInsight
from app.models.user import User
from app.utils.security import hash_password

# ---------------------------------------------------------------- database


@pytest.fixture(scope="session")
def engine():
    """One in-memory SQLite database shared by every session in the run.

    StaticPool keeps all sessions on the same underlying connection, which
    is what makes a `:memory:` database visible across the test's session
    and the request-handling session inside the app.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture(scope="session")
def session_factory(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db(session_factory):
    """A database session for arranging test data directly."""
    session = session_factory()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _clean_tables(engine):
    """Empty every table after each test so tests can't leak state into each other."""
    yield
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


# -------------------------------------------------------------- dynamodb


@pytest.fixture(autouse=True)
def fake_dynamodb(monkeypatch):
    """Replace the cache DynamoDB table with an isolated moto-mocked one for every test.

    Without this, cache reads/writes would need real AWS credentials and
    network access - moto intercepts boto3 calls entirely instead, so tests
    stay self-contained regardless of what's in the local .env file (moto
    still requires *some* credential-shaped values to exist, hence the
    dummy ones below - it never checks they're real).

    Set as real environment variables (not Settings fields) to match
    get_cache_table()'s production path, which - now that it no longer
    shadows Lambda's own injected credentials (see its docstring) - reads
    credentials via boto3's default chain rather than from Settings.
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setattr(settings, "DYNAMODB_ENDPOINT_URL", None)

    with mock_aws():
        # Force the process-wide singleton to rebuild against this test's
        # mocked backend rather than reusing a client from a previous test.
        dynamodb_client_module._table = None

        client = boto3.client(
            "dynamodb",
            region_name="us-east-1",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        client.create_table(
            TableName=settings.DYNAMODB_CACHE_TABLE,
            KeySchema=[{"AttributeName": "cache_key", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "cache_key", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield client
        dynamodb_client_module._table = None


# ------------------------------------------------------------- rate limits


@pytest.fixture(autouse=True)
def _health_checks_use_the_test_database(session_factory, monkeypatch):
    """Point the readiness probe's database check at the test database.

    It otherwise opens its own connection to the configured DATABASE_URL,
    which in a test environment means waiting out a multi-second TCP timeout
    on every health request.
    """
    import app.api.health as health_module

    monkeypatch.setattr(health_module, "SessionLocal", session_factory)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear rate-limit buckets between tests.

    The limiter is process-wide and in-memory, so without this a test that
    exhausts a limit would cause unrelated later tests to fail with 429.
    """
    limiter.reset()
    yield
    limiter.reset()


# --------------------------------------------------------------- app/client


@pytest.fixture(autouse=True)
def _configure_ai(monkeypatch):
    """Default every test to a configured-looking AI setup.

    GOOGLE_API_KEY acts as the server-wide fallback, so every test user
    resolves a key without storing one. Tests that specifically exercise
    the unconfigured path override this with monkeypatch themselves.

    Storing a key normally probes the real Gemini API; that is stubbed out
    here so no test reaches the network. Tests for the rejection path
    override it themselves.
    """
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(credential_module, "verify_api_key", lambda api_key: None)


def _build_client(session_factory, raise_server_exceptions: bool):
    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


@pytest.fixture
def client(session_factory):
    """A TestClient whose requests use the SQLite test database."""
    with _build_client(session_factory, raise_server_exceptions=True) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def non_raising_client(session_factory):
    """A TestClient that returns the app's 500 response instead of re-raising.

    TestClient's default is to re-raise unhandled exceptions, which is handy
    for debugging but hides what an actual client would receive. Tests that
    assert on error-response *content* need this variant.
    """
    with _build_client(session_factory, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------- auth data

USER_PASSWORD = "supersecret123"


def _seed_user_and_login(client, db, username: str, email: str) -> dict[str, str]:
    """Create a user row directly and log in over HTTP.

    There is no POST /auth/register endpoint (see the comment at the top of
    app/api/v1/endpoints/auth.py) - this mirrors what scripts/create_user.py
    does in production, minus the interactive password prompt.
    """
    db.add(User(
        username=username,
        full_name=username.title(),
        email=email,
        hashed_password=hash_password(USER_PASSWORD),
    ))
    db.commit()

    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": USER_PASSWORD},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth_headers(client, db):
    """Bearer headers for the primary test user (user id 1)."""
    return _seed_user_and_login(client, db, "creator1", "creator1@example.com")


@pytest.fixture
def other_auth_headers(client, db, auth_headers):
    """Bearer headers for a second, unrelated user - used for isolation tests."""
    return _seed_user_and_login(client, db, "otheruser", "other@example.com")


# ------------------------------------------------------- instagram/analytics


def _naive_utc_now() -> datetime:
    """Now, as a naive UTC datetime.

    SQLite drops tzinfo on round-trip; seeding naive values keeps what the
    test writes identical to what the app reads back.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def db_user(db):
    """A user row created directly, for service tests that bypass HTTP."""
    user = User(
        username="creator1",
        full_name="Creator One",
        email="creator1@example.com",
        hashed_password=hash_password(USER_PASSWORD),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def connected_account(db, auth_headers):
    """A connected Instagram account for the API-registered user (id 1)."""
    return seed_connected_account(db, user_id=1)


@pytest.fixture
def connected_account_for_db_user(db, db_user):
    """The same seeded account, for service tests that never touch HTTP."""
    return seed_connected_account(db, user_id=db_user.id)


def seed_connected_account(
    db,
    user_id: int,
    instagram_user_id: str = "17841400000000000",
    media_id_prefix: str = "media",
) -> InstagramAccount:
    """Seed a connected Instagram account with media and insights.

    instagram_user_id and media_id_prefix are parameterized because both
    carry unique constraints - seeding a second account requires distinct
    values.

    Engagement rates implied by this data (reach-normalized):
      media_1 (IMAGE): (100 + 10 + 0 + 5)     / 1000 = 11.5%
      media_2 (REELS): (500 + 80 + 60 + 100)  / 8000 = 9.25%
    media_1 therefore ranks *higher* than media_2 despite far fewer likes -
    the rate is normalized by reach, so a small, highly-engaged audience
    beats a large, lightly-engaged one.
    """
    now = _naive_utc_now()
    account = InstagramAccount(
        user_id=user_id,
        instagram_user_id=instagram_user_id,
        username="creator1",
        account_type="BUSINESS",
        followers_count=1200,
        media_count=2,
        access_token="encrypted-placeholder",
        token_expires_at=None,
    )
    db.add(account)
    db.flush()

    # Follower history: 1000 -> 1200 (+200, +20%)
    db.add(AccountInsight(
        instagram_account_id=account.id, period="profile",
        metrics={"followers_count": 1000, "media_count": 1},
        fetched_at=now - timedelta(days=20),
    ))
    db.add(AccountInsight(
        instagram_account_id=account.id, period="profile",
        metrics={"followers_count": 1200, "media_count": 2},
        fetched_at=now - timedelta(hours=1),
    ))
    # Account-level daily snapshots; the later one is the "current" reading.
    db.add(AccountInsight(
        instagram_account_id=account.id, period="day",
        metrics={"reach": 3000, "impressions": 4000, "profile_views": 150, "accounts_engaged": 80},
        fetched_at=now - timedelta(days=5),
    ))
    db.add(AccountInsight(
        instagram_account_id=account.id, period="day",
        metrics={"reach": 5000, "impressions": 6000, "profile_views": 200, "accounts_engaged": 120},
        fetched_at=now - timedelta(hours=2),
    ))

    media_1 = InstagramMedia(
        instagram_account_id=account.id, media_id=f"{media_id_prefix}_1", media_type="IMAGE",
        caption="A photo", permalink="https://instagram.com/p/1",
        posted_at=now - timedelta(days=3), like_count=100, comments_count=10,
    )
    media_2 = InstagramMedia(
        instagram_account_id=account.id, media_id=f"{media_id_prefix}_2", media_type="REELS",
        caption="A reel", permalink="https://instagram.com/p/2",
        posted_at=now - timedelta(days=1), like_count=500, comments_count=80,
    )
    db.add_all([media_1, media_2])
    db.flush()

    # media_1 gets two snapshots; only the newer one should ever be used.
    db.add(MediaInsight(
        media_id=media_1.id, metrics={"reach": 800, "impressions": 900, "saves": 1},
        fetched_at=now - timedelta(days=2),
    ))
    db.add(MediaInsight(
        media_id=media_1.id, metrics={"reach": 1000, "impressions": 1200, "saves": 5},
        fetched_at=now - timedelta(hours=3),
    ))
    db.add(MediaInsight(
        media_id=media_2.id,
        metrics={"reach": 8000, "impressions": 9000, "saves": 100, "shares": 60,
                 "ig_reels_avg_watch_time": 4500},
        fetched_at=now - timedelta(hours=1),
    ))
    db.commit()
    return account


def seed_deal(db, user_id: int, **overrides) -> Deal:
    """Seed a deal with sensible defaults, overridable per test."""
    fields = {
        "title": "Summer Campaign Reel",
        "brand_name": "Acme Skincare",
        "deal_status": "confirmed",
        "payment_amount": 15000,
        "currency": "INR",
        "payment_status": "unpaid",
    }
    fields.update(overrides)
    deal = Deal(user_id=user_id, **fields)
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


# ------------------------------------------------------------- fake clients


class FakeGraphClient:
    """Stand-in for InstagramGraphClient covering the full OAuth + fetch flow."""

    def build_authorization_url(self, redirect_uri, state):
        return f"https://www.instagram.com/oauth/authorize?redirect_uri={redirect_uri}&state={state}"

    def exchange_code_for_user_token(self, code, redirect_uri):
        return {"access_token": "short_lived_token"}

    def exchange_for_long_lived_token(self, short_lived_token):
        return {"access_token": "long_lived_token", "expires_in": 5184000}

    def get_profile(self, access_token):
        return {
            "user_id": "17841400000000000", "username": "test_creator", "account_type": "BUSINESS",
            "profile_picture_url": "https://example.com/pic.jpg", "followers_count": 1000,
            "media_count": 2,
        }

    def get_media(self, instagram_user_id, access_token, limit=25):
        return [
            {"id": "media_1", "caption": "First", "media_type": "IMAGE",
             "media_url": "https://example.com/1.jpg", "permalink": "https://instagram.com/p/1",
             "timestamp": "2026-01-01T10:00:00+0000", "like_count": 10, "comments_count": 2},
            {"id": "media_2", "caption": "A reel", "media_type": "VIDEO",
             "media_url": "https://example.com/2.mp4", "permalink": "https://instagram.com/p/2",
             "timestamp": "2026-01-02T10:00:00+0000", "like_count": 20, "comments_count": 4},
        ]

    def get_media_insights(self, media_id, media_type, access_token):
        return {"reach": 400, "impressions": 500, "saves": 5}

    def get_account_insights(self, instagram_user_id, access_token, period="day"):
        return {"reach": 4000, "impressions": 5000, "profile_views": 100}


@pytest.fixture
def fake_graph_client():
    return FakeGraphClient()


class CountingStructuredLLM:
    """Fake chat model for structured-output generation.

    Records how many generations actually ran, which is how the cache tests
    prove a cache hit skipped the work rather than merely returning
    equivalent data.
    """

    def __init__(self, narratives_by_schema):
        self.narratives_by_schema = narratives_by_schema
        self.call_count = 0

    def with_structured_output(self, schema):
        return _StructuredRunnable(self, schema)


class _StructuredRunnable:
    def __init__(self, llm, schema):
        self.llm = llm
        self.schema = schema

    def invoke(self, messages):
        self.llm.call_count += 1
        return self.llm.narratives_by_schema[self.schema]


@pytest.fixture
def fake_structured_llm(monkeypatch):
    """Patch every LLM-backed service to use one counting fake model."""
    from app.schemas.insights import (
        InsightNarratives,
        RecommendationNarratives,
        ReportNarratives,
    )

    llm = CountingStructuredLLM({
        InsightNarratives: InsightNarratives(
            account_performance="Account narrative.",
            content_performance="Content narrative.",
            growth_trend="Growth narrative.",
            engagement_trend="Engagement narrative.",
            audience_behavior="Audience narrative.",
        ),
        RecommendationNarratives: RecommendationNarratives(
            best_posting_times="Post in the evening.",
            recommended_content_formats="Reels do well.",
            content_ideas=["Idea one", "Idea two"],
            posting_frequency="Three times a week.",
            engagement_reach_tips=["Tip one", "Tip two"],
        ),
        ReportNarratives: ReportNarratives(
            summary="A solid period.",
            key_strengths=["Strength one"],
            areas_for_improvement=["Improvement one"],
            actionable_next_steps=["Step one"],
        ),
    })

    for module in (insights_module, recommendation_module, report_module):
        monkeypatch.setattr(module, "build_llm", lambda api_key: llm)
    return llm
