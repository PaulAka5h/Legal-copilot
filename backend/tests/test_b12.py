import secrets

from fastapi.testclient import TestClient

ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "correct horse battery staple"


def register_login(client: TestClient) -> None:
    email = f"b12-{secrets.token_hex(8)}@example.com"
    register = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "SAMPLE_DATA_NOT_REAL_LAW Lawyer",
        },
    )
    assert register.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": PASSWORD},
    )
    assert login.status_code == 200


def test_invitation_accept_creates_real_client_session(api_client) -> None:
    register_login(api_client)
    client_profile = api_client.post(
        "/api/v1/clients",
        headers=ORIGIN,
        json={
            "display_name": "SAMPLE_DATA_NOT_REAL_LAW Client",
            "email": f"b12-client-{secrets.token_hex(6)}@example.com",
        },
    )
    assert client_profile.status_code == 201
    client_id = client_profile.json()["id"]

    case = api_client.post(
        "/api/v1/cases",
        headers=ORIGIN,
        json={
            "reference_no": "SAMPLE-B12",
            "title": "SAMPLE_DATA_NOT_REAL_LAW Matter",
            "case_type": "sample",
        },
    )
    assert case.status_code == 201
    case_id = case.json()["id"]

    invite = api_client.post(
        f"/api/v1/cases/{case_id}/invitations",
        headers=ORIGIN,
        json={"client_profile_id": client_id},
    )
    assert invite.status_code == 201
    token = invite.json().get("development_token")
    assert token

    api_client.cookies.clear()
    accept = api_client.post(
        "/api/v1/auth/invitations/accept",
        headers=ORIGIN,
        json={"token": token, "password": PASSWORD},
    )
    assert accept.status_code == 200
    assert accept.json()["role"] == "client"
    assert api_client.get("/api/v1/me").json()["role"] == "client"

    reused = api_client.post(
        "/api/v1/auth/invitations/accept",
        headers=ORIGIN,
        json={"token": token, "password": PASSWORD},
    )
    assert reused.status_code == 400
