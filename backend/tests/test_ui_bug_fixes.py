"""UI bug fixes: case edit/archive, derived progress, summary versions, client share, lawyer profile.

All case content is SAMPLE_DATA_NOT_REAL_LAW.
"""

import asyncio
import secrets
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.cases.progress import case_progress
from app.cases.router import archive_case_endpoint
from app.cases.schemas import CaseAccess
from tests.step_c_helpers import ORIGIN, lawyer_with_case, new_client, sql_as
from tests.test_analysis import NEGLECT, add_fact
from tests.test_hearing_reassessment import make_hearing, update
from tests.test_phase2_exit import PASSWORD, create_case

CLAIM = {"id": "note-1", "type": "lawyer", "verification": "verified",
         "text": {"en": "SAMPLE_DATA_NOT_REAL_LAW edited note", "bn": ""},
         "source": {"en": "Hearing record (lawyer entered)", "bn": ""}}


def states(progress) -> dict[str, str]:
    return {stage["id"] if isinstance(stage, dict) else stage.id: (
        stage["state"] if isinstance(stage, dict) else stage.state) for stage in progress}


def audit_actions(database_url: str, user_id: UUID, case_id: str) -> list[str]:
    rows = sql_as(database_url, user_id, "SELECT action FROM public.audit_logs WHERE case_id = :c ORDER BY id",
                  c=case_id)
    return [row[0] for row in rows]


def test_case_progress_is_derived_from_hearings_and_status() -> None:
    assert states(case_progress(status="open", has_hearing=False, has_held_hearing=False)) == {
        "opened": "complete", "scheduled": "current", "held": "upcoming", "closed": "upcoming"}
    assert states(case_progress(status="open", has_hearing=True, has_held_hearing=False)) == {
        "opened": "complete", "scheduled": "complete", "held": "current", "closed": "upcoming"}
    assert states(case_progress(status="on_hold", has_hearing=True, has_held_hearing=True))["closed"] == "upcoming"
    for has_hearing in (False, True):  # "Case closed" is never current unless the case is closed
        for held in (False, True):
            assert states(case_progress(status="open", has_hearing=has_hearing, has_held_hearing=held))[
                "closed"] == "upcoming"
    assert set(states(case_progress(status="closed", has_hearing=False, has_held_hearing=False)).values()) == {
        "complete"}


def test_only_lead_lawyer_may_archive() -> None:
    access = CaseAccess(case_id=uuid4(), role="team_lawyer", permissions={"can_edit_case": True})
    with pytest.raises(HTTPException) as error:
        asyncio.run(archive_case_endpoint(request=None, case_id=access.case_id, user=None,
                                          case_access=access, session=None))
    assert error.value.status_code == 403


def test_edit_case_and_soft_archive_keep_history(api_client, local_app_user_database_url) -> None:
    user_id, case_id = lawyer_with_case(api_client, "edit-archive")
    edited = api_client.patch(f"/api/v1/cases/{case_id}", headers=ORIGIN, json={
        "title": "SAMPLE_DATA_NOT_REAL_LAW Renamed", "case_type": "civil", "court": "SAMPLE court",
        "status": "on_hold"})
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert (body["title"], body["case_type"], body["court"], body["status"]) == (
        "SAMPLE_DATA_NOT_REAL_LAW Renamed", "civil", "SAMPLE court", "on_hold")
    assert api_client.patch(f"/api/v1/cases/{case_id}", headers=ORIGIN, json={"status": "closed"}).status_code == 422
    assert api_client.post(f"/api/v1/cases/{case_id}/archive").status_code == 403  # CSRF origin check

    archived = api_client.post(f"/api/v1/cases/{case_id}/archive", headers=ORIGIN)
    assert archived.status_code == 200 and archived.json()["archived_at"]
    assert api_client.post(f"/api/v1/cases/{case_id}/archive", headers=ORIGIN).status_code == 409
    assert case_id not in [c["id"] for c in api_client.get("/api/v1/cases").json()]
    assert case_id in [c["id"] for c in api_client.get("/api/v1/cases?include_archived=true").json()]
    assert api_client.get(f"/api/v1/cases/{case_id}").json()["title"] == "SAMPLE_DATA_NOT_REAL_LAW Renamed"
    assert api_client.get("/api/v1/lawyer/dashboard/overview").json()["total_matters"] == 0
    assert api_client.patch(f"/api/v1/cases/{case_id}", headers=ORIGIN, json={"title": "x"}).status_code == 409

    other = new_client(api_client, 0)
    with other:
        lawyer_with_case(other, "edit-archive-other")
        assert other.post(f"/api/v1/cases/{case_id}/restore", headers=ORIGIN).status_code == 404

    restored = api_client.post(f"/api/v1/cases/{case_id}/restore", headers=ORIGIN)
    assert restored.status_code == 200 and restored.json()["archived_at"] is None
    assert case_id in [c["id"] for c in api_client.get("/api/v1/cases").json()]
    actions = audit_actions(local_app_user_database_url, user_id, case_id)
    assert actions[-3:] == ["case.updated", "case.archived", "case.restored"]
    details = sql_as(local_app_user_database_url, user_id,
                     "SELECT details::text FROM public.audit_logs WHERE case_id = :c AND action = 'case.updated'",
                     c=case_id)
    assert '"status_to": "on_hold"' in details[0][0]


