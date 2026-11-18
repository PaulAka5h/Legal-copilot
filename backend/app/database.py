from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_SET_USER_CONTEXT = text(
    "SELECT set_config('app.current_user_id', :user_id, true)"
)
_RUNTIME_ROLE_CHECK = text(
    "SELECT current_user, rolsuper, rolbypassrls "
    "FROM pg_roles WHERE rolname = current_user"
)


def create_database_engine(database_url: str) -> AsyncEngine:
    url = make_url(database_url)
    if url.drivername != "postgresql+asyncpg" or url.username != "app_user":
        raise ValueError("DATABASE_URL must use postgresql+asyncpg as app_user")
    return create_async_engine(database_url, pool_pre_ping=True)


async def verify_runtime_role(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        role_name, is_superuser, bypasses_rls = (
            await connection.execute(_RUNTIME_ROLE_CHECK)
        ).one()
    if role_name != "app_user" or is_superuser or bypasses_rls:
        raise RuntimeError(
            "DATABASE_URL must connect as a non-superuser app_user without BYPASSRLS"
        )


@asynccontextmanager
async def user_transaction(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: UUID,
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                _SET_USER_CONTEXT,
                {"user_id": str(user_id)},
            )
            yield session
