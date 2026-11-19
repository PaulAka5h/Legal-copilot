"""Strategy generation is NOT_CONFIGURED: no template strategies, no invented citations."""

import pytest
from backend.src.strategy.generator import (
    ProductionLLMConfigurationError,
    StrategyGenerator,
)


def test_generator_returns_no_template_strategies():
    strategies = StrategyGenerator().generate_candidate_strategies(
        case_id="case-101",
        case_facts={"title": "SAMPLE_DATA_NOT_REAL_LAW"},
        available_documents=[{"filename": "doc.pdf", "text": "SAMPLE_DATA_NOT_REAL_LAW"}],
    )
    assert strategies == []


def test_production_environment_fails_safely_without_real_llm(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    generator = StrategyGenerator()

    with pytest.raises(ProductionLLMConfigurationError) as exc_info:
        generator.generate_candidate_strategies(
            case_id="case-prod",
            case_facts={},
            available_documents=[],
        )
    assert "MockLLMProvider in production environment" in str(exc_info.value)
