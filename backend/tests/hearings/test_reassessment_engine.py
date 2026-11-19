"""Unit tests for HearingReassessmentEngine: tree diffing, rubric shifts, and posture recommendations."""

from datetime import datetime, timezone
from uuid import uuid4
import pytest
from backend.src.hearings.reassessment import HearingReassessmentEngine
from backend.src.hearings.schemas import (
    HearingRecommendation,
    HearingSourceLabel,
    HearingUpdateRecord,
)
from backend.src.strategy.evaluator import RubricEvaluator
from backend.src.strategy.schemas import (
    Plausibility,
    ResidualRiskMetadata,
    RubricDimensionScore,
    RubricRating,
    ScenarioOpposingNode,
    ScenarioResponseNode,
    ScenarioTree,
    StrategyOrigin,
    StrategyRecord,
    StrategyRubricEvaluation,
    StrategyStatus,
)


def _build_test_active_strategy() -> StrategyRecord:
    root_id = uuid4()
    opp1_id = uuid4()
    opp2_id = uuid4()
    tree = ScenarioTree(
        root_strategy_id=root_id,
        strategy_name="Criminal Complaint under Section 138 NI Act",
        opposing_arguments=[
            ScenarioOpposingNode(
                id=opp1_id,
                parent_id=root_id,
                legal_ground="Section 139 NI Act rebuttal",
                text="Drawer claims cheque was a blank security deposit leaf without commercial debt consideration.",
                plausibility=Plausibility.POSSIBLE,
                responses=[
                    ScenarioResponseNode(
                        id=uuid4(),
                        parent_id=opp1_id,
                        text="Invoke statutory presumption under Section 139 NI Act.",
                        residual_risk=ResidualRiskMetadata(
                            risk_summary="Court may requisition trade delivery challans.",
                            risk_level="medium",
                        ),
                    )
                ],
            ),
            ScenarioOpposingNode(
                id=opp2_id,
                parent_id=root_id,
                legal_ground="Section 138(b) statutory notice requirement",
                text="Drawer challenges delivery of statutory legal demand notice.",
                plausibility=Plausibility.POSSIBLE,
                responses=[
                    ScenarioResponseNode(
                        id=uuid4(),
                        parent_id=opp2_id,
                        text="Tender registered post dispatch slip and postal A.D. card.",
                        residual_risk=ResidualRiskMetadata(
                            risk_summary="Low risk if address matches registry.",
                            risk_level="low",
                        ),
                    )
                ],
            ),
        ],
    )
    rubric = StrategyRubricEvaluation(
        statutory_strength=RubricDimensionScore(
            dimension_name="statutory_strength",
            rating=RubricRating.STRONG,
            explanation="NI Act Section 138",
        ),
        precedent_alignment=RubricDimensionScore(
            dimension_name="precedent_alignment",
            rating=RubricRating.INSUFFICIENT_INFORMATION,
            explanation="Not verified",
        ),
        factual_support=RubricDimensionScore(
            dimension_name="factual_support",
            rating=RubricRating.MODERATE,
            explanation="Cheque copy",
        ),
        procedural_compliance=RubricDimensionScore(
            dimension_name="procedural_compliance",
            rating=RubricRating.STRONG,
            explanation="Within limitation",
        ),
        forum_risk=RubricDimensionScore(
            dimension_name="forum_risk",
            rating=RubricRating.MODERATE,
            explanation="Magistrate calendar",
        ),
        overall_rating=RubricRating.INSUFFICIENT_INFORMATION,
        weakest_critical_dimension="precedent_alignment",
    )
    return StrategyRecord(
        id=root_id,
        case_id="case-reassess-1",
        version=1,
        name="Criminal Complaint under Section 138 NI Act",
        legal_basis="Section 138 of Negotiable Instruments Act 1881",
        status=StrategyStatus.CURRENT,
        is_current_strategy=True,
        scenario_tree=tree,
        rubric_evaluation=rubric,
    )


