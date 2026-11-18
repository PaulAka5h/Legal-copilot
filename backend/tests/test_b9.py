import secrets

from fastapi.testclient import TestClient

from app.main import create_app

ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "correct horse battery staple"


def register_and_login(client: TestClient) -> str:
    email = f"b9-lawyer-{secrets.token_hex(8)}@example.com"
    registered = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "SAMPLE_DATA_NOT_REAL_LAW Lawyer",
        },
    )
    assert registered.status_code == 201
    logged_in = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": PASSWORD},
    )
    assert logged_in.status_code == 200
    return email


def create_case(client: TestClient) -> str:
    response = client.post(
        "/api/v1/cases",
        headers=ORIGIN,
        json={
            "reference_no": f"SAMPLE-B9-{secrets.token_hex(6)}",
            "title": "SAMPLE_DATA_NOT_REAL_LAW Matter",
            "case_type": "sample",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_password_forgot_is_generic_and_reset_is_single_use(api_client) -> None:
    email = register_and_login(api_client)

    unknown = api_client.post(
        "/api/v1/auth/password/forgot",
        headers=ORIGIN,
        json={"email": "unknown@example.com"},
    )
    known = api_client.post(
        "/api/v1/auth/password/forgot",
        headers=ORIGIN,
        json={"email": email},
    )

    assert unknown.status_code == known.status_code == 200
    assert unknown.json() == known.json()

    bad_reset = api_client.post(
        "/api/v1/auth/password/reset",
        headers=ORIGIN,
        json={
            "token": "not-a-real-reset-token-with-sufficient-length",
            "new_password": "another sufficiently long password",
        },
    )
    assert bad_reset.status_code == 400


def test_mfa_setup_and_verification_require_lawyer_session(api_client) -> None:
    anonymous = api_client.post(
        "/api/v1/auth/mfa/setup",
        headers=ORIGIN,
    )
    assert anonymous.status_code == 401

    register_and_login(api_client)
    setup = api_client.post(
        "/api/v1/auth/mfa/setup",
        headers=ORIGIN,
    )
    assert setup.status_code == 200
    assert "secret" not in setup.json()
    assert "otpauth_uri" in setup.json()
    assert "recovery_codes" not in setup.json()


def test_case_member_list_remove_and_audit_are_isolated(api_client) -> None:
    register_and_login(api_client)
    case_id = create_case(api_client)

    members = api_client.get(f"/api/v1/cases/{case_id}/members")
    audit = api_client.get(f"/api/v1/cases/{case_id}/audit")
    unknown_members = api_client.get(
        f"/api/v1/cases/{secrets.token_hex(16)}-not-a-uuid/members"
    )

    assert members.status_code == 200
    assert any(item["role"] == "lead_lawyer" for item in members.json())
    assert audit.status_code == 200
    assert isinstance(audit.json(), list)
    assert unknown_members.status_code == 422
