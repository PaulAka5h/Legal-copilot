"""Continuous Strategy Reassessment & Scenario Tree Diffing Engine (Phase 7).

Adheres strictly to Legal Product Rules:
- Rule 1: No invented law; citations strictly grounded in Bangladesh legal corpus.
- Rule 3: Separation of lawyer notes, AI inference, and confirmed court orders.
- Rule 4: Qualitative rubric ratings only (no win percentages).
- Rule 5: AI output is a draft. Next dates are tentative until an authorized lawyer confirms.
- Rule 6: Keep history; versions chained via supersedes_id (prior trees and analyses immutable).
- Rule 8: Client data is separate; draft client updates require lawyer approval before publishing.
"""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from backend.src.ai.gateway import LLMGateway
from backend.src.hearings.schemas import (
    BranchDiffItem,
    DraftClientUpdatePayload,
    HearingRecommendation,
    HearingReassessmentRecord,
    HearingReviewStatus,
    HearingUpdateRecord,
    RubricDiffItem,
)
from backend.src.strategy.evaluator import RATING_ORDER, RubricEvaluator
from backend.src.strategy.schemas import (
    Plausibility,
    ResidualRiskMetadata,
    RubricDimensionScore,
    RubricRating,
    ScenarioOpposingNode,
    ScenarioResponseNode,
    StrategyOrigin,
    StrategyRecord,
    StrategyRubricEvaluation,
    StrategyStatus,
)


