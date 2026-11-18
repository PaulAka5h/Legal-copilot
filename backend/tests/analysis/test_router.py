"""Integration tests for Phase 5 FastAPI Case Analysis endpoints."""

from fastapi.testclient import TestClient
from backend.src.main import app

client = TestClient(app)


def test_trigger_analysis_run_and_get():
    case_id = "test-case-uuid-999"

    # Trigger analysis
    res = client.post(
        f"/api/v1/cases/{case_id}/analysis-runs",
        json={
            "case_type": "Cheque Dishonour (NI Act Sec 138)",
            "document_chunks": [
                {
                    "id": "c1",
                    "filename": "cheque.pdf",
                    "page": 1,
                    "text": "Cheque no. 4928192 for BDT 1,500,000 issued by accused on 10 Jan 2023.",
                }
            ],
            "trigger": "initial",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["case_id"] == case_id
    assert data["version"] == 1
    assert len(data["claims"]) > 0
    assert len(data["timeline"]) > 0
    assert len(data["citations"]) > 0

    analysis_id = data["id"]

    # Get latest analysis
    get_res = client.get(f"/api/v1/cases/{case_id}/analysis")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == analysis_id

    # Get timeline
    timeline_res = client.get(f"/api/v1/cases/{case_id}/timeline")
    assert timeline_res.status_code == 200
    assert len(timeline_res.json()) > 0

    # Get contradictions & gaps
    contra_res = client.get(f"/api/v1/cases/{case_id}/contradictions")
    assert contra_res.status_code == 200
    assert "contradictions" in contra_res.json()
    assert "gaps" in contra_res.json()

    # Get evidence
    ev_res = client.get(f"/api/v1/cases/{case_id}/evidence")
    assert ev_res.status_code == 200
    assert len(ev_res.json()) > 0

    # Lawyer review
    rev_res = client.post(
        f"/api/v1/cases/{case_id}/analysis/{analysis_id}/review",
        json={
            "reviewer_id": "lawyer-123",
            "status": "lawyer_reviewed",
            "notes": "Verified facts against original bank memo.",
        },
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["review_status"] == "lawyer_reviewed"
