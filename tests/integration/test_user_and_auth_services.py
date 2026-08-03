import pytest

from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate
from app.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from app.services.user_service import (
    DuplicateEmailError,
    DuplicateUsernameError,
    UserNotFoundError,
    UserService,
)
from app.utils.jwt import create_refresh_token, decode_access_token, decode_refresh_token

pytestmark = pytest.mark.integration


@pytest.fixture
def user_service(db):
    return UserService(UserRepository(db))


@pytest.fixture
def auth_service(db):
    return AuthService(UserRepository(db))


def make_user_data(username="newuser", email="new@example.com", password="supersecret123"):
    return UserCreate(
        username=username, full_name="New User", email=email, password=password
    )


class TestCreateUser:
    def test_persists_the_user(self, user_service, db):
        user = user_service.create_user(make_user_data())
        assert user.id is not None
        assert UserRepository(db).get_by_email("new@example.com") is not None

    def test_stores_a_hash_never_the_plaintext(self, user_service):
        user = user_service.create_user(make_user_data(password="supersecret123"))
        assert user.hashed_password != "supersecret123"
        assert user.hashed_password.startswith("$2b$")

    def test_rejects_a_duplicate_username(self, user_service):
        user_service.create_user(make_user_data(username="taken", email="a@example.com"))
        with pytest.raises(DuplicateUsernameError):
            user_service.create_user(make_user_data(username="taken", email="b@example.com"))

    def test_rejects_a_duplicate_email(self, user_service):
        user_service.create_user(make_user_data(username="one", email="taken@example.com"))
        with pytest.raises(DuplicateEmailError):
            user_service.create_user(make_user_data(username="two", email="taken@example.com"))

    def test_rolls_back_so_a_rejected_duplicate_leaves_no_row(self, user_service, db):
        user_service.create_user(make_user_data(username="one", email="taken@example.com"))
        with pytest.raises(DuplicateEmailError):
            user_service.create_user(make_user_data(username="two", email="taken@example.com"))
        assert UserRepository(db).get_by_username("two") is None


class TestGetUser:
    def test_returns_an_existing_user(self, user_service):
        created = user_service.create_user(make_user_data())
        assert user_service.get_user(created.id).id == created.id

    def test_raises_for_an_unknown_id(self, user_service):
        with pytest.raises(UserNotFoundError):
            user_service.get_user(9999)


class TestAuthentication:
    def test_authenticates_valid_credentials(self, user_service, auth_service):
        user_service.create_user(make_user_data(email="me@example.com"))
        user = auth_service.authenticate("me@example.com", "supersecret123")
        assert user.email == "me@example.com"

    def test_rejects_a_wrong_password(self, user_service, auth_service):
        user_service.create_user(make_user_data(email="me@example.com"))
        with pytest.raises(InvalidCredentialsError):
            auth_service.authenticate("me@example.com", "wrong-password")

    def test_rejects_an_unknown_email(self, auth_service):
        with pytest.raises(InvalidCredentialsError):
            auth_service.authenticate("nobody@example.com", "supersecret123")

    def test_unknown_email_and_wrong_password_are_indistinguishable(
        self, user_service, auth_service
    ):
        """Different messages here would let an attacker enumerate which
        email addresses have accounts."""
        user_service.create_user(make_user_data(email="me@example.com"))

        with pytest.raises(InvalidCredentialsError) as wrong_password:
            auth_service.authenticate("me@example.com", "wrong-password")
        with pytest.raises(InvalidCredentialsError) as unknown_email:
            auth_service.authenticate("nobody@example.com", "supersecret123")

        assert str(wrong_password.value) == str(unknown_email.value)

    def test_login_issues_a_token_pair_for_the_right_user(self, user_service, auth_service):
        created = user_service.create_user(make_user_data(email="me@example.com"))
        access_token, refresh_token = auth_service.login("me@example.com", "supersecret123")
        assert decode_access_token(access_token)["sub"] == str(created.id)
        assert decode_refresh_token(refresh_token)["sub"] == str(created.id)

    def test_refresh_issues_a_new_token_pair_for_the_right_user(self, user_service, auth_service):
        created = user_service.create_user(make_user_data(email="me@example.com"))
        _, refresh_token = auth_service.login("me@example.com", "supersecret123")

        new_access_token, new_refresh_token = auth_service.refresh(refresh_token)

        assert decode_access_token(new_access_token)["sub"] == str(created.id)
        assert decode_refresh_token(new_refresh_token)["sub"] == str(created.id)

    def test_refresh_rejects_an_access_token(self, user_service, auth_service):
        """An access token must never work as a refresh token - decode_refresh_token
        enforces the "type" claim for exactly this reason."""
        user_service.create_user(make_user_data(email="me@example.com"))
        access_token, _ = auth_service.login("me@example.com", "supersecret123")

        with pytest.raises(InvalidRefreshTokenError):
            auth_service.refresh(access_token)

    def test_refresh_rejects_garbage(self, auth_service):
        with pytest.raises(InvalidRefreshTokenError):
            auth_service.refresh("not-a-real-token")

    def test_refresh_rejects_a_token_for_a_nonexistent_user(self, auth_service):
        """Covers the same "user no longer exists" branch get_current_user
        checks for access tokens - there's no user-deletion feature to
        exercise it via login/refresh, so the token is built directly."""
        from app.utils.jwt import create_refresh_token

        with pytest.raises(InvalidRefreshTokenError):
            auth_service.refresh(create_refresh_token(subject="999999"))
