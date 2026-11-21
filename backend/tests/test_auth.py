import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.dependencies import (
    SESSION_COOKIE_NAME,
    UserSessionDep,
)
from app.auth.security import hash_token, new_session_token
from app.database import create_database_engine, user_transaction
from app.main import create_app

ORIGIN = {"Origin": "http://localhost:3000"}


def register_lawyer(client, *, password: str = "correct horse battery staple") -> str:
    email = f"lawyer-{secrets.token_hex(8)}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={
            "email": email,
            "password": password,
            "full_name": "Sample Lawyer",
            "preferred_language": "en",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "lawyer"
    assert "password" not in response.json()
    assert "password_hash" not in response.json()
    return email


def test_registration_accepts_request_without_origin_and_rejects_short_password(api_client) -> None:
    import secrets
    # Auth endpoints must work without Origin header (production: Vercel rewrites don't send Origin)
    no_origin = api_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"origin-{secrets.token_hex(8)}@example.com",
            "password": "a sufficiently long password",
            "full_name": "Origin Test",
        },
    )
    short_password = api_client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={
            "email": f"short-{secrets.token_hex(8)}@example.com",
            "password": "short",
            "full_name": "Short Password",
        },
    )

    assert no_origin.status_code == 201
    assert short_password.status_code == 422


def test_login_is_generic_and_sets_an_opaque_secure_cookie(api_client, caplog) -> None:
    password = "correct horse battery staple"
    email = register_lawyer(api_client, password=password)

    unknown = api_client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": "unknown@example.com", "password": password},
    )
    wrong = api_client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": "incorrect password"},
    )
    with caplog.at_level(logging.INFO):
        success = api_client.post(
            "/api/v1/auth/login",
            headers=ORIGIN,
            json={"email": email, "password": password},
        )

    assert unknown.status_code == wrong.status_code == 401
    assert {
        key: unknown.json()[key] for key in ("status", "title", "detail")
    } == {
        key: wrong.json()[key] for key in ("status", "title", "detail")
    }
    assert success.status_code == 200
    assert password not in success.text
    token = api_client.cookies.get(SESSION_COOKIE_NAME)
    assert token
    assert token not in success.text
    assert token not in caplog.text
    assert SESSION_COOKIE_NAME in success.headers["set-cookie"]
    assert "httponly" in success.headers["set-cookie"].lower()
    assert "secure" in success.headers["set-cookie"].lower()
    assert "samesite=lax" in success.headers["set-cookie"].lower()
    assert password not in caplog.text
    assert api_client.get("/api/v1/me").json()["email"] == email


def test_logout_revokes_the_current_session(api_client) -> None:
    email = register_lawyer(api_client)
    api_client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": "correct horse battery staple"},
    )

    async def current_user_context(
        session: UserSessionDep,
    ) -> str:
        return str(await session.scalar(text("SELECT app.current_user_id()")))

    api_client.app.add_api_route(
        "/_test/current-user-context",
        current_user_context,
        response_model=str,
    )
    assert api_client.get("/_test/current-user-context").json() == (
        api_client.get("/api/v1/me").json()["id"]
    )

    logout = api_client.post("/api/v1/auth/logout", headers=ORIGIN)

    assert logout.status_code == 200
    assert api_client.get("/api/v1/me").status_code == 401


def test_login_rotates_the_same_account_session(api_client) -> None:
    email = register_lawyer(api_client)
    first_login = api_client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": "correct horse battery staple"},
    )
    first_token = api_client.cookies.get(SESSION_COOKIE_NAME)
    second_login = api_client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": "correct horse battery staple"},
    )
    second_token = api_client.cookies.get(SESSION_COOKIE_NAME)

    assert first_login.status_code == second_login.status_code == 200
    assert first_token and second_token and first_token != second_token
    api_client.cookies.clear()
    api_client.cookies.set(SESSION_COOKIE_NAME, first_token)
    assert api_client.get("/api/v1/me").status_code == 401
    api_client.cookies.clear()
    api_client.cookies.set(SESSION_COOKIE_NAME, second_token)
    assert api_client.get("/api/v1/me").status_code == 200


def test_expired_session_is_rejected(api_client) -> None:
    email = register_lawyer(api_client)
    api_client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": "correct horse battery staple"},
    )
    user_id = UUID(api_client.get("/api/v1/me").json()["id"])
    token = new_session_token()
    database_url = api_client.app.state.settings.database_url

    async def create_expired_session() -> None:
        engine = create_database_engine(database_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with user_transaction(session_factory, user_id) as session:
                await session.execute(
                    text(
                        """
                        INSERT INTO public.sessions
                          (user_id, token_hash, expires_at)
                        VALUES (:user_id, :token_hash, :expires_at)
                        """
                    ),
                    {
                        "user_id": user_id,
                        "token_hash": hash_token(token),
                        "expires_at": datetime.now(UTC) - timedelta(minutes=1),
                    },
                )
        finally:
            await engine.dispose()

    asyncio.run(create_expired_session())
    api_client.cookies.clear()
    api_client.cookies.set(SESSION_COOKIE_NAME, token)

    assert api_client.get("/api/v1/me").status_code == 401


def test_logout_all_revokes_sessions_on_other_clients(api_client) -> None:
    email = register_lawyer(api_client)
    api_client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": "correct horse battery staple"},
    )
    second_client = TestClient(
        create_app(api_client.app.state.settings),
        base_url="https://testserver",
    )
    with second_client:
        second_login = second_client.post(
            "/api/v1/auth/login",
            headers=ORIGIN,
            json={"email": email, "password": "correct horse battery staple"},
        )
        assert second_login.status_code == 200

        logout_all = api_client.post("/api/v1/auth/logout-all", headers=ORIGIN)

        assert logout_all.status_code == 200
        assert second_client.get("/api/v1/me").status_code == 401


def test_account_lockout_and_ip_rate_limit(api_client) -> None:
    email = register_lawyer(api_client)
    for _ in range(5):
        response = api_client.post(
            "/api/v1/auth/login",
            headers=ORIGIN,
            json={"email": email, "password": "incorrect password"},
        )
        assert response.status_code == 401

    locked = api_client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": "correct horse battery staple"},
    )
    assert locked.status_code == 401

    for index in range(4):
        api_client.post(
            "/api/v1/auth/login",
            headers=ORIGIN,
            json={
                "email": f"missing-{index}@example.com",
                "password": "irrelevant password",
            },
        )
    rate_limited = api_client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": "missing@example.com", "password": "irrelevant password"},
    )
    assert rate_limited.status_code == 429
