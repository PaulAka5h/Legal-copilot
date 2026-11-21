import hashlib
import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

_password_hasher = PasswordHasher()
_dummy_password_hash = _password_hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    if password_hash is None:
        password_hash = _dummy_password_hash
    try:
        return _password_hasher.verify(password_hash, password)
    except VerificationError:
        return False


_TEMPORARY_PASSWORD_ALPHABET = string.ascii_letters + string.digits
TEMPORARY_PASSWORD_LENGTH = 16


def generate_temporary_password() -> str:
    """16 random letters and digits; at least one of each class."""
    while True:
        password = "".join(
            secrets.choice(_TEMPORARY_PASSWORD_ALPHABET)
            for _ in range(TEMPORARY_PASSWORD_LENGTH)
        )
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
        ):
            return password


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()
