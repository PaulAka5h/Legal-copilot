"""Fixed-window rate limits backed by ``app.consume_rate_limit`` (migration 0012).

Each check runs in its own committed transaction, so attempts count even when the
request later fails and its main transaction rolls back. Keys are hashed in the
database; raw emails and IPs are never stored.
"""

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

WINDOW_SECONDS = 15 * 60


@dataclass(frozen=True)
class RateLimit:
    bucket: str
    limit: int
    window_seconds: int = WINDOW_SECONDS


PASSWORD_FORGOT_PER_IP = RateLimit("password_forgot_ip", 10)
PASSWORD_FORGOT_PER_ACCOUNT = RateLimit("password_forgot_account", 3)
PASSWORD_RESET_PER_IP = RateLimit("password_reset_ip", 10)
MFA_VERIFY_PER_USER = RateLimit("mfa_verify_user", 5)

TOO_MANY_REQUESTS = "Too many requests. Try again later."


async def enforce_rate_limit(
    session_factory: async_sessionmaker[AsyncSession],
    rule: RateLimit,
    key: str,
) -> None:
    async with session_factory() as session, session.begin():
        allowed = await session.scalar(
            text("SELECT app.consume_rate_limit(:bucket, :key, :limit, :window)"),
            {
                "bucket": rule.bucket,
                "key": key,
                "limit": rule.limit,
                "window": rule.window_seconds,
            },
        )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=TOO_MANY_REQUESTS,
        )