class HearingReassessmentEngine:
    """Diffs hearing developments against active strategy and re-evaluates scenario trees."""

    def __init__(self, llm_gateway: Optional[LLMGateway] = None):
        self.gateway = llm_gateway or LLMGateway()
        self.evaluator = RubricEvaluator()

    def reassess_hearing(
        self,
        case_id: str,
        hearing_id: str,
        hearing_update: HearingUpdateRecord,
        active_strategy: StrategyRecord,
        alternative_strategies: Optional[List[StrategyRecord]] = None,
        case_title: str = "Commercial Proceeding",
        organization_id: str = "default_org",
    ) -> HearingReassessmentRecord:
        """Run targeted diffing of the 2-ply scenario tree and recalculate rubric dimensions."""

        tree_diffs: List[BranchDiffItem] = []
        rubric_diffs: List[RubricDiffItem] = []
        new_risks: List[str] = []
        new_evidence_needs: List[str] = []

        # 1. Diff 2-Ply Scenario Tree against Hearing Developments
        reassessed_strategy = self._diff_and_update_strategy_tree(
            active_strategy=active_strategy,
            hearing_update=hearing_update,
            tree_diffs=tree_diffs,
            new_risks=new_risks,
            new_evidence_needs=new_evidence_needs,
        )

        # 2. Re-evaluate 5-Dimension Qualitative Rubric
        updated_rubric = self._reevaluate_rubric(
            previous_rubric=active_strategy.rubric_evaluation,
            hearing_update=hearing_update,
            rubric_diffs=rubric_diffs,
        )
        reassessed_strategy.rubric_evaluation = updated_rubric

        # 3. Formulate Posture Recommendation ('maintain' | 'review' | 'change_suggested')
        recommendation, recommendation_reason = self._determine_posture_recommendation(
            reassessed_strategy=reassessed_strategy,
            tree_diffs=tree_diffs,
            rubric_diffs=rubric_diffs,
            hearing_update=hearing_update,
            alternative_strategies=alternative_strategies,
        )

        # 4. Draft Plain-Language Client Update (Draft only, Rule 8 & HEAR-8)
        draft_client_update = self._draft_client_update(
            case_title=case_title,
            hearing_id=hearing_id,
            hearing_update=hearing_update,
            recommendation=recommendation,
        )

        return HearingReassessmentRecord(
            case_id=case_id,
            hearing_id=hearing_id,
            hearing_update_id=str(hearing_update.id),
            organization_id=organization_id,
            previous_strategy_id=active_strategy.id,
            reassessed_strategy_id=reassessed_strategy.id,
            recommendation=recommendation,
            recommendation_reason=recommendation_reason,
            tree_diff=tree_diffs,
            rubric_diff=rubric_diffs,
            new_risks=new_risks,
            new_evidence_needs=new_evidence_needs,
            reassessed_strategy=reassessed_strategy,
            draft_client_update=draft_client_update,
            review_status=HearingReviewStatus.DRAFT,
        )

    def _diff_and_update_strategy_tree(
        self,
        active_strategy: StrategyRecord,
        hearing_update: HearingUpdateRecord,
        tree_diffs: List[BranchDiffItem],
        new_risks: List[str],
        new_evidence_needs: List[str],
    ) -> StrategyRecord:
        """Create new immutable strategy version (supersedes_id) and adjust 2-ply branch nodes."""

        new_strat = deepcopy(active_strategy)
        new_strat.id = uuid4()
        new_strat.version = active_strategy.version + 1
        new_strat.supersedes_id = active_strategy.id
        new_strat.status = StrategyStatus.PROPOSED
        new_strat.origin = StrategyOrigin.AI
        new_strat.is_current_strategy = False  # Requires lawyer selection to make current

        update_text = (
            f"{hearing_update.happened or ''} "
            f"{hearing_update.judge_remarks or ''} "
            f"{hearing_update.opposing_arguments or ''} "
            f"{hearing_update.orders_directions or ''} "
            f"{hearing_update.objections_procedural or ''}"
        ).lower()

        if new_strat.scenario_tree:
            for opp in new_strat.scenario_tree.opposing_arguments:
                opp_lower = opp.text.lower()
                prev_plausibility = opp.plausibility
                updated_plausibility = opp.plausibility
                is_pruned = opp.pruned
                diff_reason = "No material shift observed during hearing."

                # Opponent argument sustained / given credence by judge
                if any(k in update_text for k in ["sustain", "directed complainant to prove", "serious question", "adjourn to produce invoice", "consideration doubtful"]):
                    if "security" in opp_lower or "consideration" in opp_lower:
                        updated_plausibility = Plausibility.LIKELY
                        diff_reason = "Court expressed doubt regarding commercial consideration and directed evidentiary proof."
                        new_evidence_needs.append("Tender original delivery challans, sales VAT returns, and business correspondence.")

                # Opponent argument dismissed or rejected by court
                if any(k in update_text for k in ["reject", "overrule", "dismiss objection", "frivolous"]):
                    if "notice" in opp_lower or "postal" in opp_lower or "jurisdiction" in opp_lower:
                        updated_plausibility = Plausibility.UNLIKELY
                        is_pruned = True
                        diff_reason = "Court rejected adverse party's procedural objection regarding postal notice."

                # Update node state
                opp.plausibility = updated_plausibility
                opp.pruned = is_pruned

                # Update Depth 2 rebuttal residual risk
                for resp in opp.responses:
                    prev_risk = resp.residual_risk.risk_summary
                    if is_pruned:
                        resp.residual_risk.risk_summary = "Risk neutralized by favorable court ruling during hearing."
                        resp.residual_risk.risk_level = "low"
                        resp.residual_risk.unresolved_weaknesses = []
                        resp.residual_risk.practical_obstacles = []
                    elif updated_plausibility == Plausibility.LIKELY:
                        resp.residual_risk.risk_summary = "Elevated risk: Court active inquiry on consideration requires documentary corroboration."
                        new_risks.append("Evidentiary burden shifted to complainant on commercial supply contract.")

                    tree_diffs.append(
                        BranchDiffItem(
                            branch_id=str(opp.id),
                            opponent_argument=opp.text,
                            rebuttal_text=resp.text,
                            previous_plausibility=prev_plausibility,
                            updated_plausibility=updated_plausibility,
                            is_pruned=is_pruned,
                            diff_reason=diff_reason,
                            previous_residual_risk=prev_risk,
                            updated_residual_risk=resp.residual_risk.risk_summary,
                        )
                    )

        return new_strat

    def _reevaluate_rubric(
        self,
        previous_rubric: Optional[StrategyRubricEvaluation],
        hearing_update: HearingUpdateRecord,
        rubric_diffs: List[RubricDiffItem],
    ) -> StrategyRubricEvaluation:
        """Re-evaluate the 5-dimension qualitative rubric based on courtroom events."""

        update_text = (
            f"{hearing_update.happened or ''} "
            f"{hearing_update.judge_remarks or ''} "
            f"{hearing_update.orders_directions or ''}"
        ).lower()

        # Defaults from previous rubric or baseline
        stat_score = previous_rubric.statutory_strength.rating if previous_rubric else RubricRating.STRONG
        prec_score = previous_rubric.precedent_alignment.rating if previous_rubric else RubricRating.INSUFFICIENT_INFORMATION
        fact_score = previous_rubric.factual_support.rating if previous_rubric else RubricRating.MODERATE
        proc_score = previous_rubric.procedural_compliance.rating if previous_rubric else RubricRating.STRONG
        forum_score = previous_rubric.forum_risk.rating if previous_rubric else RubricRating.MODERATE

        # 1. Procedural Compliance adjustment
        if "procedural defect" in update_text or "show cause" in update_text:
            proc_score = RubricRating.MODERATE
            rubric_diffs.append(
                RubricDiffItem(
                    dimension="procedural_compliance",
                    previous_rating=RubricRating.STRONG,
                    updated_rating=RubricRating.MODERATE,
                    justification="Court identified procedural questions regarding service proof.",
                )
            )

        # 2. Forum Risk adjustment
        if "adjourn" in update_text and ("months" in update_text or "prolonged" in update_text or "heavy backlog" in update_text):
            forum_score = RubricRating.WEAK
            rubric_diffs.append(
                RubricDiffItem(
                    dimension="forum_risk",
                    previous_rating=RubricRating.MODERATE,
                    updated_rating=RubricRating.WEAK,
                    justification="Extended adjournment granted; trial delay risk increased.",
                )
            )
        elif "expedite" in update_text or "fixed for peremptory hearing" in update_text:
            forum_score = RubricRating.STRONG
            rubric_diffs.append(
                RubricDiffItem(
                    dimension="forum_risk",
                    previous_rating=RubricRating.MODERATE,
                    updated_rating=RubricRating.STRONG,
                    justification="Court set expedited schedule for disposal.",
                )
            )

        # 3. Factual Support adjustment
        if hearing_update.new_evidence and ("admitted" in hearing_update.new_evidence.lower() or "marked exhibit" in hearing_update.new_evidence.lower()):
            fact_score = RubricRating.STRONG
            rubric_diffs.append(
                RubricDiffItem(
                    dimension="factual_support",
                    previous_rating=RubricRating.MODERATE,
                    updated_rating=RubricRating.STRONG,
                    justification="New documentary evidence marked as formal trial exhibit.",
                )
            )

        # Construct dimension scores and apply deterministic weakest-critical-dimension ceiling rule
        stat_dim = RubricDimensionScore(
            dimension_name="statutory_strength",
            rating=stat_score,
            explanation="Statutory presumption verified under NI Act Sec 138/139.",
        )
        prec_dim = RubricDimensionScore(
            dimension_name="precedent_alignment",
            rating=prec_score,
            explanation="Binding High Court & Appellate Division citations.",
        )
        fact_dim = RubricDimensionScore(
            dimension_name="factual_support",
            rating=fact_score,
            explanation="Exhibits and documentary cheques in record.",
        )
        proc_dim = RubricDimensionScore(
            dimension_name="procedural_compliance",
            rating=proc_score,
            explanation="Compliance with limitation periods and notice requirements.",
        )
        forum_dim = RubricDimensionScore(
            dimension_name="forum_risk",
            rating=forum_score,
            explanation="Court workload, calendar delays, and bench disposition.",
        )

        return self.evaluator.evaluate_strategy(
            statutory_strength=stat_dim,
            precedent_alignment=prec_dim,
            factual_support=fact_dim,
            procedural_compliance=proc_dim,
            forum_risk=forum_dim,
        )

    def _determine_posture_recommendation(
        self,
        reassessed_strategy: StrategyRecord,
        tree_diffs: List[BranchDiffItem],
        rubric_diffs: List[RubricDiffItem],
        hearing_update: HearingUpdateRecord,
        alternative_strategies: Optional[List[StrategyRecord]] = None,
    ) -> tuple[HearingRecommendation, str]:
        """Determine whether lawyer should maintain, review, or change strategy."""

        update_text = (
            f"{hearing_update.happened or ''} "
            f"{hearing_update.judge_remarks or ''} "
            f"{hearing_update.orders_directions or ''}"
        ).lower()

        # Check for fatal legal blow (e.g. complaint barred by limitation, rejected under 203 CrPC)
        if any(term in update_text for term in ["dismissed under section 203", "barred by limitation", "quashed"]):
            return (
                HearingRecommendation.CHANGE_SUGGESTED,
                "Criminal complaint barred or dismissed by court. Recommend switching immediately to alternative civil summary recovery under Order XXXVII CPC.",
            )

        # Check for significant evidentiary requirements or procedural warnings
        has_elevated_branch = any(
            d.updated_plausibility == Plausibility.LIKELY and not d.is_pruned for d in tree_diffs
        )
        has_rubric_downgrade = any(
            RATING_ORDER[d.updated_rating] < RATING_ORDER[d.previous_rating] for d in rubric_diffs
        )

        if has_elevated_branch or has_rubric_downgrade or "show cause" in update_text:
            return (
                HearingRecommendation.REVIEW,
                "Active strategy viable but exposed to increased evidential demands. Review pending witness evidence and consideration proof before next date.",
            )

        return (
            HearingRecommendation.MAINTAIN,
            "Court proceedings aligned with strategy objectives. Presumptions and procedural posture remain intact. Maintain current trajectory.",
        )

    def _draft_client_update(
        self,
        case_title: str,
        hearing_id: str,
        hearing_update: HearingUpdateRecord,
        recommendation: HearingRecommendation,
    ) -> DraftClientUpdatePayload:
        """Draft a simple, non-confidential client summary for lawyer review before publishing."""

        summary_parts = []
        summary_parts.append(f"A hearing took place regarding {case_title}.")
        if hearing_update.orders_directions:
            summary_parts.append(f"The court directed: {hearing_update.orders_directions}.")
        else:
            summary_parts.append("The court heard the submissions of both parties and recorded the appearance.")

        next_info = None
        if hearing_update.next_hearing_date:
            date_str = hearing_update.next_hearing_date.strftime("%d %B %Y")
            confirmed_status = "confirmed" if hearing_update.next_hearing_confirmed else "tentative"
            next_info = f"Next scheduled hearing: {date_str} ({confirmed_status})."

        client_action = None
        if "bring witness" in (hearing_update.follow_ups or "").lower() or "original document" in (hearing_update.follow_ups or "").lower():
            client_action = "Please provide the original trade documents to your lawyer before the next date."

        return DraftClientUpdatePayload(
            hearing_id=hearing_id,
            title=f"Hearing Update: {case_title}",
            plain_language_summary=" ".join(summary_parts),
            next_hearing_info=next_info,
            client_action_required=client_action,
            is_approved_by_lawyer=False,
        )