def test_reassessment_tree_diff_objection_sustained():
    """Test tree diff when judge orders evidence on consideration defense (elevating branch)."""
    engine = HearingReassessmentEngine()
    active_strat = _build_test_active_strategy()
    update = HearingUpdateRecord(
        case_id="case-reassess-1",
        hearing_id="h-01",
        author_id="lawyer-1",
        happened="Court heard preliminary arguments.",
        judge_remarks="Judge expressed doubt regarding commercial consideration and directed complainant to prove delivery.",
        orders_directions="Complainant directed to produce trade delivery challan on next date.",
    )

    reassessment = engine.reassess_hearing(
        case_id="case-reassess-1",
        hearing_id="h-01",
        hearing_update=update,
        active_strategy=active_strat,
    )

    # 1. Recommendation should shift to 'review' due to elevated evidentiary burden
    assert reassessment.recommendation == HearingRecommendation.REVIEW
    assert len(reassessment.new_evidence_needs) >= 1
    assert any("challan" in item.lower() for item in reassessment.new_evidence_needs)

    # 2. Check branch diff on consideration branch
    tree_diffs = reassessment.tree_diff
    assert len(tree_diffs) == 2
    consideration_diff = [d for d in tree_diffs if "consideration" in d.opponent_argument.lower()][0]
    assert consideration_diff.updated_plausibility == Plausibility.LIKELY
    assert "consideration" in consideration_diff.diff_reason.lower()


def test_reassessment_tree_diff_objection_dismissed():
    """Test tree diff when judge rejects procedural notice objection (pruning branch)."""
    engine = HearingReassessmentEngine()
    active_strat = _build_test_active_strategy()
    update = HearingUpdateRecord(
        case_id="case-reassess-1",
        hearing_id="h-02",
        author_id="lawyer-1",
        happened="Adverse counsel raised objection on postal notice.",
        judge_remarks="Court overruled adverse party's frivolous notice objection.",
        orders_directions="Overruled and rejected defense plea.",
    )

    reassessment = engine.reassess_hearing(
        case_id="case-reassess-1",
        hearing_id="h-02",
        hearing_update=update,
        active_strategy=active_strat,
    )

    notice_diff = [d for d in reassessment.tree_diff if "notice" in d.opponent_argument.lower()][0]
    assert notice_diff.updated_plausibility == Plausibility.UNLIKELY
    assert notice_diff.is_pruned is True
    assert "neutralized" in notice_diff.updated_residual_risk.lower()


def test_reassessment_fatal_dismissal_recommends_change():
    """Test recommendation shifts to 'change_suggested' if criminal complaint is quashed/barred."""
    engine = HearingReassessmentEngine()
    active_strat = _build_test_active_strategy()
    update = HearingUpdateRecord(
        case_id="case-reassess-1",
        hearing_id="h-03",
        author_id="lawyer-1",
        happened="Magistrate passed final order.",
        orders_directions="Complaint dismissed under Section 203 CrPC as barred by limitation.",
    )

    reassessment = engine.reassess_hearing(
        case_id="case-reassess-1",
        hearing_id="h-03",
        hearing_update=update,
        active_strategy=active_strat,
    )

    assert reassessment.recommendation == HearingRecommendation.CHANGE_SUGGESTED
    assert "Order XXXVII" in reassessment.recommendation_reason or "alternative" in reassessment.recommendation_reason.lower()


def test_reassessment_rubric_admitted_evidence_upgrades_factual_support():
    """Test new exhibits admitted by court upgrades factual_support dimension."""
    engine = HearingReassessmentEngine()
    active_strat = _build_test_active_strategy()
    update = HearingUpdateRecord(
        case_id="case-reassess-1",
        hearing_id="h-04",
        author_id="lawyer-1",
        happened="Complainant examined and tendered documentary exhibits.",
        new_evidence="Original delivery challans and bank dishonour memo marked exhibit 1 and 2 admitted.",
        orders_directions="Exhibits admitted without objection. Fixed for cross.",
    )

    reassessment = engine.reassess_hearing(
        case_id="case-reassess-1",
        hearing_id="h-04",
        hearing_update=update,
        active_strategy=active_strat,
    )

    rubric_diffs = reassessment.rubric_diff
    fact_diff = [d for d in rubric_diffs if d.dimension == "factual_support"]
    assert len(fact_diff) == 1
    assert fact_diff[0].updated_rating == RubricRating.STRONG
