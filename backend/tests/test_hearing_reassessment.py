"""Step F: hearing update -> reassessment. All case content is SAMPLE_DATA_NOT_REAL_LAW."""

from datetime import date
from uuid import UUID

from app.hearing_updates.service import suggest_date
from tests.step_c_helpers import ORIGIN, lawyer_with_case, new_client, sql_as
from tests.test_analysis import NEGLECT, add_fact
from tests.test_phase2_exit import create_invite_and_accept

ORDER = ("SAMPLE_DATA_NOT_REAL_LAW order: the court directed the officer to file a written reply "
         "and fixed the next hearing on 15 March 2025.")


def make_hearing(client, case_id, confirmed=True):
    response = client.post(f"/api/v1/lawyer/cases/{case_id}/hearings", headers=ORIGIN,
                           json={"scheduled_at": "2025-01-10T10:00:00Z", "purpose": "SAMPLE first hearing",
                                 "date_confirmed": confirmed})
    assert response.status_code == 201, response.text
    return response.json()


def update(client, case_id, hearing_id, **body):
    response = client.post(f"/api/v1/lawyer/cases/{case_id}/hearings/{hearing_id}/updates", headers=ORIGIN,
                           json={"order_text": ORDER, **body})
    assert response.status_code == 201, response.text
    return response.json()


def test_suggest_date_is_deterministic_and_bilingual():
    assert suggest_date(ORDER, date(2025, 1, 10)) == date(2025, 3, 15)
    assert suggest_date("পরবর্তী শুনানি ১৫ মার্চ ২০২৫ তারিখে", date(2025, 1, 10)) == date(2025, 3, 15)
    assert suggest_date("next date 2025-04-02 and 01.02.2025", None) == date(2025, 4, 2)
    assert suggest_date("no date here", None) is None
    assert suggest_date("held on 5 January 2025", date(2025, 1, 10)) is None  # only dates after the hearing


def test_hearing_update_reruns_analysis_and_strategy_and_drafts_client_summary(api_client):
    _, case_id = lawyer_with_case(api_client, "reassess")
    add_fact(api_client, case_id, NEGLECT)
    first_analysis = api_client.post(f"/api/v1/lawyer/cases/{case_id}/analysis", headers=ORIGIN, json={}).json()
    api_client.post(f"/api/v1/lawyer/cases/{case_id}/strategy", headers=ORIGIN, json={})
    hearing = make_hearing(api_client, case_id)
    assert hearing["date_status"] == "confirmed" and hearing["date_confirmed_by"]

    result = update(api_client, case_id, hearing["id"], notes="SAMPLE notes")
    assert result["analysis_version"] == first_analysis["version"] + 1
    assert result["tree_version"] == 2
    assert result["suggested_next_date"] == "2025-03-15" and result["suggested_next_date_status"] == "draft"
    assert result["next_hearing_id"] is None  # AI-suggested dates never create hearings
    assert any("Confirm the next hearing date" in t for t in result["tasks"])
    assert isinstance(result["closed_options"], list) and isinstance(result["new_options"], list)
    assert result["client_update_status"] == "draft"

    timeline = api_client.get(f"/api/v1/lawyer/cases/{case_id}/hearings/timeline").json()
    assert timeline[-1]["order_text"] == ORDER and timeline[-1]["source_label"] == "lawyer_entered"
    facts = api_client.get(f"/api/v1/lawyer/cases/{case_id}/facts/confirmed").json()["facts"]
    assert any(ORDER in f["statement"] and f["statement_type"] == "lawyer_entered" for f in facts)
    latest = api_client.get(f"/api/v1/lawyer/cases/{case_id}/analysis").json()
    assert latest["fact_set_hash"] != first_analysis["fact_set_hash"]  # re-run on the updated facts

    hearings = api_client.get(f"/api/v1/lawyer/cases/{case_id}/hearings").json()
    assert [h["date_status"] for h in hearings] == ["held"]

    client = new_client(api_client, 41)
    with client:
        create_invite_and_accept(api_client, client, case_id, "reassess-client")
        updates_url = f"/api/v1/client/cases/{case_id}/updates"
        assert client.get(updates_url).json() == [] or all(
            u["id"] != result["client_update_id"] for u in client.get(updates_url).json())
        published = api_client.post(f"/api/v1/client-updates/{result['client_update_id']}/publish", headers=ORIGIN)
        assert published.status_code == 200, published.text
        visible = client.get(updates_url).json()
        mine = [u for u in visible if u["id"] == result["client_update_id"]]
        assert mine and ORDER in mine[0]["body"]
        assert "finding" not in mine[0]["body"].lower() and "strength" not in mine[0]["body"].lower()
        assert client.get(f"/api/v1/lawyer/cases/{case_id}/reassessments").status_code == 403
    listed = api_client.get(f"/api/v1/lawyer/cases/{case_id}/reassessments").json()
    assert listed[0]["id"] == result["id"] and listed[0]["client_update_status"] == "published"


def test_lawyer_confirmed_next_date_creates_confirmed_hearing(api_client):
    _, case_id = lawyer_with_case(api_client, "reassess-confirmed")
    add_fact(api_client, case_id, NEGLECT)
    hearing = make_hearing(api_client, case_id, confirmed=False)
    assert hearing["date_status"] == "tentative" and hearing["date_confirmed_by"] is None
    result = update(api_client, case_id, hearing["id"], next_hearing_date="2025-03-15T10:00:00Z",
                    next_hearing_confirmed=True)
    assert result["next_hearing_id"] and result["suggested_next_date"] is None
    hearings = {h["id"]: h for h in api_client.get(f"/api/v1/lawyer/cases/{case_id}/hearings").json()}
    assert hearings[result["next_hearing_id"]]["date_status"] == "confirmed"
    bad = api_client.post(f"/api/v1/lawyer/cases/{case_id}/hearings/{hearing['id']}/updates", headers=ORIGIN,
                          json={"order_text": ORDER, "next_hearing_confirmed": True})
    assert bad.status_code == 422  # confirming needs a date


def test_reassessment_isolation(api_client):
    _, case_id = lawyer_with_case(api_client, "reassess-iso")
    add_fact(api_client, case_id, NEGLECT)
    hearing = make_hearing(api_client, case_id)
    result = update(api_client, case_id, hearing["id"])
    database_url = api_client.app.state.settings.database_url
    other = new_client(api_client, 42)
    with other:
        other_id, _ = lawyer_with_case(other, "reassess-other")
        for path in ("/hearings", "/hearings/timeline", "/reassessments"):
            assert other.get(f"/api/v1/lawyer/cases/{case_id}{path}").status_code == 404
        assert other.post(f"/api/v1/lawyer/cases/{case_id}/hearings/{hearing['id']}/updates", headers=ORIGIN,
                          json={"order_text": ORDER}).status_code == 404
    for table, column in (("case_reassessments", "case_id"), ("hearing_updates", "case_id")):
        assert sql_as(database_url, other_id, f"SELECT count(*) FROM public.{table} WHERE {column} = :c",
                      c=case_id)[0][0] == 0
    assert UUID(result["id"])
