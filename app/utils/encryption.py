from cryptography.fernet import Fernet, InvalidToken

from app.core.settings import settings

_fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode("utf-8"))


def encrypt_token(plain_token: str) -> str:
    """Encrypt a plaintext token for storage."""
    return _fernet.encrypt(plain_token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token, raising ValueError if it cannot be decrypted."""
    try:
        return _fernet.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored access token could not be decrypted.") from exc
