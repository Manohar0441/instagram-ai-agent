import pytest

from app.integrations.instagram_client import InstagramAPIError
from app.models.instagram_account import InstagramAccount
from app.repositories.account_insight_repository import AccountInsightRepository
from app.repositories.instagram_account_repository import InstagramAccountRepository
from app.repositories.instagram_media_repository import InstagramMediaRepository
from app.repositories.media_insight_repository import MediaInsightRepository
from app.services.instagram_service import (
    DuplicateInstagramAccountError,
    InstagramAccountAlreadyConnectedError,
    InstagramAccountNotConnectedError,
    InstagramNotConfiguredError,
    InstagramOAuthError,
    InstagramService,
    InstagramTokenExpiredError,
    InvalidOAuthStateError,
)
from app.utils.encryption import decrypt_token
from app.utils.jwt import create_oauth_state_token

pytestmark = pytest.mark.integration


@pytest.fixture
def instagram_service(db, fake_graph_client, monkeypatch):
    from app.core.settings import settings

    monkeypatch.setattr(settings, "INSTAGRAM_APP_ID", "test-app-id")
    monkeypatch.setattr(settings, "INSTAGRAM_APP_SECRET", "test-app-secret")
    monkeypatch.setattr(
        settings, "INSTAGRAM_REDIRECT_URI", "http://localhost:8000/api/v1/instagram/callback"
    )
    return InstagramService(
        InstagramAccountRepository(db),
        InstagramMediaRepository(db),
        MediaInsightRepository(db),
        AccountInsightRepository(db),
        fake_graph_client,
    )


class TestAuthorizationUrl:
    def test_includes_a_state_token_bound_to_the_user(self, instagram_service, db_user):
        url = instagram_service.get_authorization_url(db_user.id)
        assert "state=" in url

    def test_raises_when_credentials_are_not_configured(
        self, instagram_service, db_user, monkeypatch
    ):
        from app.core.settings import settings

        monkeypatch.setattr(settings, "INSTAGRAM_APP_ID", None)
        with pytest.raises(InstagramNotConfiguredError):
            instagram_service.get_authorization_url(db_user.id)


class TestConnectAccount:
    def test_persists_the_account_from_the_oauth_exchange(
        self, instagram_service, db, db_user
    ):
        state = create_oauth_state_token(db_user.id)
        account = instagram_service.connect_account(code="auth-code", state=state)

        assert account.user_id == db_user.id
        assert account.username == "test_creator"
        assert account.followers_count == 1000

    def test_stores_the_access_token_encrypted(self, instagram_service, db_user):
        state = create_oauth_state_token(db_user.id)
        account = instagram_service.connect_account(code="auth-code", state=state)

        assert account.access_token != "long_lived_token"
        assert decrypt_token(account.access_token) == "long_lived_token"

    def test_records_a_profile_snapshot_for_growth_tracking(
        self, instagram_service, db, db_user
    ):
        from app.models.account_insight import AccountInsight

        state = create_oauth_state_token(db_user.id)
        instagram_service.connect_account(code="auth-code", state=state)

        snapshots = db.query(AccountInsight).filter(AccountInsight.period == "profile").all()
        assert len(snapshots) == 1
        assert snapshots[0].metrics["followers_count"] == 1000

    def test_rejects_an_invalid_state_token(self, instagram_service, db_user):
        with pytest.raises(InvalidOAuthStateError):
            instagram_service.connect_account(code="auth-code", state="not-a-real-token")

    def test_rejects_connecting_a_second_account(self, instagram_service, db_user):
        state = create_oauth_state_token(db_user.id)
        instagram_service.connect_account(code="auth-code", state=state)

        with pytest.raises(InstagramAccountAlreadyConnectedError):
            instagram_service.connect_account(
                code="auth-code", state=create_oauth_state_token(db_user.id)
            )

    def test_rejects_an_account_already_linked_to_someone_else(
        self, instagram_service, db, db_user
    ):
        from app.models.user import User

        other = User(
            username="other", full_name="Other",
            email="other@example.com", hashed_password="x",
        )
        db.add(other)
        db.commit()

        instagram_service.connect_account(
            code="auth-code", state=create_oauth_state_token(db_user.id)
        )
        # The fake client always resolves to the same Instagram account id.
        with pytest.raises(DuplicateInstagramAccountError):
            instagram_service.connect_account(
                code="auth-code", state=create_oauth_state_token(other.id)
            )

    def test_reports_a_helpful_error_when_no_page_is_linked(
        self, instagram_service, fake_graph_client, db_user, monkeypatch
    ):
        monkeypatch.setattr(fake_graph_client, "get_facebook_pages", lambda user_access_token: [])
        with pytest.raises(InstagramOAuthError, match="No Facebook Pages"):
            instagram_service.connect_account(
                code="auth-code", state=create_oauth_state_token(db_user.id)
            )


