"""Batch 3: authentication hardening (TRD §4, Security.md §4).

Idle timeout, rate limits on password reset and MFA, session rotation when MFA is
enabled, TOTP drift window, real client sessions, ``can_run_ai`` enforcement and
auth audit events. Runs as ``app_user``; synthetic data only.
"""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.dependencies import SESSION_COOKIE_NAME
from app.auth.mfa import totp_code, verify_totp
from app.auth.security import hash_token, new_session_token
from app.database import create_database_engine, user_transaction
from tests.test_b13_gaps import _case, _invite
from tests.test_rls_bypass import ORIGIN, PASSWORD, SAMPLE, _client, _post, _register_login


def _run_as(database_url: str, user_id: UUID, sql: str, params: dict):
    async def run():
        engine = create_database_engine(database_url)
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with user_transaction(factory, user_id) as session:
                result = await session.execute(text(sql), params)
                return result.all() if result.returns_rows else None
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _mfa_secret(client: TestClient) -> str:
    setup = client.post("/api/v1/auth/mfa/setup", headers=ORIGIN)
    assert setup.status_code == 200
    return parse_qs(urlsplit(setup.json()["otpauth_uri"]).query)["secret"][0]


def test_totp_accepts_one_step_of_drift_but_not_old_codes() -> None:
    secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
    now = int(time.time())
    assert verify_totp(secret, totp_code(secret, now))
    assert verify_totp(secret, totp_code(secret, now - 30))
    assert not verify_totp(secret, totp_code(secret, now - 900))


def test_idle_session_is_rejected(api_client) -> None:
    user_id = _register_login(api_client, "idle")
    token = new_session_token()
    _run_as(
        api_client.app.state.settings.database_url,
        user_id,
        "INSERT INTO public.sessions (user_id, token_hash, expires_at, last_seen_at) "
        "VALUES (:user_id, :token_hash, :expires_at, :last_seen_at)",
        {
            "user_id": user_id,
            "token_hash": hash_token(token),
            "expires_at": datetime.now(UTC) + timedelta(hours=6),
            "last_seen_at": datetime.now(UTC) - timedelta(hours=2),
        },
    )
    api_client.cookies.clear()
    api_client.cookies.set(SESSION_COOKIE_NAME, token)

    assert api_client.get("/api/v1/me").status_code == 401


def test_password_forgot_is_rate_limited_per_account_without_leaking_existence(api_client) -> None:
    settings = api_client.app.state.settings
    _register_login(api_client, "forgot")
    known = api_client.get("/api/v1/me").json()["email"]
    unknown = f"nobody-{uuid4().hex}@example.com"
    for email in (known, unknown):
        with _client(settings, 31) as fresh:
            replies = [
                fresh.post("/api/v1/auth/password/forgot", headers=ORIGIN, json={"email": email})
                for _ in range(4)
            ]
        assert [r.status_code for r in replies] == [200, 200, 200, 429]
        assert replies[0].json() == {"message": "If the account exists, a reset link was sent."}
        assert replies[3].headers["content-type"].startswith("application/problem+json")


def test_password_reset_is_rate_limited_per_ip(api_client) -> None:
    codes = [
        api_client.post(
            "/api/v1/auth/password/reset",
            headers=ORIGIN,
            json={"token": new_session_token(), "new_password": "another long password"},
        ).status_code
        for _ in range(11)
    ]
    assert codes[:10] == [400] * 10
    assert codes[10] == 429


def test_mfa_verify_is_rate_limited_per_user(api_client) -> None:
    _register_login(api_client, "mfa-limit")
    _mfa_secret(api_client)
    codes = [
        api_client.post("/api/v1/auth/mfa/verify", headers=ORIGIN, json={"code": "000000"}).status_code
        for _ in range(6)
    ]
    assert codes[:5] == [400] * 5
    assert codes[5] == 429


def test_enabling_mfa_rotates_the_session_and_revokes_other_sessions(api_client) -> None:
    settings = api_client.app.state.settings
    email = f"rotate-{uuid4().hex}@example.com"
    assert api_client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": PASSWORD, "full_name": f"{SAMPLE} rotate"},
    ).status_code == 201
    with _client(settings, 32) as other_device:
        for client in (api_client, other_device):
            assert client.post(
                "/api/v1/auth/login", headers=ORIGIN, json={"email": email, "password": PASSWORD}
            ).status_code == 200
        old_token = api_client.cookies.get(SESSION_COOKIE_NAME)
        secret = _mfa_secret(api_client)

        verified = api_client.post(
            "/api/v1/auth/mfa/verify", headers=ORIGIN, json={"code": totp_code(secret)}
        )
        assert verified.status_code == 200
        new_token = api_client.cookies.get(SESSION_COOKIE_NAME)
        assert new_token and new_token != old_token
        assert api_client.get("/api/v1/me").status_code == 200
        assert other_device.get("/api/v1/me").status_code == 401

    api_client.cookies.clear()
    api_client.cookies.set(SESSION_COOKIE_NAME, old_token)
    assert api_client.get("/api/v1/me").status_code == 401