def test_progress_moves_with_hearings_and_status(api_client) -> None:
    _, case_id = lawyer_with_case(api_client, "progress")
    progress = lambda: states(api_client.get(f"/api/v1/cases/{case_id}").json()["progress"])  # noqa: E731
    assert progress()["scheduled"] == "current"
    add_fact(api_client, case_id, NEGLECT)
    hearing = make_hearing(api_client, case_id)
    assert progress()["scheduled"] == "complete" and progress()["held"] == "current"
    update(api_client, case_id, hearing["id"])
    assert progress()["held"] == "complete" and progress()["closed"] == "upcoming"
    assert api_client.post(f"/api/v1/cases/{case_id}/close", headers=ORIGIN, json={}).status_code == 200
    assert set(progress().values()) == {"complete"}


def test_summary_versions_are_append_only(api_client, local_app_user_database_url) -> None:
    user_id, case_id = lawyer_with_case(api_client, "summary-versions")
    hearing = make_hearing(api_client, case_id)
    url = f"/api/v1/lawyer/cases/{case_id}/hearings/{hearing['id']}/summary-versions"
    sections = [{"id": "keyNotes", "claims": [CLAIM]}]
    assert api_client.get(url).json() == []

    first = api_client.post(url, headers=ORIGIN, json={"base_version": 1, "sections": sections})
    assert first.status_code == 201, first.text
    assert first.json()["version"] == 2 and first.json()["supersedes_id"] is None
    assert api_client.post(url, headers=ORIGIN, json={"base_version": 1, "sections": sections}).status_code == 409

    changed = [{"id": "keyNotes", "claims": [{**CLAIM, "text": {"en": "SAMPLE second edit", "bn": ""}}]}]
    second = api_client.post(url, headers=ORIGIN, json={"base_version": 2, "sections": changed})
    assert second.status_code == 201 and second.json()["supersedes_id"] == first.json()["id"]
    listed = api_client.get(url).json()
    assert [v["version"] for v in listed] == [2, 3]
    assert listed[0]["sections"][0]["claims"][0]["text"]["en"] == CLAIM["text"]["en"]  # not overwritten

    empty = [{"id": "keyNotes", "claims": [{**CLAIM, "text": {"en": " ", "bn": ""}}]}]
    assert api_client.post(url, headers=ORIGIN, json={"base_version": 3, "sections": empty}).status_code == 422
    dupes = [{"id": "keyNotes", "claims": [CLAIM, CLAIM]}]
    assert api_client.post(url, headers=ORIGIN, json={"base_version": 3, "sections": dupes}).status_code == 422
    assert audit_actions(local_app_user_database_url, user_id, case_id).count(
        "hearing_summary.version_saved") == 2

    other = new_client(api_client, 0)
    with other:
        lawyer_with_case(other, "summary-versions-other")
        assert other.get(url).status_code == 404
        assert other.post(url, headers=ORIGIN, json={"base_version": 3, "sections": sections}).status_code == 404

    api_client.post(f"/api/v1/cases/{case_id}/close", headers=ORIGIN, json={})
    assert api_client.post(url, headers=ORIGIN, json={"base_version": 3, "sections": sections}).status_code == 409


