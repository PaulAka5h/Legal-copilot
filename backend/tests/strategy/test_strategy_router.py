"""FastAPI Integration Tests for Strategy Engine Endpoints."""

from fastapi.testclient import TestClient
from backend.src.main import app

client = TestClient(app)


def test_strategy_api_e2e_flow():
    case_id = "test-case-strategy-api-101"

    # 1. Generate strategies
    gen_res = client.post(
        f"/api/v1/cases/{case_id}/strategies/generate",
        json={
            "case_facts": {
                "case_type": "Cheque Dishonour (NI Act Sec 138)",
                "title": "Dishonoured Cheque Dispute",
            },
            "available_documents": [
                {"filename": "cheque.pdf", "text": "Cheque #4928192"},
                {"filename": "memo.pdf", "text": "Bank return memo"},
                {"filename": "notice.pdf", "text": "Legal notice dispatched"},
            ],
            "organization_id": "test-org-1",
        },
    )
    assert gen_res.status_code == 201
    strategies = gen_res.json()
    assert len(strategies) >= 2
    strat_id = strategies[0]["id"]

    # 2. List strategies
    list_res = client.get(f"/api/v1/cases/{case_id}/strategies")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 2

    # 3. Get single strategy
    get_res = client.get(f"/api/v1/cases/{case_id}/strategies/{strat_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == strat_id

    # 4. Get 2-ply scenario tree
    tree_res = client.get(f"/api/v1/cases/{case_id}/strategies/{strat_id}/tree")
    assert tree_res.status_code == 200
    tree_data = tree_res.json()
    assert "opposing_arguments" in tree_data
    assert len(tree_data["opposing_arguments"]) <= 3
    for opp in tree_data["opposing_arguments"]:
        assert opp["depth"] == 1
        for resp in opp["responses"]:
            assert resp["depth"] == 2
            assert "residual_risk" in resp

    # 5. Get comparison matrix
    comp_res = client.get(f"/api/v1/cases/{case_id}/strategies/comparison")
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert len(comp_data["strategies"]) >= 2
    assert comp_data["recommendation"] == "initial"

    # 6. Approve strategy
    appr_res = client.post(
        f"/api/v1/cases/{case_id}/strategies/{strat_id}/approve",
        json={"lawyer_id": "lawyer-123", "notes": "Approved for proceeding."},
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "approved"

    # 7. Select strategy as current
    sel_res = client.post(
        f"/api/v1/cases/{case_id}/strategies/{strat_id}/select",
        json={"lawyer_id": "lawyer-123"},
    )
    assert sel_res.status_code == 200
    assert sel_res.json()["status"] == "current"
    assert sel_res.json()["is_current_strategy"] is True

    # 8. Reject other strategy
    strat_b_id = strategies[1]["id"]
    rej_res = client.post(
        f"/api/v1/cases/{case_id}/strategies/{strat_b_id}/reject",
        json={"lawyer_id": "lawyer-123", "notes": "Not pursuing civil suit."},
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "rejected"

    # 9. Generate comprehensive strategy report
    rep_res = client.post(
        f"/api/v1/cases/{case_id}/strategies/report",
        json={
            "case_facts": {
                "case_type": "Cheque Dishonour",
                "summary": "Commercial debt dispute over supply invoice",
            },
            "available_documents": [
                {"filename": "cheque.pdf", "text": "Cheque #4928192"},
            ],
            "organization_id": "test-org-1",
        },
    )
    assert rep_res.status_code == 200
    report_data = rep_res.json()
    assert report_data["case_id"] == case_id
    assert len(report_data["disputed_facts"]) >= 1
    assert len(report_data["undisputed_facts"]) >= 1
    assert len(report_data["identified_issues"]) >= 1
    assert len(report_data["candidate_strategies"]) >= 1
    assert len(report_data["recommended_next_steps"]) >= 1
