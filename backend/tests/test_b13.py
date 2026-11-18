import secrets

from fastapi.testclient import TestClient

ORIGIN = {"Origin": "http://localhost:3000"}


def register_login(client: TestClient) -> None:
    email = f"b13-{secrets.token_hex(8)}@example.com"
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


def test_client_update_publish_withdraw_lifecycle(api_client) -> None:
    register_login(api_client)
    case = api_client.post(
        "/api/v1/cases",
        headers=ORIGIN,
        json={
            "reference_no": "SAMPLE-B13",
            "title": "SAMPLE_DATA_NOT_REAL_LAW Matter",
            "case_type": "sample",
        },
    )
    assert case.status_code == 201
    case_id = case.json()["id"]

    draft = api_client.post(
        f"/api/v1/cases/{case_id}/client-updates",
        headers=ORIGIN,
        json={
            "title": "SAMPLE_DATA_NOT_REAL_LAW Update",
            "body": "SAMPLE_DATA_NOT_REAL_LAW draft body",
            "language": "en",
        },
    )
    assert draft.status_code == 201
    assert draft.json()["status"] == "draft"
    update_id = draft.json()["id"]

    published = api_client.post(
        f"/api/v1/client-updates/{update_id}/publish",
        headers=ORIGIN,
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    withdrawn = api_client.post(
        f"/api/v1/client-updates/{update_id}/withdraw",
        headers=ORIGIN,
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"
