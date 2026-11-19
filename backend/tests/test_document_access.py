"""Batch 5: the document authorization contract Dev 2's document routes must use.

No document endpoints exist yet, so the helpers in ``app.cases.document_access``
are exercised through probe routes mounted only in this test's app. The probes
mirror the TRD routes: case-path list/upload and ``/documents/{id}``-style
read/write that resolve the owning case first.
"""

import secrets
from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

import pytest
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.auth.dependencies import LawyerDep, UserSessionDep, require_same_origin_for_writes
from app.cases.document_access import (
    DOCUMENT_AUDIT_ACTIONS,
    DocumentReadDep,
    DocumentWriteDep,
    authorize_document_read,
    authorize_document_write,
    check_document_delete,
)
from app.main import create_app
from tests.test_auth_hardening import _run_as
from tests.test_b13_gaps import _invite
from tests.test_rls_bypass import ORIGIN, SAMPLE, _post, _register_login


class Probe(BaseModel):
    ok: bool


probe = APIRouter(prefix="/api/v1/_probe", dependencies=[Depends(require_same_origin_for_writes)])


@probe.get("/cases/{case_id}/documents", response_model=Probe)
async def list_documents(access: DocumentReadDep) -> Probe:
    return Probe(ok=True)


@probe.post("/cases/{case_id}/documents", response_model=Probe)
async def upload_document(access: DocumentWriteDep) -> Probe:
    return Probe(ok=True)


@probe.get("/documents/{case_ref}", response_model=Probe)
async def read_document(
    case_ref: Annotated[str, Path()], user: LawyerDep, session: UserSessionDep
) -> Probe:
    # Stands in for "SELECT case_id FROM documents WHERE id = :id" (None = no row).
    case_id = None if case_ref == "missing" else UUID(case_ref)
    await authorize_document_read(session, acting_user_id=user.id, case_id=case_id)
    return Probe(ok=True)


@probe.post("/documents/{case_ref}/reprocess", response_model=Probe)
async def reprocess_document(
    case_ref: Annotated[str, Path()], user: LawyerDep, session: UserSessionDep
) -> Probe:
    case_id = None if case_ref == "missing" else UUID(case_ref)
    await authorize_document_write(session, acting_user_id=user.id, case_id=case_id)
    return Probe(ok=True)


def _app(settings):
    app = create_app(settings)
    app.include_router(probe)
    return app


def _tc(settings, octet: int) -> TestClient:
    # One app per client: each TestClient runs the app lifespan, which owns the
    # database engine, so clients must not share an app instance.
    return TestClient(
        _app(settings),
        base_url="https://testserver",
        client=(f"127.0.{secrets.randbelow(200) + 20}.{octet}", 50000),
    )


def _calls(tc: TestClient, case_id: str) -> dict[str, int]:
    return {
        "list": tc.get(f"/api/v1/_probe/cases/{case_id}/documents").status_code,
        "upload": tc.post(f"/api/v1/_probe/cases/{case_id}/documents", headers=ORIGIN).status_code,
        "read": tc.get(f"/api/v1/_probe/documents/{case_id}").status_code,
        "write": tc.post(f"/api/v1/_probe/documents/{case_id}/reprocess", headers=ORIGIN).status_code,
    }


def test_document_access_contract(api_client) -> None:
    settings = api_client.app.state.settings
    with (
        _tc(settings, 61) as lead,
        _tc(settings, 62) as team,
        _tc(settings, 63) as other,
        _tc(settings, 64) as client,
    ):
        lead_id = _register_login(lead, "doc-lead")
        case = _post(
            lead,
            "/api/v1/cases",
            {"reference_no": f"SAMPLE-DOC-{secrets.token_hex(4)}", "title": SAMPLE, "case_type": "sample"},
        )
        case_id = case["id"]
        team_id = _register_login(team, "doc-team")
        _run_as(
            settings.database_url,
            lead_id,
            "INSERT INTO public.organization_members (organization_id, user_id, org_role) "
            "VALUES (:org, :user, 'lawyer')",
            {"org": UUID(case["organization_id"]), "user": team_id},
        )
        _post(lead, f"/api/v1/cases/{case_id}/members", {"user_id": str(team_id), "role": "team_lawyer"})
        _register_login(other, "doc-other")
        _invite(lead, client, case_id)

        assert _calls(lead, case_id) == {"list": 200, "upload": 200, "read": 200, "write": 200}
        assert _calls(team, case_id) == {"list": 200, "upload": 403, "read": 200, "write": 403}
        assert _calls(other, case_id) == {"list": 404, "upload": 404, "read": 404, "write": 404}
        assert set(_calls(client, case_id).values()) == {403}

        unknown = lead.get("/api/v1/_probe/documents/missing")
        foreign = other.get(f"/api/v1/_probe/documents/{case_id}")
        assert unknown.status_code == foreign.status_code == 404
        assert unknown.json()["detail"] == foreign.json()["detail"]
        assert lead.post(f"/api/v1/_probe/cases/{case_id}/documents").status_code == 403  # no Origin

        _post(lead, f"/api/v1/cases/{case_id}/members", {
            "user_id": str(team_id), "role": "team_lawyer", "permissions": {"can_upload": True},
        })
        assert _calls(team, case_id)["upload"] == 200

        _post(lead, f"/api/v1/cases/{case_id}/close", {"reason": f"{SAMPLE} closed"})
        closed = _calls(lead, case_id)
        assert closed == {"list": 200, "upload": 409, "read": 200, "write": 409}


def test_document_delete_needs_reason_and_respects_retention() -> None:
    today = date(2026, 11, 19)
    with pytest.raises(HTTPException) as short:
        check_document_delete("  too short ", None, today)
    assert short.value.status_code == 422
    with pytest.raises(HTTPException) as held:
        check_document_delete(f"{SAMPLE} duplicate upload", today + timedelta(days=1), today)
    assert held.value.status_code == 409
    assert check_document_delete(f"  {SAMPLE} duplicate upload ", today, today) == f"{SAMPLE} duplicate upload"
    assert check_document_delete(f"{SAMPLE} duplicate upload", None, today)


def test_document_audit_action_names_are_canonical() -> None:
    assert DOCUMENT_AUDIT_ACTIONS == {
        "upload": "document.upload",
        "view": "document.view",
        "download": "document.download",
        "correct": "document.correct",
        "delete": "document.delete",
    }
