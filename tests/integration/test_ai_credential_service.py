import pytest

from app.core.settings import settings
from app.repositories.user_repository import UserRepository
from app.services.ai_credential_service import AICredentialService, AIUserNotFoundError
from app.services.ai_generation import AINotConfiguredError
from app.utils.encryption import encrypt_token

pytestmark = pytest.mark.integration

USER_KEY = "AQ.Ab8RN6JusersOwnGeminiKeyValue01"


@pytest.fixture
def credential_service(db):
    return AICredentialService(UserRepository(db))


class TestResolution:
    """The precedence rule is the whole point of this service, so each
    branch of it is pinned separately."""

    def test_a_users_own_key_wins_over_the_server_key(
        self, credential_service, db, db_user
    ):
        db_user.gemini_api_key = encrypt_token(USER_KEY)
        db.commit()

        assert credential_service.resolve_api_key(db_user.id) == USER_KEY

    def test_falls_back_to_the_server_key(self, credential_service, db_user):
        """_configure_ai sets GOOGLE_API_KEY, and this user stored nothing."""
        assert credential_service.resolve_api_key(db_user.id) == settings.GOOGLE_API_KEY

    def test_raises_when_there_is_no_key_anywhere(
        self, credential_service, db_user, monkeypatch
    ):
        monkeypatch.setattr(settings, "GOOGLE_API_KEY", None)

        with pytest.raises(AINotConfiguredError):
            credential_service.resolve_api_key(db_user.id)

    def test_an_undecryptable_key_does_not_fall_through_to_the_server_key(
        self, credential_service, db, db_user
    ):
        """If TOKEN_ENCRYPTION_KEY was rotated, silently using the server
        key would bill the wrong account - so this must be a hard stop even
        though a usable fallback exists."""
        db_user.gemini_api_key = "not-valid-fernet-ciphertext"
        db.commit()

        with pytest.raises(AINotConfiguredError):
            credential_service.resolve_api_key(db_user.id)


class TestStatus:
    def test_reports_the_server_source_when_the_user_has_no_key(
        self, credential_service, db_user
    ):
        status = credential_service.get_status(db_user.id)
        assert status.configured is True
        assert status.has_own_key is False
        assert status.source == "server"
        assert status.hint is None

    def test_reports_the_user_source_and_a_hint(self, credential_service, db_user):
        credential_service.set_api_key(db_user.id, USER_KEY)

        status = credential_service.get_status(db_user.id)
        assert status.has_own_key is True
        assert status.source == "user"
        assert status.hint == USER_KEY[-4:]
        assert status.model == settings.GEMINI_MODEL

    def test_reports_nothing_configured_without_any_key(
        self, credential_service, db_user, monkeypatch
    ):
        monkeypatch.setattr(settings, "GOOGLE_API_KEY", None)

        status = credential_service.get_status(db_user.id)
        assert status.configured is False
        assert status.source == "none"

    def test_an_undecryptable_key_has_no_hint(self, credential_service, db, db_user):
        db_user.gemini_api_key = "not-valid-fernet-ciphertext"
        db.commit()

        assert credential_service.get_status(db_user.id).hint is None


class TestPersistence:
    def test_the_stored_key_is_encrypted_at_rest(self, credential_service, db, db_user):
        credential_service.set_api_key(db_user.id, USER_KEY)
        db.refresh(db_user)

        assert db_user.gemini_api_key is not None
        assert USER_KEY not in db_user.gemini_api_key

    def test_setting_a_key_replaces_the_previous_one(
        self, credential_service, db_user
    ):
        replacement = "AQ.Ab8RN6JreplacementGeminiKey0002"

        credential_service.set_api_key(db_user.id, USER_KEY)
        credential_service.set_api_key(db_user.id, replacement)

        assert credential_service.resolve_api_key(db_user.id) == replacement

    def test_clearing_removes_the_key(self, credential_service, db, db_user):
        credential_service.set_api_key(db_user.id, USER_KEY)
        credential_service.clear_api_key(db_user.id)
        db.refresh(db_user)

        assert db_user.gemini_api_key is None

    def test_operations_on_a_missing_user_raise(self, credential_service):
        with pytest.raises(AIUserNotFoundError):
            credential_service.set_api_key(9999, USER_KEY)

        with pytest.raises(AIUserNotFoundError):
            credential_service.clear_api_key(9999)