def _client_with_login(lawyer, client, case_id: str) -> str:
    """A client profile invited to case_id; returns the profile id."""
    profile = lawyer.post("/api/v1/clients", headers=ORIGIN, json={
        "display_name": "SAMPLE_DATA_NOT_REAL_LAW share client",
        "email": f"share-{secrets.token_hex(8)}@example.com"}).json()
    token = lawyer.post(f"/api/v1/cases/{case_id}/invitations", headers=ORIGIN,
                        json={"client_profile_id": profile["id"]}).json()["development_token"]
    accepted = client.post("/api/v1/auth/invitations/accept", headers=ORIGIN,
                           json={"token": token, "password": PASSWORD})
    assert accepted.status_code == 200, accepted.text
    return profile["id"]


def test_shared_summary_reaches_client_unshared_does_not(api_client, local_app_user_database_url) -> None:
    user_id, case_a = lawyer_with_case(api_client, "share")
    case_b = create_case(api_client, f"SAMPLE-share-b-{secrets.token_hex(3)}")
    add_fact(api_client, case_a, NEGLECT)
    shared = update(api_client, case_a, make_hearing(api_client, case_a)["id"])
    add_fact(api_client, case_b, NEGLECT)
    unshared = update(api_client, case_b, make_hearing(api_client, case_b)["id"])

    client = new_client(api_client, 0)
    with client:
        profile_id = _client_with_login(api_client, client, case_a)
        linked = api_client.post(f"/api/v1/clients/{profile_id}/cases", headers=ORIGIN, json={"case_id": case_b})
        assert linked.status_code == 201, linked.text

        def visible(case_id: str) -> list[str]:
            return [u["id"] for u in client.get(f"/api/v1/client/cases/{case_id}/updates").json()]

        assert visible(case_a) == [] and visible(case_b) == []  # drafts are never client-visible
        published = api_client.post(f"/api/v1/client-updates/{shared['client_update_id']}/publish", headers=ORIGIN)
        assert published.status_code == 200, published.text

        assert visible(case_a) == [shared["client_update_id"]]
        assert unshared["client_update_id"] not in visible(case_b)
        cases = client.get("/api/v1/client/cases").json()
        # Every linked case is listed; the one with the newest published update comes first.
        assert [c["id"] for c in cases][0] == case_a and {c["id"] for c in cases} == {case_a, case_b}
        assert states(cases[0]["progress"])["held"] == "complete"
        assert states(cases[1]["progress"])["held"] == "upcoming"  # nothing client-visible yet
        assert client.get(f"/api/v1/lawyer/cases/{case_a}/hearings/{shared['hearing_id']}/summary-versions"
                          ).status_code == 403  # lawyer-only summary drafts (Rule 8)
    assert "client_update.published" in audit_actions(local_app_user_database_url, user_id, case_a)


def test_lawyer_profile_edit_is_audited(api_client, local_app_user_database_url) -> None:
    user_id, _ = lawyer_with_case(api_client, "profile")
    before = api_client.get("/api/v1/lawyer/profile").json()
    assert before["can_edit_organization"] is True
    changed = api_client.patch("/api/v1/lawyer/profile", headers=ORIGIN, json={
        "full_name": "SAMPLE Lawyer Renamed", "phone": "+880 1700-000000", "preferred_language": "bn",
        "chamber_name": "SAMPLE Chamber", "organization_name": "SAMPLE Firm"})
    assert changed.status_code == 200, changed.text
    after = changed.json()
    assert (after["full_name"], after["phone"], after["preferred_language"], after["chamber_name"],
            after["organization_name"], after["email"]) == (
        "SAMPLE Lawyer Renamed", "+880 1700-000000", "bn", "SAMPLE Chamber", "SAMPLE Firm", before["email"])
    assert api_client.get("/api/v1/me").json()["full_name"] == "SAMPLE Lawyer Renamed"
    assert api_client.patch("/api/v1/lawyer/profile", headers=ORIGIN,
                            json={"email": "new@example.com"}).status_code == 422
    assert api_client.patch("/api/v1/lawyer/profile", headers=ORIGIN, json={"phone": "abc"}).status_code == 422
    assert api_client.patch("/api/v1/lawyer/profile", json={"full_name": "x"}).status_code == 403  # CSRF
    rows = sql_as(local_app_user_database_url, user_id,
                  "SELECT details::text FROM public.audit_logs WHERE actor_user_id = :u "
                  "AND action = 'lawyer.profile_updated'", u=user_id)
    assert len(rows) == 1 and "full_name" in rows[0][0] and "SAMPLE Lawyer Renamed" not in rows[0][0]
