import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.database import (
    create_database_engine,
    user_transaction,
    verify_runtime_role,
)
from app.main import create_app

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@pytest.mark.parametrize(
    ("is_superuser", "bypasses_rls"),
    [(True, False), (False, True)],
)
def test_runtime_role_rejects_rls_bypass_flags(
    is_superuser: bool,
    bypasses_rls: bool,
) -> None:
    async def verify() -> None:
        result = MagicMock()
        result.one.return_value = ("app_user", is_superuser, bypasses_rls)
        connection = MagicMock()
        connection.execute = AsyncMock(return_value=result)
        connection_context = MagicMock()
        connection_context.__aenter__ = AsyncMock(return_value=connection)
        connection_context.__aexit__ = AsyncMock(return_value=False)
        engine = MagicMock()
        engine.connect.return_value = connection_context

        with pytest.raises(RuntimeError, match="without BYPASSRLS"):
            await verify_runtime_role(engine)

    asyncio.run(verify())


def test_database_engine_requires_asyncpg_url() -> None:
    with pytest.raises(ValueError, match="postgresql\\+asyncpg"):
        create_database_engine("postgresql://localhost/legal_copilot")

    with pytest.raises(ValueError, match="as app_user"):
        create_database_engine(
            "postgresql+asyncpg://app_owner:unused@localhost:5432/legal_copilot"
        )


def test_user_transaction_sets_and_clears_context_as_app_user() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    url = make_url(database_url)
    if (
        url.drivername != "postgresql+asyncpg"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or url.username != "app_user"
        or url.database not in {"legal_copilot", "legal_copilot_test"}
        or not url.password
    ):
        pytest.fail(
            "TEST_DATABASE_URL must target the local Compose database as app_user"
        )

    async def verify_transaction_context() -> None:
        engine = create_database_engine(database_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        user_id = uuid4()
        other_user_id = uuid4()
        try:
            await verify_runtime_role(engine)
            async with user_transaction(session_factory, user_id) as session:
                assert await session.scalar(text("SELECT current_user")) == "app_user"
                assert (
                    await session.scalar(text("SELECT app.current_user_id()"))
                ) == user_id

            async with session_factory() as session:
                assert await session.scalar(
                    text("SELECT app.current_user_id()")
                ) is None
                await session.rollback()

            with pytest.raises(RuntimeError, match="transaction rollback check"):
                async with user_transaction(
                    session_factory,
                    other_user_id,
                ) as session:
                    assert await session.scalar(
                        text("SELECT app.current_user_id()")
                    ) == other_user_id
                    raise RuntimeError("transaction rollback check")

            async with session_factory() as session:
                assert await session.scalar(
                    text("SELECT app.current_user_id()")
                ) is None
                await session.rollback()
        finally:
            await engine.dispose()

    asyncio.run(verify_transaction_context())


def test_app_startup_checks_database_role_and_disposes_engine(monkeypatch) -> None:
    engine = MagicMock()
    engine.dispose = AsyncMock()
    verify_role = AsyncMock()
    monkeypatch.setattr("app.main.create_database_engine", lambda _url: engine)
    monkeypatch.setattr("app.main.verify_runtime_role", verify_role)
    app = create_app(
        Settings(
            app_env="test",
            database_url="postgresql+asyncpg://app_user@localhost/legal_copilot",
        )
    )

    with TestClient(app):
        assert app.state.session_factory is not None
        verify_role.assert_awaited_once_with(engine)

    engine.dispose.assert_awaited_once()


def test_app_startup_rejects_bad_database_role_and_disposes_engine(
    monkeypatch,
) -> None:
    engine = MagicMock()
    engine.dispose = AsyncMock()
    verify_role = AsyncMock(side_effect=RuntimeError("role check failed"))
    monkeypatch.setattr("app.main.create_database_engine", lambda _url: engine)
    monkeypatch.setattr("app.main.verify_runtime_role", verify_role)
    app = create_app(
        Settings(
            app_env="test",
            database_url="postgresql+asyncpg://app_user@localhost/legal_copilot",
        )
    )

    with pytest.raises(RuntimeError, match="role check failed"):
        with TestClient(app):
            pytest.fail("startup should not complete")

    verify_role.assert_awaited_once_with(engine)
    assert app.state.session_factory is None
    engine.dispose.assert_awaited_once()
