import hashlib
import secrets

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


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()
