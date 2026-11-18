import base64
import hashlib
import hmac
import secrets
import struct
import time

from cryptography.fernet import Fernet


def fernet_for_key(key: str | None) -> Fernet:
    if key:
        try:
            return Fernet(key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise ValueError("MFA_ENCRYPTION_KEY must be a valid Fernet key") from exc
    material = "legal-copilot-development-mfa-key".encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def totp_code(secret: str, timestamp: int | None = None) -> str:
    now = int(time.time()) if timestamp is None else timestamp
    counter = now // 30
    digest = hmac.new(
        base64.b32decode(secret + ("=" * ((-len(secret)) % 8))),
        struct.pack(">Q", counter),
        hashlib.sha1,
    ).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1000000:06d}"


def verify_totp(secret: str, code: str) -> bool:
    now = int(time.time())
    return any(
        hmac.compare_digest(totp_code(secret, now + step * 30), code)
        for step in (-30, 0, 30)
    )
