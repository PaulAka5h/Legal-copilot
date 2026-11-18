"""Tests for Strategy Generator, Dynamic K, Traceability, and Mock Restrictions."""

import os
import pytest
from backend.src.ai.gateway import LLMGateway
from backend.src.strategy.generator import (
    ProductionLLMConfigurationError,
    StrategyGenerator,
)
from backend.src.strategy.schemas import StrategyOrigin


def test_generator_dynamic_k_and_plausibility():
    generator = StrategyGenerator()
    docs = [
        {"filename": "cheque.pdf", "text": "Cheque #4928192 for BDT 1,500,000"},
        {"filename": "memo.pdf", "text": "Dishonour memo insufficient funds"},
        {"filename": "notice.pdf", "text": "Demand notice"},
    ]
    strategies = generator.generate_candidate_strategies(
        case_id="case-101",
        case_facts={"case_type": "Cheque Dishonour", "title": "Agrani Bank Cheque"},
        available_documents=docs,
    )

    # Instruction 1: Does not force exactly 4; returns legally supportable paths (here 3)
    assert len(strategies) >= 2
    assert len(strategies) <= 4

    names = [s.name for s in strategies]
    assert any("138" in n for n in names)
    assert any("Summary Civil Suit" in n for n in names)

    # Instruction 4: Citations & source references are grounded
    for s in strategies:
        assert len(s.source_references) > 0
        assert s.source_references[0].act_name is not None
        assert s.origin == StrategyOrigin.AI_MOCK
        assert s.is_mock is True


def test_generator_avoids_unsupported_candidate_path():
    # If case facts involve active criminal fraud/forgery, ADR mediation path is not generated
    generator = StrategyGenerator()
    docs = [
        {"filename": "cheque.pdf", "text": "Cheque #4928192"},
        {"filename": "memo.pdf", "text": "Dishonoured"},
    ]
    strategies = generator.generate_candidate_strategies(
        case_id="case-fraud",
        case_facts={"case_type": "Cheque Fraud", "title": "Forged Cheque Fraud Case"},
        available_documents=docs,
    )

    names = [s.name for s in strategies]
    assert not any("Mediation" in n for n in names)


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
