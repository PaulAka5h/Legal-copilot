"""FastAPI tests for strategy endpoints. Strategies are lawyer-entered SAMPLE_DATA_NOT_REAL_LAW."""

from fastapi.testclient import TestClient
from backend.src.main import app
from backend.src.strategy.router import get_strategy_engine
from backend.src.strategy.schemas import NOT_CONFIGURED
from backend.tests.sample_strategies import seed_strategies

client = TestClient(app)


def test_generate_returns_no_strategies_and_not_configured_comparison():
    case_id = "test-case-strategy-api-empty"

    gen_res = client.post(f"/api/v1/cases/{case_id}/strategies/generate", json={})
    assert gen_res.status_code == 201
    assert gen_res.json() == []

    comp_res = client.get(f"/api/v1/cases/{case_id}/strategies/comparison")
    assert comp_res.status_code == 200
    assert comp_res.json()["strategies"] == []
    assert comp_res.json()["trade_offs_analysis"] == NOT_CONFIGURED


def test_strategy_lifecycle_endpoints_on_lawyer_strategies():
    case_id = "test-case-strategy-api-101"
    strat_a, strat_b = seed_strategies(get_strategy_engine(), case_id, count=2)

    list_res = client.get(f"/api/v1/cases/{case_id}/strategies")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 2

    get_res = client.get(f"/api/v1/cases/{case_id}/strategies/{strat_a.id}")
    assert get_res.status_code == 200

    appr_res = client.post(
        f"/api/v1/cases/{case_id}/strategies/{strat_a.id}/approve",
        json={"lawyer_id": "lawyer-123"},
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "approved"

    sel_res = client.post(
        f"/api/v1/cases/{case_id}/strategies/{strat_a.id}/select",
        json={"lawyer_id": "lawyer-123"},
    )
    assert sel_res.status_code == 200
    assert sel_res.json()["is_current_strategy"] is True

    rej_res = client.post(
        f"/api/v1/cases/{case_id}/strategies/{strat_b.id}/reject",
        json={"lawyer_id": "lawyer-123", "notes": "Not pursuing."},
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "rejected"


def test_report_endpoint_is_not_configured():
    case_id = "test-case-strategy-report"
    rep_res = client.post(f"/api/v1/cases/{case_id}/strategies/report", json={})
    assert rep_res.status_code == 200
    data = rep_res.json()
    assert data["metadata"]["status"] == NOT_CONFIGURED
    assert data["candidate_strategies"] == []
    assert data["relevant_precedents"] == []
