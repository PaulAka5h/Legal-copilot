"""Five-Dimension Legal Evaluation Rubric with Weakest-Dimension Ceiling.

Enforces:
- AGENTS.md Rule 4: "No win percentages. Use strong, moderate, weak, or insufficient information, with reasons."
- TRD Section 8.2: Weakest-dimension ceiling aggregation rule.
- Refinement Requirement 3: Precedent alignment must rely on verified judgments (HCD/AD),
  never inferred from statutory text alone; otherwise marked 'insufficient_information'.
- Forum risk evaluated separately as operational/delay impact.
"""

from typing import List, Optional
from backend.src.strategy.schemas import (
    PrecedentReference,
    RubricDimensionScore,
    RubricRating,
    StrategyRubricEvaluation,
)

# Ordinal ranking scale (0 = lowest, 3 = highest)
RATING_ORDER = {
    RubricRating.INSUFFICIENT_INFORMATION: 0,
    RubricRating.WEAK: 1,
    RubricRating.MODERATE: 2,
    RubricRating.STRONG: 3,
}

ORDER_TO_RATING = {
    0: RubricRating.INSUFFICIENT_INFORMATION,
    1: RubricRating.WEAK,
    2: RubricRating.MODERATE,
    3: RubricRating.STRONG,
}

# The four core legal validity dimensions that cap the substantive legal rating
CRITICAL_LEGAL_DIMENSIONS = [
    "statutory_strength",
    "precedent_alignment",
    "factual_support",
    "procedural_compliance",
]


class RubricEvaluator:
    """Evaluates candidate legal strategies across five rigorous dimensions."""

    @classmethod
    def evaluate_precedent_alignment(
        cls,
        precedents: List[PrecedentReference],
    ) -> RubricDimensionScore:
        """Evaluate precedent alignment strictly against verified judicial decisions.
        
        Rule: Never infer precedent alignment from statutory text alone.
        If verified precedent is unavailable, it MUST be marked 'insufficient_information'.
        """
        verified_precedents = [p for p in precedents if p.is_verified]

        if not verified_precedents:
            return RubricDimensionScore(
                dimension_name="precedent_alignment",
                rating=RubricRating.INSUFFICIENT_INFORMATION,
                explanation=(
                    "Insufficient information: No verified High Court Division or Appellate Division judgment was found or cited in the database. "
                    "Precedent alignment cannot be inferred from statutory provisions alone; requires advocate case-law verification."
                ),
                supporting_evidence=[],
                source_references=[],
                gaps_or_uncertainties=["Unverified judicial precedent; requires review against DLR/BLD law reports."],
            )

        # Check court hierarchy
        has_ad = any("Appellate Division" in p.court for p in verified_precedents)
        has_hcd = any("High Court" in p.court for p in verified_precedents)

        if has_ad:
            rating = RubricRating.STRONG
            expl = f"Directly anchored in binding Appellate Division authority: {verified_precedents[0].citation}."
        elif has_hcd:
            rating = RubricRating.MODERATE
            expl = f"Anchored in High Court Division ruling: {verified_precedents[0].citation}."
        else:
            rating = RubricRating.WEAK
            expl = "Precedent exists but from subordinate or non-binding forum."

        return RubricDimensionScore(
            dimension_name="precedent_alignment",
            rating=rating,
            explanation=expl,
            supporting_evidence=[p.legal_principle for p in verified_precedents],
            source_references=[f"{p.case_title} ({p.citation})" for p in verified_precedents],
            gaps_or_uncertainties=[],
        )

    @classmethod
    def evaluate_strategy(
        cls,
        statutory_strength: RubricDimensionScore,
        precedent_alignment: RubricDimensionScore,
        factual_support: RubricDimensionScore,
        procedural_compliance: RubricDimensionScore,
        forum_risk: RubricDimensionScore,
    ) -> StrategyRubricEvaluation:
        """Apply weakest-critical-dimension aggregation rule.
        
        Rules:
        1. If ANY critical dimension has 'insufficient_information', overall MUST be
           'insufficient_information' and requires lawyer review.
        2. Otherwise, overall rating is capped by the minimum of the critical dimensions.
        3. Forum risk is tracked separately and influences practical viability.
        """
        dimension_map = {
            "statutory_strength": statutory_strength,
            "precedent_alignment": precedent_alignment,
            "factual_support": factual_support,
            "procedural_compliance": procedural_compliance,
        }

        review_reasons: List[str] = []
        requires_review = False

        # Check for insufficient information first
        has_insufficient_info = False
        weakest_dim = "statutory_strength"
        lowest_score = 999

        for dim_name, score_obj in dimension_map.items():
            score_val = RATING_ORDER[score_obj.rating]
            if score_obj.rating == RubricRating.INSUFFICIENT_INFORMATION:
                has_insufficient_info = True
                review_reasons.append(
                    f"Dimension '{dim_name}' has insufficient information: {score_obj.explanation}"
                )
            if score_val < lowest_score:
                lowest_score = score_val
                weakest_dim = dim_name

        if has_insufficient_info:
            overall = RubricRating.INSUFFICIENT_INFORMATION
            requires_review = True
            review_reasons.append(
                "Critical legal information is missing or unverified. Strategy requires advocate review before action."
            )
        else:
            overall = ORDER_TO_RATING[lowest_score]
            if overall == RubricRating.WEAK:
                requires_review = True
                review_reasons.append(
                    f"Overall legal rating is capped at WEAK due to weakest critical dimension: '{weakest_dim}'."
                )

        # Operational impact of forum risk
        if forum_risk.rating in (RubricRating.WEAK, RubricRating.INSUFFICIENT_INFORMATION):
            review_reasons.append(
                f"High forum risk detected: {forum_risk.explanation}. Significant potential for trial delays or revision stays."
            )

        return StrategyRubricEvaluation(
            statutory_strength=statutory_strength,
            precedent_alignment=precedent_alignment,
            factual_support=factual_support,
            procedural_compliance=procedural_compliance,
            forum_risk=forum_risk,
            overall_rating=overall,
            weakest_critical_dimension=weakest_dim,
            requires_lawyer_review=requires_review,
            review_reasons=review_reasons,
        )
