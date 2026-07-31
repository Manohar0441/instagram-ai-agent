from cryptography.fernet import Fernet, InvalidToken

from app.core.settings import settings


def _build_fernet() -> Fernet:
    """Build the Fernet cipher, failing with actionable guidance if misconfigured.

    Without this, a malformed key surfaces as a bare
    "Fernet key must be 32 url-safe base64-encoded bytes" raised from deep
    inside an import chain, which gives no hint about which setting is wrong
    or how to produce a valid one.
    """
    try:
        return Fernet(settings.TOKEN_ENCRYPTION_KEY.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY is not a valid Fernet key (it must be 32 "
            "url-safe base64-encoded bytes). Generate one with:\n"
            '  python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        ) from exc


_fernet = _build_fernet()


def encrypt_token(plain_token: str) -> str:
    """Encrypt a plaintext token for storage."""
    return _fernet.encrypt(plain_token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token, raising ValueError if it cannot be decrypted."""
    try:
        return _fernet.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored access token could not be decrypted.") from exc
