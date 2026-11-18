import secrets
import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.exc import DBAPIError
from uuid import uuid4

from app.auth.repository import write_audit_event
from app.database import create_database_engine, user_transaction

ORIGIN = {"Origin": "http://localhost:3000"}


def register_and_login(client: TestClient) -> str:
    email = f"b10-lawyer-{secrets.token_hex(8)}@example.com"
    registered = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={
            "email": email,
            "password": "correct horse battery staple",
            "full_name": "SAMPLE_DATA_NOT_REAL_LAW Lawyer",
        },
    )
    assert registered.status_code == 201
    logged_in = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": "correct horse battery staple"},
    )
    assert logged_in.status_code == 200
    return client.get("/api/v1/me").json()["id"]


def test_audit_event_rolls_back_with_change(api_client) -> None:
    user_id = register_and_login(api_client)
    database_url = api_client.app.state.settings.database_url
    engine = create_database_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def run() -> None:
        try:
            user_uuid = __import__("uuid").UUID(user_id)
            try:
                async with user_transaction(factory, user_uuid) as session:
                    before = await session.scalar(
                        text(
                            "SELECT count(*) FROM public.audit_logs "
                            "WHERE actor_user_id = :actor AND action = 'test.roll_back'"
                        ),
                        {"actor": user_id},
                    )
                    await write_audit_event(
                        session,
                        action="test.roll_back",
                        actor_user_id=user_uuid,
                        actor_role="lawyer",
                        object_type="test",
                        object_id=None,
                        ip_address=None,
                        user_agent=None,
                        request_id=None,
                    )
                    raise RuntimeError("roll back audit")
            except RuntimeError:
                pass

            async with user_transaction(factory, user_uuid) as session:
                after = await session.scalar(
                    text(
                        "SELECT count(*) FROM public.audit_logs "
                        "WHERE actor_user_id = :actor AND action = 'test.roll_back'"
                    ),
                    {"actor": user_id},
                )
            assert after == before
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_audit_log_update_and_delete_are_denied(api_client) -> None:
    user_id = register_and_login(api_client)
    database_url = api_client.app.state.settings.database_url
    engine = create_database_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def run() -> None:
        try:
            user_uuid = __import__("uuid").UUID(user_id)
            async with user_transaction(factory, user_uuid) as session:
                row = (
                    await session.scalar(
                        text(
                            "SELECT app.write_audit_event("
                            "NULL, NULL, :actor, 'lawyer', 'test.append_only', "
                            "'test', NULL, NULL, NULL, NULL, '{}'::jsonb)"
                        ),
                        {"actor": user_uuid},
                    )
                )
            for statement in (
                text("UPDATE public.audit_logs SET action = 'changed' WHERE id = :id"),
                text("DELETE FROM public.audit_logs WHERE id = :id"),
            ):
                async with user_transaction(factory, user_uuid) as session:
                    try:
                        await session.execute(statement, {"id": row})
                        raise AssertionError("append-only audit mutation succeeded")
                    except DBAPIError:
                        await session.rollback()
        finally:
            await engine.dispose()

    import asyncio
    asyncio.run(run())