class TestFetchingData:
    @pytest.fixture
    def connected(self, instagram_service, db_user):
        return instagram_service.connect_account(
            code="auth-code", state=create_oauth_state_token(db_user.id)
        )

    def test_get_profile_requires_a_connection(self, instagram_service, db_user):
        with pytest.raises(InstagramAccountNotConnectedError):
            instagram_service.get_profile(db_user.id)

    def test_get_media_stores_fetched_items(self, instagram_service, db_user, connected):
        media = instagram_service.get_media(db_user.id)
        assert {m.media_id for m in media} == {"media_1", "media_2"}

    def test_get_media_captures_likes_and_comments(
        self, instagram_service, db_user, connected
    ):
        by_id = {m.media_id: m for m in instagram_service.get_media(db_user.id)}
        assert by_id["media_1"].like_count == 10
        assert by_id["media_1"].comments_count == 2

    def test_refetching_media_updates_rather_than_duplicates(
        self, instagram_service, db, db_user, connected
    ):
        from app.models.instagram_media import InstagramMedia

        instagram_service.get_media(db_user.id)
        instagram_service.get_media(db_user.id)
        assert db.query(InstagramMedia).count() == 2

    def test_parses_graph_api_timestamps(self, instagram_service, db_user, connected):
        """The Graph API returns '+0000' offsets, which Python's
        fromisoformat only accepts colon-delimited before 3.11."""
        by_id = {m.media_id: m for m in instagram_service.get_media(db_user.id)}
        assert by_id["media_1"].posted_at is not None
        assert by_id["media_1"].posted_at.year == 2026

    def test_get_insights_stores_snapshots_for_each_media(
        self, instagram_service, db_user, connected
    ):
        instagram_service.get_media(db_user.id)
        account_insight, media_pairs = instagram_service.get_insights(db_user.id)

        assert account_insight.metrics["reach"] == 4000
        assert len(media_pairs) == 2


class TestTokenHandling:
    def test_expired_token_is_reported_as_such(self, instagram_service, db, db_user):
        from datetime import datetime, timedelta, timezone

        db.add(InstagramAccount(
            user_id=db_user.id, instagram_user_id="ig-expired", facebook_page_id="p",
            username="expired", access_token="x",
            token_expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1),
        ))
        db.commit()

        with pytest.raises(InstagramTokenExpiredError):
            instagram_service.get_profile(db_user.id)

    def test_upstream_401_is_translated_to_a_token_error(
        self, instagram_service, fake_graph_client, db_user, monkeypatch
    ):
        """A revoked token surfaces as 'reconnect your account', not as a
        generic upstream failure."""
        instagram_service.connect_account(
            code="auth-code", state=create_oauth_state_token(db_user.id)
        )

        def unauthorized(**kwargs):
            raise InstagramAPIError("Invalid OAuth access token", status_code=401)

        monkeypatch.setattr(fake_graph_client, "get_profile", unauthorized)
        with pytest.raises(InstagramTokenExpiredError):
            instagram_service.get_profile(db_user.id)

    def test_other_upstream_errors_stay_upstream_errors(
        self, instagram_service, fake_graph_client, db_user, monkeypatch
    ):
        instagram_service.connect_account(
            code="auth-code", state=create_oauth_state_token(db_user.id)
        )

        def server_error(**kwargs):
            raise InstagramAPIError("Internal error", status_code=500)

        monkeypatch.setattr(fake_graph_client, "get_profile", server_error)
        with pytest.raises(InstagramOAuthError):
            instagram_service.get_profile(db_user.id)


class TestDisconnect:
    def test_removes_the_connection(self, instagram_service, db, db_user):
        """Only the account row is asserted here. The dependent media and
        insight rows are removed by ON DELETE CASCADE, which Postgres
        enforces but SQLite does not by default - asserting it against this
        test database would be verifying a fiction.
        """
        instagram_service.connect_account(
            code="auth-code", state=create_oauth_state_token(db_user.id)
        )
        instagram_service.get_media(db_user.id)
        instagram_service.disconnect_account(db_user.id)

        assert db.query(InstagramAccount).count() == 0
        with pytest.raises(InstagramAccountNotConnectedError):
            instagram_service.get_profile(db_user.id)

    def test_disconnecting_without_a_connection_raises(self, instagram_service, db_user):
        with pytest.raises(InstagramAccountNotConnectedError):
            instagram_service.disconnect_account(db_user.id)
