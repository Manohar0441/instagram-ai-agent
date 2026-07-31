import jwt as pyjwt
import pytest

from app.core.settings import settings
from app.utils.encryption import decrypt_token, encrypt_token
from app.utils.jwt import (
    create_access_token,
    create_oauth_state_token,
    decode_access_token,
    decode_oauth_state_token,
)
from app.utils.security import hash_password, verify_password

pytestmark = pytest.mark.unit


class TestPasswordHashing:
    def test_hash_does_not_contain_the_plaintext(self):
        hashed = hash_password("supersecret123")
        assert "supersecret123" not in hashed

    def test_correct_password_verifies(self):
        assert verify_password("supersecret123", hash_password("supersecret123"))

    def test_wrong_password_does_not_verify(self):
        assert not verify_password("wrong-password", hash_password("supersecret123"))

    def test_same_password_hashes_differently_each_time(self):
        """bcrypt salts each hash, so identical passwords must not produce
        identical digests - otherwise hashes leak which users share one."""
        assert hash_password("samepass1") != hash_password("samepass1")

    def test_verification_is_case_sensitive(self):
        assert not verify_password("SUPERSECRET123", hash_password("supersecret123"))


class TestTokenEncryption:
    def test_round_trips(self):
        assert decrypt_token(encrypt_token("instagram-token")) == "instagram-token"

    def test_ciphertext_does_not_contain_the_plaintext(self):
        assert "instagram-token" not in encrypt_token("instagram-token")

    def test_encryption_is_non_deterministic(self):
        assert encrypt_token("same-token") != encrypt_token("same-token")

    def test_undecryptable_value_raises_value_error(self):
        """Callers catch ValueError to convert this into a 'reconnect your
        account' message rather than a 500."""
        with pytest.raises(ValueError):
            decrypt_token("not-a-valid-fernet-token")


class TestAccessTokens:
    def test_round_trips_the_subject(self):
        assert decode_access_token(create_access_token("42"))["sub"] == "42"

    def test_rejects_a_token_signed_with_another_key(self):
        forged = pyjwt.encode({"sub": "1", "type": "access"}, "some-other-key", algorithm="HS256")
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token(forged)

    def test_rejects_an_expired_token(self):
        expired = pyjwt.encode(
            {"sub": "1", "exp": 1, "type": "access"},
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_access_token(expired)

    def test_rejects_an_oauth_state_token(self):
        """Regression test for a token-confusion flaw found in the Milestone 9
        review: OAuth state tokens are signed with the same key and travel in
        URLs (browser history, Referer headers to facebook.com), so they were
        accepted as API credentials."""
        state_token = create_oauth_state_token(1)
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token(state_token)

    def test_rejects_a_token_with_no_type_claim(self):
        untyped = pyjwt.encode(
            {"sub": "1"}, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token(untyped)


class TestOAuthStateTokens:
    def test_round_trips_the_user_id_as_an_int(self):
        assert decode_oauth_state_token(create_oauth_state_token(7)) == 7

    def test_rejects_an_access_token(self):
        """The converse of the confusion check: an API credential must not be
        usable to complete someone's OAuth callback."""
        with pytest.raises(pyjwt.PyJWTError):
            decode_oauth_state_token(create_access_token("1"))

    def test_rejects_a_garbage_token(self):
        with pytest.raises(pyjwt.PyJWTError):
            decode_oauth_state_token("not-a-token")
