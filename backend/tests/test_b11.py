import secrets

from fastapi.testclient import TestClient
from app.main import create_app

ORIGIN = {"Origin": "http://localhost:3000"}


def register_login(client: TestClient, name: str) -> str:
    email = f"b11-{secrets.token_hex(8)}@example.com"
    register = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={
            "email": email,
            "password": "correct horse battery staple",
            "full_name": name,
        },
    )
    assert register.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    return client.get("/api/v1/me").json()["id"]


def test_lawyer_dashboard_isolated_by_organization(api_client) -> None:
    register_login(api_client, "SAMPLE_DATA_NOT_REAL_LAW Lawyer A")
    create = api_client.post(
        "/api/v1/cases",
        headers=ORIGIN,
        json={
            "reference_no": "SAMPLE-B11-A",
            "title": "SAMPLE_DATA_NOT_REAL_LAW Overlapping Name",
            "case_type": "sample",
        },
    )
    assert create.status_code == 201

    overview = api_client.get("/api/v1/lawyer/dashboard/overview")
    activity = api_client.get("/api/v1/lawyer/dashboard/activity")
    team = api_client.get("/api/v1/lawyer/team")

    assert overview.status_code == 200
    assert overview.json()["active_cases"] >= 1
    assert activity.status_code == 200
    assert isinstance(activity.json(), list)
    assert team.status_code == 200
    assert len(team.json()) >= 1

    first_overview = overview.json()

    other = TestClient(
        create_app(api_client.app.state.settings),
        base_url="https://testserver",
    )
    with other:
        register_login(other, "SAMPLE_DATA_NOT_REAL_LAW Lawyer B")
        b_client = other.post(
            "/api/v1/clients",
            headers=ORIGIN,
            json={"display_name": "SAMPLE_DATA_NOT_REAL_LAW Overlapping Name"},
        )
        assert b_client.status_code == 201
        b_case = other.post(
            "/api/v1/cases",
            headers=ORIGIN,
            json={
                "reference_no": "SAMPLE-B11-B",
                "title": "SAMPLE_DATA_NOT_REAL_LAW Overlapping Name",
                "case_type": "sample",
            },
        )
        assert b_case.status_code == 201

        b_overview = other.get("/api/v1/lawyer/dashboard/overview")
        assert b_overview.status_code == 200
        assert b_overview.json()["active_cases"] == 1
        assert b_overview.json()["total_matters"] == 1
        assert b_overview.json()["total_clients"] == 1

    assert first_overview["active_cases"] == 1
