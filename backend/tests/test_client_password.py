"""Lawyer-set client passwords: create, forced change, reset, isolation, no leaks."""

import asyncio
import logging
import secrets
import string
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.dependencies import SESSION_COOKIE_NAME
from app.database import create_database_engine, user_transaction

ORIGIN = {"Origin": "http://localhost:3000"}
LAWYER_PASSWORD = "correct horse battery staple"
NEW_CLIENT_PASSWORD = "client chosen passphrase 42"


def _register_login(client: TestClient) -> tuple[str, str]:
    email = f"cpw-lawyer-{secrets.token_hex(8)}@example.com"
    registered = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={
            "email": email,
            "password": LAWYER_PASSWORD,
            "full_name": "SAMPLE_DATA_NOT_REAL_LAW Lawyer",
        },
    )
    assert registered.status_code == 201
    _login(client, email, LAWYER_PASSWORD)
    return email, registered.json()["id"]


def _login(client: TestClient, email: str, password: str):
    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/login", headers=ORIGIN, json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response


def _create_case(client: TestClient) -> str:
    case = client.post(
        "/api/v1/cases",
        headers=ORIGIN,
        json={
            "reference_no": f"SAMPLE-CPW-{secrets.token_hex(3)}",
            "title": "SAMPLE_DATA_NOT_REAL_LAW Matter",
            "case_type": "sample",
        },
    )
    assert case.status_code == 201
    return case.json()["id"]


def _client_email() -> str:
    return f"cpw-client-{secrets.token_hex(6)}@example.com"


