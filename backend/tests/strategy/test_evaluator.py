"""Tests for Five-Dimension Evaluation Rubric and Weakest-Dimension Ceiling Rule."""

import pytest
from backend.src.strategy.evaluator import RubricEvaluator
from backend.src.strategy.schemas import (
    PrecedentReference,
    RubricDimensionScore,
    RubricRating,
)


def test_weakest_dimension_ceiling_rule():
    # If statutory strength is STRONG, factual support is STRONG, procedural is WEAK,
    # overall rating MUST be capped at WEAK.
    stat = RubricDimensionScore(dimension_name="statutory_strength", rating=RubricRating.STRONG, explanation="Strong law")
    prec = RubricDimensionScore(dimension_name="precedent_alignment", rating=RubricRating.STRONG, explanation="Strong precedents")
    fact = RubricDimensionScore(dimension_name="factual_support", rating=RubricRating.STRONG, explanation="Strong facts")
    proc = RubricDimensionScore(dimension_name="procedural_compliance", rating=RubricRating.WEAK, explanation="Time barred")
    forum = RubricDimensionScore(dimension_name="forum_risk", rating=RubricRating.STRONG, explanation="Fast court")

    rubric = RubricEvaluator.evaluate_strategy(stat, prec, fact, proc, forum)
    assert rubric.overall_rating == RubricRating.WEAK
    assert rubric.weakest_critical_dimension == "procedural_compliance"
    assert rubric.requires_lawyer_review is True


def test_insufficient_information_ceiling():
    # If ANY critical dimension has insufficient information, overall MUST be insufficient_information
    stat = RubricDimensionScore(dimension_name="statutory_strength", rating=RubricRating.STRONG, explanation="Strong law")
    prec = RubricDimensionScore(dimension_name="precedent_alignment", rating=RubricRating.INSUFFICIENT_INFORMATION, explanation="Missing precedent")
    fact = RubricDimensionScore(dimension_name="factual_support", rating=RubricRating.STRONG, explanation="Strong facts")
    proc = RubricDimensionScore(dimension_name="procedural_compliance", rating=RubricRating.MODERATE, explanation="Moderate procedure")
    forum = RubricDimensionScore(dimension_name="forum_risk", rating=RubricRating.MODERATE, explanation="Moderate court")

    rubric = RubricEvaluator.evaluate_strategy(stat, prec, fact, proc, forum)
    assert rubric.overall_rating == RubricRating.INSUFFICIENT_INFORMATION
    assert rubric.requires_lawyer_review is True
    assert any("insufficient information" in r for r in rubric.review_reasons)


def test_unverified_precedent_marked_insufficient_information():
    # Requirement: Precedent alignment must rely on verified relevant judgments (HCD/AD).
    # Never infer from statutory text alone; if unverified, mark insufficient_information.
    unverified_precedents = [
        PrecedentReference(
            case_title="Rahman vs State",
            citation="54 DLR 124",
            legal_principle="Presumption of consideration",
            is_verified=False,
        )
    ]
    prec_score = RubricEvaluator.evaluate_precedent_alignment(unverified_precedents)
    assert prec_score.rating == RubricRating.INSUFFICIENT_INFORMATION
    assert "insufficient information" in prec_score.explanation.lower()


def test_verified_appellate_division_precedent_strong():
    ad_precedent = [
        PrecedentReference(
            case_title="Shamsul Haque vs State",
            citation="62 DLR (AD) 250",
            court="Appellate Division",
            legal_principle="Notice receipt presumed under Section 27 General Clauses Act",
            is_verified=True,
        )
    ]
    prec_score = RubricEvaluator.evaluate_precedent_alignment(ad_precedent)
    assert prec_score.rating == RubricRating.STRONG
    assert "Appellate Division" in prec_score.explanation
