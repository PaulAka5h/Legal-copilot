import secrets

from fastapi.testclient import TestClient

from app.main import create_app

ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "correct horse battery staple"


def register_login(client: TestClient, label: str) -> str:
    email = f"{label}-{secrets.token_hex(8)}@example.com"
    register = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": f"SAMPLE_DATA_NOT_REAL_LAW {label}",
        },
    )
    assert register.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": PASSWORD},
    )
    assert login.status_code == 200
    return client.get("/api/v1/me").json()["id"]


def create_case(client: TestClient, reference: str) -> str:
    response = client.post(
        "/api/v1/cases",
        headers=ORIGIN,
        json={
            "reference_no": reference,
            "title": "SAMPLE_DATA_NOT_REAL_LAW Matter",
            "case_type": "sample",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_invite_and_accept(
    lawyer: TestClient,
    client: TestClient,
    case_id: str,
    label: str,
) -> None:
    profile = lawyer.post(
        "/api/v1/clients",
        headers=ORIGIN,
        json={
            "display_name": f"SAMPLE_DATA_NOT_REAL_LAW {label}",
            "email": f"{label}-{secrets.token_hex(8)}@example.com",
        },
    )
    assert profile.status_code == 201
    profile_id = profile.json()["id"]

    invite = lawyer.post(
        f"/api/v1/cases/{case_id}/invitations",
        headers=ORIGIN,
        json={"client_profile_id": profile_id},
    )
    assert invite.status_code == 201
    token = invite.json()["development_token"]

    accept = client.post(
        "/api/v1/auth/invitations/accept",
        headers=ORIGIN,
        json={"token": token, "password": PASSWORD},
    )
    assert accept.status_code == 200


def test_phase2_two_tenant_exit_scenario(api_client) -> None:
    lawyer_a = api_client
    register_login(lawyer_a, "exit-lawyer-a")
    case_a1 = create_case(lawyer_a, "SAMPLE-P2-A1")
    case_a2 = create_case(lawyer_a, "SAMPLE-P2-A2")

    lawyer_b = TestClient(
        create_app(lawyer_a.app.state.settings),
        base_url="https://testserver",
    )
    client_a = TestClient(
        create_app(lawyer_a.app.state.settings),
        base_url="https://testserver",
    )
    client_b = TestClient(
        create_app(lawyer_a.app.state.settings),
        base_url="https://testserver",
    )

    with lawyer_b:
        register_login(lawyer_b, "exit-lawyer-b")
        case_b1 = create_case(lawyer_b, "SAMPLE-P2-B1")
        case_b2 = create_case(lawyer_b, "SAMPLE-P2-B2")

        with client_a:
            create_invite_and_accept(lawyer_a, client_a, case_a1, "exit-client-a")
            assert client_a.get("/api/v1/client/cases").status_code == 200
            assert client_a.get(
                f"/api/v1/client/cases/{case_b1}/updates"
            ).status_code == 404
            assert client_a.get(
                f"/api/v1/client/cases/{case_a1}/hearing"
            ).status_code == 200

            draft = lawyer_a.post(
                f"/api/v1/cases/{case_a1}/client-updates",
                headers=ORIGIN,
                json={
                    "title": "SAMPLE_DATA_NOT_REAL_LAW Published Update",
                    "body": "SAMPLE_DATA_NOT_REAL_LAW",
                    "language": "en",
                },
            )
            assert draft.status_code == 201
            update_id = draft.json()["id"]
            published = lawyer_a.post(
                f"/api/v1/client-updates/{update_id}/publish",
                headers=ORIGIN,
            )
            assert published.status_code == 200
            updates = client_a.get(
                f"/api/v1/client/cases/{case_a1}/updates"
            )
            assert updates.status_code == 200
            assert len(updates.json()) == 1

            withdrawn = lawyer_a.post(
                f"/api/v1/client-updates/{update_id}/withdraw",
                headers=ORIGIN,
            )
            assert withdrawn.status_code == 200
            assert client_a.get(
                f"/api/v1/client/cases/{case_a1}/updates"
            ).json() == []

            wrong_role = client_a.get("/api/v1/lawyer/dashboard/overview")
            assert wrong_role.status_code == 403

            close = lawyer_a.post(
                f"/api/v1/cases/{case_a1}/close",
                headers=ORIGIN,
                json={"reason": "SAMPLE_DATA_NOT_REAL_LAW exit gate"},
            )
            assert close.status_code == 200
            assert client_a.get(
                f"/api/v1/client/cases/{case_a1}/updates"
            ).status_code == 404

            reopen = lawyer_a.post(
                f"/api/v1/cases/{case_a1}/reopen",
                headers=ORIGIN,
            )
            assert reopen.status_code == 200

        with client_b:
            create_invite_and_accept(lawyer_b, client_b, case_b1, "exit-client-b")
            assert client_b.get("/api/v1/client/cases").status_code == 200
            assert client_b.get(
                f"/api/v1/client/cases/{case_a1}/updates"
            ).status_code == 404
            assert client_b.get(
                f"/api/v1/client/cases/{case_a2}/updates"
            ).status_code == 404

        for not_owned in (case_b1, case_b2):
            response = lawyer_a.get(f"/api/v1/cases/{not_owned}")
            assert response.status_code == 404
