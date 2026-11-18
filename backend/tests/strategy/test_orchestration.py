"""Unit and integration tests for RAG + LLM Strategy Orchestrator (Stages A through J)."""

import pytest
from backend.src.strategy.orchestrator import StrategyOrchestrator
from backend.src.strategy.schemas import (
    LegalCitationReference,
    LegalStrategyReportRecord,
    PrecedentReference,
    QueryExpansionResult,
)


def test_stage_a_fact_categorization():
    """Stage A: Test fact understanding, disputed vs undisputed separation with IDs."""
    orchestrator = StrategyOrchestrator()
    case_facts = {
        "title": "Cheque Dishonour Case",
        "cheque_amount": 1500000,
        "dishonour_date": "2023-01-25",
    }
    docs = [{"filename": "cheque.pdf", "text": "Cheque 4928192"}]

    disputed, undisputed, issues = orchestrator.understand_case_facts(case_facts, docs)

    assert len(undisputed) >= 2
    assert all(not f.is_disputed for f in undisputed)
    assert any(f.id == "fact-1" for f in undisputed)

    assert len(disputed) >= 1
    assert all(f.is_disputed for f in disputed)
    assert disputed[0].dispute_reason is not None

    assert len(issues) >= 2
    assert any("138" in issue for issue in issues)


def test_stage_b_query_expansion_and_numeral_normalization():
    """Stage B: Test bilingual query expansion and Bengali numeral normalization."""
    orchestrator = StrategyOrchestrator()

    # Numeral normalization
    assert orchestrator.normalize_numerals("ধারা ১৩৮ এবং ১৩৯") == "ধারা 138 এবং 139"
    assert orchestrator.normalize_numerals("২০০৮ সালের আইন") == "2008 সালের আইন"

    # Query expansion
    issue = "তামাদি সংক্রান্ত নোটিশ ধারা ১৩৮ NI Act"
    result: QueryExpansionResult = orchestrator.expand_queries(issue)

    assert result.original_issue == issue
    assert len(result.search_queries_en) >= 2
    assert len(result.search_queries_bn) >= 1
    assert "138" in result.extracted_section_numbers


def test_stage_c_legal_issue_analysis_grounding():
    """Stage C: Test legal issue analysis grounded in statutes and precedents."""
    orchestrator = StrategyOrchestrator()
    issues = [
        "Whether statutory notice under NI Act Sec 138(b) was valid?",
        "Whether presumption under Section 139 applies?",
    ]
    citations = [
        LegalCitationReference(
            act_name="The Negotiable Instruments Act, 1881",
            section="138",
            source_url="https://bdlaws.minlaw.gov.bd/act-25/section-138.html",
            is_verified=True,
        )
    ]

    analysis = orchestrator.analyze_legal_issues(issues, citations)

    assert len(analysis) == 2
    assert analysis[0].issue_id == "issue-1"
    assert len(analysis[0].applicable_statutes) >= 1
    assert analysis[0].applicable_statutes[0].section == "138"
    assert len(analysis[0].supporting_fact_ids) >= 1
    assert len(analysis[0].uncertainties) >= 1

    # Precedent check on issue 1
    assert len(analysis[0].relevant_precedents) >= 1
    assert analysis[0].relevant_precedents[0].is_verified is True


def test_stage_h_final_report_generation():
    """Stage H: Test generation of comprehensive LegalStrategyReportRecord."""
    orchestrator = StrategyOrchestrator()
    case_id = "test-case-orchestration-001"
    case_facts = {
        "title": "Supply Invoice Debt Dishonour",
        "case_type": "Cheque Dishonour",
        "summary": "Commercial debt dispute over supply of construction materials.",
    }
    docs = [{"filename": "cheque.pdf", "text": "Cheque 4928192 for BDT 1,500,000"}]

    report = orchestrator.generate_final_report(
        case_id=case_id,
        case_facts=case_facts,
        available_documents=docs,
        organization_id="org-law-chambers",
    )

    assert isinstance(report, LegalStrategyReportRecord)
    assert report.case_id == case_id
    assert report.organization_id == "org-law-chambers"
    assert len(report.disputed_facts) >= 1
    assert len(report.undisputed_facts) >= 1
    assert len(report.identified_issues) >= 1
    assert len(report.candidate_strategies) >= 1
    assert report.comparison_matrix is not None
    assert len(report.evidence_gaps) >= 1
    assert len(report.unresolved_risks) >= 1
    assert len(report.recommended_next_steps) >= 1
    assert "orchestration_version" in report.metadata


def test_stage_j_citation_and_provenance_validation():
    """Stage J: Test evidence and citation validation pass."""
    orchestrator = StrategyOrchestrator()
    valid_citations = [
        LegalCitationReference(
            act_name="The Negotiable Instruments Act, 1881",
            section="138",
            is_verified=True,
        )
    ]

    # Generate strategies
    strategies = orchestrator.generate_evidence_grounded_strategies(
        case_id="case-val",
        case_facts={"case_type": "Cheque Dishonour"},
        documents=[{"filename": "doc.pdf", "text": "sample"}],
        retrieved_citations=valid_citations,
    )

    # Invalidate one citation artificially to verify validation
    if strategies and strategies[0].source_references:
        strategies[0].source_references.append(
            LegalCitationReference(
                act_name="Non-Existent Made Up Act, 2099",
                section="999",
                is_verified=True,
            )
        )

    orchestrator.validate_citations_and_provenance(strategies, valid_citations)

    # The invented act reference must now be marked False
    invented_ref = [
        r for r in strategies[0].source_references if r.act_name == "Non-Existent Made Up Act, 2099"
    ]
    assert len(invented_ref) == 1
    assert invented_ref[0].is_verified is False
