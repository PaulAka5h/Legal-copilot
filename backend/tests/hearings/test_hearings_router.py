"""FastAPI Integration Tests for Phase 7 Hearings, Reassessment, and Calendar Endpoints."""

from datetime import datetime, timezone
from fastapi.testclient import TestClient
from backend.src.main import app

client = TestClient(app)


def test_hearings_api_e2e_workflow():
    case_id = "test-case-hearings-api-101"
    now_str = datetime.now(timezone.utc).isoformat()

    # 1. Schedule hearing: POST /api/v1/cases/{case_id}/hearings
    create_res = client.post(
        f"/api/v1/cases/{case_id}/hearings?lawyer_id=lawyer-lead",
        json={
            "scheduled_at": now_str,
            "purpose": "Hearing on Preliminary Objections",
            "court_room": "Court 4, Dhaka Metropolitan Magistrate",
            "date_status": "tentative",
            "client_attendance_required": True,
            "organization_id": "test-org-1",
        },
    )
    assert create_res.status_code == 201
    hearing = create_res.json()
    assert hearing["case_id"] == case_id
    assert hearing["date_status"] == "tentative"
    hearing_id = hearing["id"]

    # 2. List case hearings: GET /api/v1/cases/{case_id}/hearings
    list_res = client.get(f"/api/v1/cases/{case_id}/hearings")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Get single hearing: GET /api/v1/hearings/{hearing_id}
    get_res = client.get(f"/api/v1/hearings/{hearing_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == hearing_id

    # 4. Patch hearing and confirm date: PATCH /api/v1/hearings/{hearing_id}
    patch_res = client.patch(
        f"/api/v1/hearings/{hearing_id}?lawyer_id=lawyer-lead",
        json={
            "purpose": "Updated Hearing Purpose",
            "confirm_date": True,
        },
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["date_status"] == "confirmed"
    assert patch_res.json()["date_confirmed_by"] == "lawyer-lead"

    # 5. Submit hearing update and trigger strategy reassessment: POST /api/v1/hearings/{hearing_id}/updates
    update_res = client.post(
        f"/api/v1/hearings/{hearing_id}/updates?case_title=Rahman+Cheque+Dishonour",
        json={
            "happened": "The court heard submissions on Section 138 notice validity.",
            "our_arguments": "Statutory notice sent by registered post with A.D. within 30 days.",
            "opposing_arguments": "Adverse counsel claimed consideration was not proven.",
            "judge_remarks": "Judge directed complainant to produce original delivery challan.",
            "orders_directions": "Complainant directed to produce trade documents on next date.",
            "next_hearing_date": "2025-05-20T10:00:00Z",
            "next_hearing_confirmed": False,
            "follow_ups": "Obtain signed challan from sales department.",
            "author_id": "lawyer-lead",
        },
    )
    assert update_res.status_code == 201
    reassessment = update_res.json()
    assert reassessment["recommendation"] in ["maintain", "review", "change_suggested"]
    assert "tree_diff" in reassessment
    assert "draft_client_update" in reassessment
    reassessment_id = reassessment["id"]

    # 6. List update history: GET /api/v1/hearings/{hearing_id}/updates
    hist_res = client.get(f"/api/v1/hearings/{hearing_id}/updates")
    assert hist_res.status_code == 200
    assert len(hist_res.json()) >= 1
    assert hist_res.json()[0]["version"] == 1

    # 7. Get latest reassessment: GET /api/v1/hearings/{hearing_id}/reassessment
    reassess_get = client.get(f"/api/v1/hearings/{hearing_id}/reassessment")
    assert reassess_get.status_code == 200
    assert reassess_get.json()["id"] == reassessment_id

    # 8. Approve client update: POST /api/v1/hearings/{hearing_id}/reassessment/approve-client-update
    appr_res = client.post(
        f"/api/v1/hearings/{hearing_id}/reassessment/approve-client-update?reassessment_id={reassessment_id}&lawyer_id=lawyer-lead"
    )
    assert appr_res.status_code == 200
    approved_draft = appr_res.json()
    assert approved_draft["is_approved_by_lawyer"] is True
    assert approved_draft["approved_by"] == "lawyer-lead"

    # 9. Lawyer Calendar: GET /api/v1/calendar
    cal_res = client.get("/api/v1/calendar")
    assert cal_res.status_code == 200
    cal_items = cal_res.json()
    assert len(cal_items) >= 1
    assert any(c["hearing_id"] == hearing_id for c in cal_items)
