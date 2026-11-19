"""Lawyer-entered sample strategies for lifecycle tests. SAMPLE_DATA_NOT_REAL_LAW."""

from backend.src.strategy.evaluator import RubricEvaluator
from backend.src.strategy.schemas import (
    RubricDimensionScore,
    RubricRating,
    StrategyOrigin,
    StrategyRecord,
    StrategyRubricEvaluation,
)

SAMPLE_LABEL = "SAMPLE_DATA_NOT_REAL_LAW"


def sample_rubric(rating: RubricRating = RubricRating.MODERATE) -> StrategyRubricEvaluation:
    def dim(name: str) -> RubricDimensionScore:
        return RubricDimensionScore(dimension_name=name, rating=rating, explanation=SAMPLE_LABEL)

    return RubricEvaluator.evaluate_strategy(
        statutory_strength=dim("statutory_strength"),
        precedent_alignment=dim("precedent_alignment"),
        factual_support=dim("factual_support"),
        procedural_compliance=dim("procedural_compliance"),
        forum_risk=dim("forum_risk"),
    )


def make_sample_strategy(case_id: str, n: int = 1, with_rubric: bool = False) -> StrategyRecord:
    return StrategyRecord(
        case_id=case_id,
        name=f"{SAMPLE_LABEL} strategy {n}",
        legal_basis=SAMPLE_LABEL,
        origin=StrategyOrigin.LAWYER,
        rubric_evaluation=sample_rubric() if with_rubric else None,
    )


def seed_strategies(engine, case_id: str, count: int = 2, with_rubric: bool = False) -> list[StrategyRecord]:
    """Insert sample strategies directly into the engine's in-memory store."""
    strategies = [make_sample_strategy(case_id, i + 1, with_rubric) for i in range(count)]
    engine._strategy_store.setdefault(case_id, []).extend(strategies)
    return strategies
