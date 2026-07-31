import pytest

from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate
from app.services.auth_service import AuthService, InvalidCredentialsError
from app.services.user_service import (
    DuplicateEmailError,
    DuplicateUsernameError,
    UserNotFoundError,
    UserService,
)
from app.utils.jwt import decode_access_token

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

    def test_login_issues_a_token_for_the_right_user(self, user_service, auth_service):
        created = user_service.create_user(make_user_data(email="me@example.com"))
        token = auth_service.login("me@example.com", "supersecret123")
        assert decode_access_token(token)["sub"] == str(created.id)
