"""Per-user fixed-window rate limits, stored in PostgreSQL (migration 0027).

The same mechanism as the login limiter: a counter row per (user, bucket)
updated by a SECURITY DEFINER function. Each check runs in its own committed
transaction, so a request that later fails (a rejected upload, a 404) still
counts.
"""

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import user_transaction


@dataclass(frozen=True)
class RateLimit:
    bucket: str
    limit: int
    window_seconds: int


async def consume_user_quota(session_factory: async_sessionmaker[AsyncSession], user_id: UUID,
                             rule: RateLimit) -> bool:
    async with user_transaction(session_factory, user_id) as session:
        return bool(await session.scalar(
            text("SELECT app.consume_user_rate_limit(:bucket, :limit, :window)"),
            {"bucket": rule.bucket, "limit": rule.limit, "window": rule.window_seconds},
        ))


async def enforce_user_quota(session_factory: async_sessionmaker[AsyncSession], user_id: UUID,
                             rule: RateLimit) -> None:
    """Count this request; 429 (with Retry-After as the window length) when over the limit."""
    if not await consume_user_quota(session_factory, user_id, rule):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(rule.window_seconds)},
        )