def test_real_client_session_is_confined_to_the_client_namespace(api_client) -> None:
    settings = api_client.app.state.settings
    _register_login(api_client, "real-client-lawyer")
    case_id = _case(api_client)
    with _client(settings, 33) as client:
        _invite(api_client, client, case_id)
        me = client.get("/api/v1/me")
        assert me.status_code == 200 and me.json()["role"] == "client"
        assert client.get("/api/v1/client/cases").status_code == 200
        for path in (
            "/api/v1/cases",
            "/api/v1/clients",
            f"/api/v1/cases/{case_id}",
            f"/api/v1/cases/{case_id}/timeline",
            "/api/v1/lawyer/dashboard/overview",
        ):
            assert client.get(path).status_code == 403, path


def test_ai_runs_require_can_run_ai(api_client) -> None:
    settings = api_client.app.state.settings
    lead_id = _register_login(api_client, "ai-lead")
    case = api_client.get(f"/api/v1/cases/{_case(api_client)}").json()
    with _client(settings, 34) as team_lawyer:
        team_id = _register_login(team_lawyer, "ai-team")
        _run_as(
            settings.database_url,
            lead_id,
            "INSERT INTO public.organization_members (organization_id, user_id, org_role) "
            "VALUES (:org, :user, 'lawyer')",
            {"org": UUID(case["organization_id"]), "user": team_id},
        )
        _post(api_client, f"/api/v1/cases/{case['id']}/members", {"user_id": str(team_id), "role": "team_lawyer"})

        run_paths = [
            f"/api/v1/cases/{case['id']}/analysis-runs",
            f"/api/v1/cases/{case['id']}/strategies/generate",
            f"/api/v1/cases/{case['id']}/strategies/report",
        ]
        for path in run_paths:
            assert team_lawyer.post(path, headers=ORIGIN, json={}).status_code == 403, path
        assert team_lawyer.get(f"/api/v1/cases/{case['id']}/timeline").status_code == 200

        _post(
            api_client,
            f"/api/v1/cases/{case['id']}/members",
            {"user_id": str(team_id), "role": "team_lawyer", "permissions": {"can_run_ai": True}},
        )
        allowed = team_lawyer.post(run_paths[0], headers=ORIGIN, json={})
        assert allowed.status_code == 201


def test_auth_and_membership_events_are_audited(api_client) -> None:
    settings = api_client.app.state.settings
    email = f"audit-{uuid4().hex}@example.com"
    api_client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": PASSWORD, "full_name": f"{SAMPLE} audit"},
    )
    api_client.post("/api/v1/auth/login", headers=ORIGIN, json={"email": email, "password": "wrong password!"})
    api_client.post("/api/v1/auth/login", headers=ORIGIN, json={"email": email, "password": PASSWORD})
    user_id = UUID(api_client.get("/api/v1/me").json()["id"])
    secret = _mfa_secret(api_client)
    api_client.post("/api/v1/auth/mfa/verify", headers=ORIGIN, json={"code": totp_code(secret)})

    case = api_client.get(f"/api/v1/cases/{_case(api_client)}").json()
    with _client(settings, 35) as team_lawyer:
        team_id = _register_login(team_lawyer, "audit-team")
    _run_as(
        settings.database_url,
        user_id,
        "INSERT INTO public.organization_members (organization_id, user_id, org_role) "
        "VALUES (:org, :user, 'lawyer')",
        {"org": UUID(case["organization_id"]), "user": team_id},
    )
    member = _post(api_client, f"/api/v1/cases/{case['id']}/members", {"user_id": str(team_id), "role": "team_lawyer"})
    assert api_client.delete(f"/api/v1/cases/{case['id']}/members/{member['id']}", headers=ORIGIN).status_code == 200
    api_client.post("/api/v1/auth/logout", headers=ORIGIN)

    rows = _run_as(
        settings.database_url,
        user_id,
        "SELECT action FROM public.audit_logs WHERE actor_user_id = :user_id",
        {"user_id": user_id},
    )
    actions = {row[0] for row in rows}
    assert {
        "auth.registered",
        "auth.login_failed",
        "auth.login_succeeded",
        "auth.mfa_setup",
        "auth.mfa_enabled",
        "case.member_added",
        "case.member_revoked",
        "auth.logout",
    } <= actions