def _create_client(client: TestClient, **extra) -> dict:
    response = client.post(
        "/api/v1/clients",
        headers=ORIGIN,
        json={"display_name": "SAMPLE_DATA_NOT_REAL_LAW Client", "email": _client_email(), **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _change_password(client: TestClient, current: str, new: str):
    return client.post(
        "/api/v1/auth/password/change",
        headers=ORIGIN,
        json={"current_password": current, "new_password": new},
    )


def _audit_details(database_url: str, actor_id: str) -> str:
    """All audit rows the actor wrote, as text (the actor can read its own rows)."""

    async def run() -> str:
        engine = create_database_engine(database_url)
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with user_transaction(factory, UUID(actor_id)) as session:
                rows = await session.execute(
                    text(
                        "SELECT action, details::text FROM public.audit_logs "
                        "WHERE actor_user_id = :actor"
                    ),
                    {"actor": actor_id},
                )
                return "\n".join(f"{action} {details}" for action, details in rows.all())
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_generated_password_login_forced_change_then_dashboard(api_client, caplog) -> None:
    lawyer_email, lawyer_id = _register_login(api_client)
    case_id = _create_case(api_client)

    with caplog.at_level(logging.DEBUG):
        created = _create_client(api_client, case_id=case_id)
        temporary = created["temporary_password"]
        assert len(temporary) == 16
        assert set(temporary) <= set(string.ascii_letters + string.digits)
        assert created["has_account"] is True
        assert created["linked_case_id"] == case_id

        login = _login(api_client, created["email"], temporary)
        assert login.json()["role"] == "client"
        assert login.json()["must_change_password"] is True

        for path in ("/api/v1/me", "/api/v1/client/cases"):
            blocked = api_client.get(path)
            assert blocked.status_code == 403
            assert blocked.json()["detail"].startswith("PASSWORD_CHANGE_REQUIRED")

        assert _change_password(api_client, temporary, temporary).status_code == 400
        assert _change_password(api_client, temporary, "short").status_code == 422
        assert _change_password(api_client, "wrong password!", NEW_CLIENT_PASSWORD).status_code == 400

        changed = _change_password(api_client, temporary, NEW_CLIENT_PASSWORD)
        assert changed.status_code == 200
        assert changed.json()["must_change_password"] is False

        assert api_client.get("/api/v1/me").json()["must_change_password"] is False
        cases = api_client.get("/api/v1/client/cases")
        assert cases.status_code == 200
        assert [item["id"] for item in cases.json()] == [case_id]

        # The temporary password no longer works.
        api_client.cookies.clear()
        stale = api_client.post(
            "/api/v1/auth/login",
            headers=ORIGIN,
            json={"email": created["email"], "password": temporary},
        )
        assert stale.status_code == 401
        client_id = _login(api_client, created["email"], NEW_CLIENT_PASSWORD).json()["id"]

    assert temporary not in caplog.text
    assert NEW_CLIENT_PASSWORD not in caplog.text
    database_url = api_client.app.state.settings.database_url
    lawyer_audit = _audit_details(database_url, lawyer_id)
    assert "client.account_created" in lawyer_audit
    assert "case.client_linked" in lawyer_audit
    assert temporary not in lawyer_audit
    client_audit = _audit_details(database_url, client_id)
    assert "auth.password_changed" in client_audit
    assert temporary not in client_audit
    assert NEW_CLIENT_PASSWORD not in client_audit
    del lawyer_email


def test_lawyer_chosen_password_and_logout_while_change_required(api_client) -> None:
    _register_login(api_client)
    chosen = "lawyer picked secret 99"
    created = _create_client(api_client, password=chosen)
    assert created["temporary_password"] == chosen
    assert created["linked_case_id"] is None

    _login(api_client, created["email"], chosen)
    assert api_client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 200
    assert api_client.get("/api/v1/me").status_code == 401


def test_reset_password_revokes_sessions_and_requires_change(api_client, caplog) -> None:
    lawyer_email, lawyer_id = _register_login(api_client)
    created = _create_client(api_client)
    client_id = created["id"]

    _login(api_client, created["email"], created["temporary_password"])
    assert _change_password(
        api_client, created["temporary_password"], NEW_CLIENT_PASSWORD
    ).status_code == 200
    client_token = api_client.cookies.get(SESSION_COOKIE_NAME)
    assert api_client.get("/api/v1/me").status_code == 200

    _login(api_client, lawyer_email, LAWYER_PASSWORD)
    with caplog.at_level(logging.DEBUG):
        reset = api_client.post(f"/api/v1/clients/{client_id}/password-reset", headers=ORIGIN)
    assert reset.status_code == 200
    body = reset.json()
    new_temporary = body["temporary_password"]
    assert len(new_temporary) == 16
    assert new_temporary != created["temporary_password"]
    assert body["sessions_revoked"] >= 1
    assert body["created_account"] is False
    assert new_temporary not in caplog.text

    api_client.cookies.clear()
    api_client.cookies.set(SESSION_COOKIE_NAME, client_token)
    assert api_client.get("/api/v1/me").status_code == 401

    api_client.cookies.clear()
    old = api_client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": created["email"], "password": NEW_CLIENT_PASSWORD},
    )
    assert old.status_code == 401
    relogin = _login(api_client, created["email"], new_temporary)
    assert relogin.json()["must_change_password"] is True
    assert api_client.get("/api/v1/me").status_code == 403

    audit = _audit_details(api_client.app.state.settings.database_url, lawyer_id)
    assert "client.password_reset" in audit
    assert new_temporary not in audit


def test_password_change_revokes_other_sessions(api_client) -> None:
    _register_login(api_client)
    created = _create_client(api_client)
    temporary = created["temporary_password"]

    _login(api_client, created["email"], temporary)
    first_token = api_client.cookies.get(SESSION_COOKIE_NAME)
    _login(api_client, created["email"], temporary)
    assert _change_password(api_client, temporary, NEW_CLIENT_PASSWORD).status_code == 200
    assert api_client.get("/api/v1/me").status_code == 200

    api_client.cookies.clear()
    api_client.cookies.set(SESSION_COOKIE_NAME, first_token)
    assert api_client.get("/api/v1/me").status_code == 401


def test_other_lawyers_cannot_reset_or_link(api_client) -> None:
    _register_login(api_client)
    owner_case = _create_case(api_client)
    created = _create_client(api_client)

    _register_login(api_client)
    reset = api_client.post(f"/api/v1/clients/{created['id']}/password-reset", headers=ORIGIN)
    assert reset.status_code == 404

    before = len(api_client.get("/api/v1/clients").json())
    linked = api_client.post(
        "/api/v1/clients",
        headers=ORIGIN,
        json={
            "display_name": "SAMPLE_DATA_NOT_REAL_LAW Client",
            "email": _client_email(),
            "case_id": owner_case,
        },
    )
    assert linked.status_code == 404
    # The whole create rolled back: no orphan profile or login.
    assert len(api_client.get("/api/v1/clients").json()) == before


def test_validation_and_conflicts(api_client) -> None:
    _register_login(api_client)
    no_email = api_client.post(
        "/api/v1/clients",
        headers=ORIGIN,
        json={"display_name": "SAMPLE_DATA_NOT_REAL_LAW Client", "password": "long enough pass"},
    )
    assert no_email.status_code == 422
    short = api_client.post(
        "/api/v1/clients",
        headers=ORIGIN,
        json={"display_name": "SAMPLE_DATA_NOT_REAL_LAW Client", "email": _client_email(), "password": "short"},
    )
    assert short.status_code == 422

    profile_only = api_client.post(
        "/api/v1/clients", headers=ORIGIN, json={"display_name": "SAMPLE_DATA_NOT_REAL_LAW Client"}
    )
    assert profile_only.status_code == 201
    assert profile_only.json()["temporary_password"] is None
    assert profile_only.json()["has_account"] is False
    no_email_reset = api_client.post(
        f"/api/v1/clients/{profile_only.json()['id']}/password-reset", headers=ORIGIN
    )
    assert no_email_reset.status_code == 400

    taken = _create_client(api_client)
    duplicate = api_client.post(
        "/api/v1/clients",
        headers=ORIGIN,
        json={"display_name": "SAMPLE_DATA_NOT_REAL_LAW Client", "email": taken["email"]},
    )
    assert duplicate.status_code == 409


def test_invitation_still_works_for_a_client_with_a_login(api_client) -> None:
    _register_login(api_client)
    created = _create_client(api_client)
    case_id = _create_case(api_client)
    token = _invite(api_client, case_id, created["id"])

    api_client.cookies.clear()
    accepted = api_client.post(
        "/api/v1/auth/invitations/accept",
        headers=ORIGIN,
        json={"token": token, "password": NEW_CLIENT_PASSWORD},
    )
    assert accepted.status_code == 200
    # Choosing a password through the invitation satisfies the forced change.
    me = api_client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["must_change_password"] is False
    assert [item["id"] for item in api_client.get("/api/v1/client/cases").json()] == [case_id]

def _invite(client: TestClient, case_id: str, profile_id: str) -> str:
    invite = client.post(
        f"/api/v1/cases/{case_id}/invitations",
        headers=ORIGIN,
        json={"client_profile_id": profile_id},
    )
    assert invite.status_code == 201
    return invite.json()["development_token"]


def test_invitation_revokes_temporary_password_sessions(api_client) -> None:
    lawyer_email, _ = _register_login(api_client)
    created = _create_client(api_client)
    case_id = _create_case(api_client)
    token = _invite(api_client, case_id, created["id"])

    _login(api_client, created["email"], created["temporary_password"])
    temporary_session = api_client.cookies.get(SESSION_COOKIE_NAME)

    api_client.cookies.clear()
    accepted = api_client.post(
        "/api/v1/auth/invitations/accept",
        headers=ORIGIN,
        json={"token": token, "password": NEW_CLIENT_PASSWORD},
    )
    assert accepted.status_code == 200
    api_client.cookies.clear()
    api_client.cookies.set(SESSION_COOKIE_NAME, temporary_session)
    assert api_client.get("/api/v1/me").status_code == 401
    del lawyer_email


def test_invitation_never_overwrites_a_password_the_client_chose(api_client) -> None:
    lawyer_email, _ = _register_login(api_client)
    created = _create_client(api_client)
    case_id = _create_case(api_client)

    _login(api_client, created["email"], created["temporary_password"])
    assert _change_password(
        api_client, created["temporary_password"], NEW_CLIENT_PASSWORD
    ).status_code == 200

    _login(api_client, lawyer_email, LAWYER_PASSWORD)
    token = _invite(api_client, case_id, created["id"])
    api_client.cookies.clear()
    refused = api_client.post(
        "/api/v1/auth/invitations/accept",
        headers=ORIGIN,
        json={"token": token, "password": "attacker chosen password"},
    )
    assert refused.status_code == 400
    _login(api_client, created["email"], NEW_CLIENT_PASSWORD)
