"""Tests for Strategy Engine Lifecycle, Immutability, Single Current Strategy, and Comparison Matrix."""

import pytest
from backend.src.strategy.engine import (
    MockStrategyApprovalError,
    StrategyEngine,
)
from backend.src.strategy.schemas import (
    StrategyStatus,
)


def test_strategy_lifecycle_and_single_current_rule():
    engine = StrategyEngine()
    case_id = "case-lifecycle-1"

    strategies = engine.generate_strategies_for_case(
        case_id=case_id,
        case_facts={"case_type": "Cheque Dishonour"},
        available_documents=[
            {"filename": "cheque.pdf", "text": "Cheque"},
            {"filename": "memo.pdf", "text": "Memo"},
        ],
    )
    assert len(strategies) >= 2
    strat_a = strategies[0]
    strat_b = strategies[1]

    assert strat_a.status == StrategyStatus.DRAFT

    # 1. Propose strategy A
    proposed_a = engine.propose_strategy(case_id, strat_a.id, user_id="lawyer-1")
    assert proposed_a.status == StrategyStatus.PROPOSED

    # 2. Approve strategy A
    approved_a = engine.approve_strategy(case_id, strat_a.id, lawyer_id="lawyer-1")
    assert approved_a.status == StrategyStatus.APPROVED
    assert approved_a.approved_by == "lawyer-1"

    # 3. Select strategy A as CURRENT
    curr_a = engine.select_current_strategy(case_id, strat_a.id, lawyer_id="lawyer-1")
    assert curr_a.status == StrategyStatus.CURRENT
    assert curr_a.is_current_strategy is True

    # 4. Now select strategy B as CURRENT
    # Must enforce single-current rule: Strat A is demoted to SUPERSEDED!
    curr_b = engine.select_current_strategy(case_id, strat_b.id, lawyer_id="lawyer-1")
    assert curr_b.status == StrategyStatus.CURRENT
    assert curr_b.is_current_strategy is True

    updated_a = engine.get_strategy(case_id, strat_a.id)
    assert updated_a.status == StrategyStatus.SUPERSEDED
    assert updated_a.is_current_strategy is False

    # Check get_current_strategy returns strategy B only
    active_strat = engine.get_current_strategy(case_id)
    assert active_strat.id == strat_b.id


def test_strategy_version_immutability():
    engine = StrategyEngine()
    case_id = "case-immutability"

    strategies = engine.generate_strategies_for_case(
        case_id=case_id,
        case_facts={"case_type": "Cheque Dishonour"},
        available_documents=[{"filename": "cheque.pdf", "text": "Cheque"}],
    )
    strat_a = strategies[0]
    engine.approve_strategy(case_id, strat_a.id, lawyer_id="lawyer-1")

    # Updating approved strategy must spawn version 2 linked by supersedes_id
    new_v2 = engine.update_strategy_with_new_version(
        case_id=case_id,
        strategy_id=strat_a.id,
        updates={"name": "Amended Section 138 Strategy with Added Witness"},
        author_id="lawyer-2",
    )
    assert new_v2.version == 2
    assert new_v2.supersedes_id == strat_a.id
    assert new_v2.lineage_id == strat_a.lineage_id
    assert new_v2.status == StrategyStatus.DRAFT
    assert new_v2.name == "Amended Section 138 Strategy with Added Witness"

    # Original version 1 remains intact
    orig_v1 = engine.get_strategy(case_id, strat_a.id)
    assert orig_v1.version == 1
    assert orig_v1.status == StrategyStatus.APPROVED


def test_mock_strategy_cannot_be_approved_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    engine = StrategyEngine()
    case_id = "case-prod-mock"

    # Manually create mock strategy in store
    from uuid import uuid4
    from backend.src.strategy.schemas import StrategyOrigin, StrategyRecord

    mock_strat = StrategyRecord(
        id=uuid4(),
        case_id=case_id,
        name="Mock Strategy",
        legal_basis="Mock Basis",
        origin=StrategyOrigin.AI_MOCK,
        is_mock=True,
    )
    engine._strategy_store[case_id] = [mock_strat]

    with pytest.raises(MockStrategyApprovalError) as exc_info:
        engine.approve_strategy(case_id, mock_strat.id, lawyer_id="lawyer-1")
    assert "Mock-generated legal strategies cannot be approved" in str(exc_info.value)


def test_comparison_matrix_generation_and_no_win_percentages():
    engine = StrategyEngine()
    case_id = "case-comparison-test"

    engine.generate_strategies_for_case(
        case_id=case_id,
        case_facts={"case_type": "Cheque Dishonour"},
        available_documents=[
            {"filename": "cheque.pdf", "text": "Cheque"},
            {"filename": "memo.pdf", "text": "Dishonoured memo"},
        ],
    )
    comp = engine.get_latest_comparison(case_id)
    assert comp is not None
    assert len(comp.strategies) >= 2
    assert comp.best_supported_strategy_id is not None
    assert len(comp.trade_offs_analysis) > 0

    # Ensure no win percentages or statistical numbers are present
    comp_json = comp.model_dump_json()
    assert "win_probability" not in comp_json
    assert "win_percentage" not in comp_json
