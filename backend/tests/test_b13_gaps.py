"""Batch 2b: client-visibility gaps found in the close-out audit.

Covers closed-case write denial, the ``can_publish_updates`` permission, scoped and
audited publish/withdraw, typed responses, client task completion, the shared
document download path and its ``document.download`` audit event.
Synthetic data only (``SAMPLE_DATA_NOT_REAL_LAW``).
"""

import ast
import asyncio
import secrets
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine, user_transaction
from tests.test_rls_bypass import ORIGIN, PASSWORD, SAMPLE, _client, _post, _register_login

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _case(lawyer: TestClient) -> str:
    return _post(
        lawyer,
        "/api/v1/cases",
        {"reference_no": f"SAMPLE-2B-{secrets.token_hex(4)}", "title": f"{SAMPLE} Matter", "case_type": "sample"},
    )["id"]


def _invite(lawyer: TestClient, client: TestClient, case_id: str) -> None:
    profile = _post(
        lawyer,
        "/api/v1/clients",
        {"display_name": f"{SAMPLE} Client", "email": f"b2b-{secrets.token_hex(8)}@example.com"},
    )
    token = _post(lawyer, f"/api/v1/cases/{case_id}/invitations", {"client_profile_id": profile["id"]})[
        "development_token"
    ]
    assert client.post(
        "/api/v1/auth/invitations/accept",
        headers=ORIGIN,
        json={"token": token, "password": PASSWORD},
    ).status_code == 200


def _audit_actions(lawyer: TestClient, case_id: str) -> set[str]:
    response = lawyer.get(f"/api/v1/cases/{case_id}/audit")
    assert response.status_code == 200
    return {event["action"] for event in response.json()}


def test_client_can_update_own_task_and_nothing_else(api_client) -> None:
    settings = api_client.app.state.settings
    _register_login(api_client, "b2b-lawyer")
    case_id = _case(api_client)
    other_case = _case(api_client)
    with _client(settings, 21) as client, _client(settings, 22) as other_client:
        _invite(api_client, client, case_id)
        _invite(api_client, other_client, other_case)
        task = api_client.post(
            f"/api/v1/cases/{case_id}/tasks", headers=ORIGIN, json={"title": f"{SAMPLE} task"}
        )
        assert task.status_code == 201
        assert set(task.json()) == {"id", "case_id", "title", "description", "due_date", "status"}
        task_id = task.json()["id"]

        assert client.patch(f"/api/v1/client/tasks/{task_id}", json={"status": "done"}).status_code == 403
        assert other_client.patch(
            f"/api/v1/client/tasks/{task_id}", headers=ORIGIN, json={"status": "done"}
        ).status_code == 404

        done = client.patch(f"/api/v1/client/tasks/{task_id}", headers=ORIGIN, json={"status": "done"})
        assert done.status_code == 200
        assert done.json()["status"] == "done"
        tasks = client.get(f"/api/v1/client/cases/{case_id}/tasks").json()
        assert [t["status"] for t in tasks if t["id"] == task_id] == ["done"]
        assert "client_task.status_changed" in _audit_actions(api_client, case_id)

        _post(api_client, f"/api/v1/cases/{case_id}/close", {"reason": f"{SAMPLE} closed"})
        assert client.patch(
            f"/api/v1/client/tasks/{task_id}", headers=ORIGIN, json={"status": "open"}
        ).status_code == 404


def test_client_visible_writes_are_denied_on_closed_case(api_client) -> None:
    _register_login(api_client, "b2b-closed")
    case_id = _case(api_client)
    draft = _post(api_client, f"/api/v1/cases/{case_id}/client-updates", {"title": f"{SAMPLE}", "body": f"{SAMPLE}"})
    _post(api_client, f"/api/v1/cases/{case_id}/close", {"reason": f"{SAMPLE} closed"})

    attempts = [
        ("post", f"/api/v1/cases/{case_id}/client-updates", {"title": SAMPLE, "body": SAMPLE}),
        ("post", f"/api/v1/client-updates/{draft['id']}/publish", {}),
        ("post", f"/api/v1/client-updates/{draft['id']}/withdraw", {}),
        ("post", f"/api/v1/cases/{case_id}/shared-documents", {"document_id": str(uuid4()), "display_name": SAMPLE}),
        ("post", f"/api/v1/cases/{case_id}/tasks", {"title": SAMPLE}),
        ("patch", f"/api/v1/cases/{case_id}/client-visibility", {"status_label": SAMPLE}),
    ]
    for method, path, payload in attempts:
        response = getattr(api_client, method)(path, headers=ORIGIN, json=payload)
        assert response.status_code == 409, (path, response.status_code)


