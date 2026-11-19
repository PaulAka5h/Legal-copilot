"""Orchestrator tests: no canned facts, no invented precedents, citations never auto-verified.

Act names below are SAMPLE_DATA_NOT_REAL_LAW.
"""

from backend.src.strategy.orchestrator import StrategyOrchestrator
from backend.src.strategy.schemas import (
    NO_PRECEDENT_NOTE,
    NOT_CONFIGURED,
    LegalCitationReference,
    LegalStrategyReportRecord,
    QueryExpansionResult,
)
from backend.tests.sample_strategies import make_sample_strategy

SAMPLE_ACT = "SAMPLE_DATA_NOT_REAL_LAW Act"


def test_stage_a_returns_no_canned_facts():
    orchestrator = StrategyOrchestrator()
    disputed, undisputed, issues = orchestrator.understand_case_facts(
        {"title": "SAMPLE_DATA_NOT_REAL_LAW"}, [{"filename": "doc.pdf", "text": "x"}]
    )
    assert (disputed, undisputed, issues) == ([], [], [])


def test_stage_b_query_expansion_and_numeral_normalization():
    orchestrator = StrategyOrchestrator()

    assert orchestrator.normalize_numerals("ধারা ১৩৮ এবং ১৩৯") == "ধারা 138 এবং 139"
    assert orchestrator.normalize_numerals("২০০৮ সালের আইন") == "2008 সালের আইন"

    issue = "তামাদি সংক্রান্ত নোটিশ ধারা ১৩৮"
    result: QueryExpansionResult = orchestrator.expand_queries(issue)

    assert result.original_issue == issue
    assert result.search_queries_en == [orchestrator.normalize_numerals(issue)]
    assert result.search_queries_bn == []
    assert "138" in result.extracted_section_numbers


def test_stage_c_cites_no_precedents_and_keeps_citations_unverified():
    orchestrator = StrategyOrchestrator()
    citations = [LegalCitationReference(act_name=SAMPLE_ACT, section="1")]

    analysis = orchestrator.analyze_legal_issues(["SAMPLE issue"], citations)

    assert len(analysis) == 1
    assert analysis[0].relevant_precedents == []
    assert NO_PRECEDENT_NOTE in analysis[0].uncertainties
    assert analysis[0].applicable_statutes[0].is_verified is False


def test_stage_h_report_is_not_configured_and_has_no_template_content():
    orchestrator = StrategyOrchestrator()
    report = orchestrator.generate_final_report(
        case_id="test-case-orchestration-001",
        case_facts={"summary": "SAMPLE_DATA_NOT_REAL_LAW summary"},
        available_documents=[{"filename": "doc.pdf", "text": "x"}],
        organization_id="org-law-chambers",
    )

    assert isinstance(report, LegalStrategyReportRecord)
    assert report.case_summary == "SAMPLE_DATA_NOT_REAL_LAW summary"
    assert report.metadata["status"] == NOT_CONFIGURED
    assert report.candidate_strategies == []
    assert report.relevant_precedents == []
    assert report.applicable_statutes == []
    assert report.recommended_next_steps == []
    assert report.unresolved_risks == [NO_PRECEDENT_NOTE]


def test_stage_j_validation_downgrades_unknown_and_never_upgrades():
    orchestrator = StrategyOrchestrator()
    strategy = make_sample_strategy("case-val")
    strategy.source_references = [
        LegalCitationReference(act_name=SAMPLE_ACT, section="1", is_verified=False),
        LegalCitationReference(act_name="Unretrieved Act", section="9", is_verified=True),
    ]

    orchestrator.validate_citations_and_provenance(
        [strategy], [LegalCitationReference(act_name=SAMPLE_ACT, section="1")]
    )

    retrieved, unknown = strategy.source_references
    assert retrieved.is_verified is False
    assert unknown.is_verified is False
