"""Tests for hearing update versioning, immutability chains, and case isolation (Rules 6 & 7)."""

from datetime import datetime, timezone
import pytest
from backend.src.hearings.schemas import (
    HearingCreateRequest,
    HearingUpdateCreateRequest,
)
from backend.src.hearings.schemas import HearingRecommendation
from backend.src.hearings.service import HearingsService
from backend.src.strategy.schemas import StrategyStatus
from backend.tests.sample_strategies import seed_strategies


def test_hearing_update_version_history_supersedes_chain():
    service = HearingsService()
    now = datetime.now(timezone.utc)
    case_id = "case-version-chain-01"

    hearing = service.create_hearing(
        case_id=case_id,
        request=HearingCreateRequest(scheduled_at=now, purpose="Initial Examination"),
    )
    (current,) = seed_strategies(service.strategy_engine, case_id, count=1)
    current.status = StrategyStatus.CURRENT
    current.is_current_strategy = True

    # 1. First hearing update (version 1)
    reassess_v1 = service.submit_hearing_update_and_reassess(
        hearing_id=str(hearing.id),
        request=HearingUpdateCreateRequest(
            happened="Initial hearing held.",
            orders_directions="Adjourned to produce ledger.",
        ),
    )
    updates = service.list_hearing_updates(str(hearing.id))
    assert len(updates) == 1
    u1 = updates[0]
    assert u1.version == 1
    assert u1.supersedes_id is None

    # 2. Second hearing update (edit / supplement creates version 2)
    reassess_v2 = service.submit_hearing_update_and_reassess(
        hearing_id=str(hearing.id),
        request=HearingUpdateCreateRequest(
            happened="Initial hearing held; corrected time.",
            orders_directions="Adjourned to produce ledger with original vouchers.",
        ),
    )
    updates_v2 = service.list_hearing_updates(str(hearing.id))
    assert len(updates_v2) == 2
    u2 = updates_v2[1]
    assert u2.version == 2
    assert u2.supersedes_id == u1.id  # Rule 6: chained to predecessor

    # 3. Strategy version chaining
    prev_strat_id = reassess_v2.previous_strategy_id
    reassessed_strat = reassess_v2.reassessed_strategy
    assert reassessed_strat is not None
    assert reassessed_strat.version > 1
    assert reassessed_strat.supersedes_id == prev_strat_id
    assert prev_strat_id == current.id


def test_reassessment_without_lawyer_strategy_creates_none():
    service = HearingsService()
    hearing = service.create_hearing(
        case_id="case-no-strategy",
        request=HearingCreateRequest(scheduled_at=datetime.now(timezone.utc), purpose="Mention"),
    )
    reassessment = service.submit_hearing_update_and_reassess(
        hearing_id=str(hearing.id),
        request=HearingUpdateCreateRequest(happened="Hearing held."),
    )
    assert reassessment.reassessed_strategy is None
    assert reassessment.previous_strategy_id is None
    assert reassessment.recommendation == HearingRecommendation.REVIEW
    assert service.strategy_engine.get_strategies("case-no-strategy") == []


def test_hearings_case_isolation():
    service = HearingsService()
    now = datetime.now(timezone.utc)

    # Hearing for case A
    h_a = service.create_hearing("case-AAA", HearingCreateRequest(scheduled_at=now, purpose="Case A Trial"))
    # Hearing for case B
    h_b = service.create_hearing("case-BBB", HearingCreateRequest(scheduled_at=now, purpose="Case B Bail"))

    list_a = service.list_hearings_for_case("case-AAA")
    list_b = service.list_hearings_for_case("case-BBB")

    assert len(list_a) == 1
    assert list_a[0].id == h_a.id

    assert len(list_b) == 1
    assert list_b[0].id == h_b.id

    # Verify no cross-case leakage
    assert all(h.case_id == "case-AAA" for h in list_a)
    assert all(h.case_id == "case-BBB" for h in list_b)