def test_publish_and_withdraw_are_scoped_and_audited(api_client) -> None:
    settings = api_client.app.state.settings
    _register_login(api_client, "b2b-pub")
    case_id = _case(api_client)
    draft = _post(api_client, f"/api/v1/cases/{case_id}/client-updates", {"title": SAMPLE, "body": SAMPLE})
    with _client(settings, 23) as other_lawyer:
        _register_login(other_lawyer, "b2b-intruder")
        for action in ("publish", "withdraw"):
            response = other_lawyer.post(f"/api/v1/client-updates/{draft['id']}/{action}", headers=ORIGIN, json={})
            assert response.status_code == 404
        unknown = other_lawyer.post(f"/api/v1/client-updates/{uuid4()}/publish", headers=ORIGIN, json={})
        assert unknown.status_code == 404
        assert unknown.json()["detail"] == response.json()["detail"]

    assert _post(api_client, f"/api/v1/client-updates/{draft['id']}/publish", {})["status"] == "published"
    assert _post(api_client, f"/api/v1/client-updates/{draft['id']}/withdraw", {})["status"] == "withdrawn"
    actions = _audit_actions(api_client, case_id)
    assert {"client_update.published", "client_update.withdrawn"} <= actions


def test_client_visible_writes_need_publish_permission(api_client) -> None:
    settings = api_client.app.state.settings
    lead_id = _register_login(api_client, "b2b-lead")
    case = _post(
        api_client,
        "/api/v1/cases",
        {"reference_no": f"SAMPLE-2B-{secrets.token_hex(4)}", "title": SAMPLE, "case_type": "sample"},
    )
    case_id = case["id"]
    draft = _post(api_client, f"/api/v1/cases/{case_id}/client-updates", {"title": SAMPLE, "body": SAMPLE})

    with _client(settings, 24) as team_lawyer:
        team_id = _register_login(team_lawyer, "b2b-team")

        async def join_org(factory):
            async with user_transaction(factory, lead_id) as s:
                await s.execute(
                    text(
                        "INSERT INTO public.organization_members (organization_id, user_id, org_role) "
                        "VALUES (:org, :user, 'lawyer')"
                    ),
                    {"org": UUID(case["organization_id"]), "user": team_id},
                )

        engine = create_database_engine(settings.database_url)
        try:
            asyncio.run(join_org(async_sessionmaker(engine, expire_on_commit=False)))
        finally:
            asyncio.run(engine.dispose())

        _post(api_client, f"/api/v1/cases/{case_id}/members", {"user_id": str(team_id), "role": "team_lawyer"})

        denied = [
            ("post", f"/api/v1/cases/{case_id}/client-updates", {"title": SAMPLE, "body": SAMPLE}),
            ("post", f"/api/v1/client-updates/{draft['id']}/publish", {}),
            ("post", f"/api/v1/cases/{case_id}/tasks", {"title": SAMPLE}),
        ]
        for method, path, payload in denied:
            response = getattr(team_lawyer, method)(path, headers=ORIGIN, json=payload)
            assert response.status_code == 403, (path, response.status_code)

        _post(
            api_client,
            f"/api/v1/cases/{case_id}/members",
            {"user_id": str(team_id), "role": "team_lawyer", "permissions": {"can_publish_updates": True}},
        )
        allowed = team_lawyer.post(f"/api/v1/client-updates/{draft['id']}/publish", headers=ORIGIN, json={})
        assert allowed.status_code == 200


def test_shared_document_download_is_authorized_and_audited(api_client) -> None:
    settings = api_client.app.state.settings
    _register_login(api_client, "b2b-doc")
    case_id = _case(api_client)
    other_case = _case(api_client)
    document_id = str(uuid4())
    with _client(settings, 25) as client, _client(settings, 26) as other_client:
        _invite(api_client, client, case_id)
        _invite(api_client, other_client, other_case)
        shared = api_client.post(
            f"/api/v1/cases/{case_id}/shared-documents",
            headers=ORIGIN,
            json={"document_id": document_id, "display_name": f"{SAMPLE}.pdf"},
        )
        assert shared.status_code == 200
        assert set(shared.json()) == {"id", "case_id", "document_id", "display_name", "shared_at"}

        ok = client.get(f"/api/v1/client/documents/{document_id}/download-url")
        assert ok.status_code == 200
        assert ok.json()["status"] == "NOT_CONFIGURED"
        assert other_client.get(f"/api/v1/client/documents/{document_id}/download-url").status_code == 404
        assert client.get(f"/api/v1/client/documents/{uuid4()}/download-url").status_code == 404
        assert "document.download" in _audit_actions(api_client, case_id)


def test_client_portal_imports_no_lawyer_schemas() -> None:
    source = (BACKEND_DIR / "app" / "client_portal" / "router.py").read_text(encoding="utf-8")
    imported = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "app.cases.schemas" not in imported
