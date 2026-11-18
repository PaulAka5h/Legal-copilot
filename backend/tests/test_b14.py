import secrets

from fastapi.testclient import TestClient

ORIGIN = {"Origin": "http://localhost:3000"}


def register_login(client: TestClient) -> None:
    email = f"b14-{secrets.token_hex(8)}@example.com"
    register = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={
            "email": email,
            "password": "correct horse battery staple",
            "full_name": "SAMPLE_DATA_NOT_REAL_LAW Lawyer",
        },
    )
    assert register.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": "correct horse battery staple"},
    )
    assert login.status_code == 200


def test_close_reopen_and_read_only(api_client) -> None:
    register_login(api_client)
    case = api_client.post(
        "/api/v1/cases",
        headers=ORIGIN,
        json={
            "reference_no": "SAMPLE-B14",
            "title": "SAMPLE_DATA_NOT_REAL_LAW Matter",
            "case_type": "sample",
        },
    )
    assert case.status_code == 201
    case_id = case.json()["id"]

    closed = api_client.post(
        f"/api/v1/cases/{case_id}/close",
        headers=ORIGIN,
        json={"reason": "SAMPLE_DATA_NOT_REAL_LAW test closure"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    patch = api_client.patch(
        f"/api/v1/cases/{case_id}",
        headers=ORIGIN,
        json={"title": "Changed after close"},
    )
    assert patch.status_code == 409

    reopened = api_client.post(
        f"/api/v1/cases/{case_id}/reopen",
        headers=ORIGIN,
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"
