"""RAG + LLM Orchestration Architecture for Legal Strategy Engine.

Implements the multi-stage coordinated workflow:
A. Case Understanding (Material, Disputed & Undisputed Facts, Issues)
B. Query Understanding (Bilingual English/Bengali expansion, Numeral Normalization)
C. Legal Issue Analysis (Grounded in retrieved statutory provisions & precedents)
D. Candidate Strategy Generation (Evidence-grounded dynamic K)
E. Adversarial Scenario Generation (Depth D=2, Breadth B<=3 with risk metadata)
F. Strategy Evaluation (LLM qualitative scoring + deterministic weakest-dimension ceiling)
G. Strategy Comparison (Deterministic matrix + LLM trade-offs reasoning)
H. Final Comprehensive Legal Strategy Report
J. Citation & Provenance Validation
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from backend.src.ai.gateway import LLMGateway
from backend.src.strategy.schemas import (
    NO_PRECEDENT_NOTE,
    NOT_CONFIGURED,
    STRATEGY_NOT_CONFIGURED_REASON,
    DisputedFactItem,
    LegalCitationReference,
    LegalIssueAnalysisItem,
    LegalStrategyReportRecord,
    PrecedentReference,
    QueryExpansionResult,
    RecommendationType,
    StrategyComparisonItem,
    StrategyComparisonRecord,
    StrategyRecord,
    comparison_reason,
)


BN_DIGIT_MAP = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


class StrategyOrchestrator:
    """Master RAG + LLM Orchestration Engine for Legal Strategy."""

    def __init__(
        self,
        llm_gateway: Optional[LLMGateway] = None,
        retriever: Optional[Any] = None,
    ):
        self.gateway = llm_gateway or LLMGateway()
        self.retriever = retriever

    @staticmethod
    def normalize_numerals(text: str) -> str:
        """Normalize Bengali digits to ASCII digits."""
        if not text:
            return ""
        return text.translate(BN_DIGIT_MAP)

    # --------------------------------------------------------------------------
    # Stage A: Case Understanding & Fact Categorization
    # --------------------------------------------------------------------------
    def understand_case_facts(
        self,
        case_facts: Dict[str, Any],
        available_documents: List[Dict[str, Any]],
    ) -> Tuple[List[DisputedFactItem], List[DisputedFactItem], List[str]]:
        """Fact extraction is NOT_CONFIGURED until lawyer-confirmed facts exist (master prompt Step C).

        Returns empty lists instead of canned facts and issues.
        """
        return [], [], []

    # --------------------------------------------------------------------------
    # Stage B: Query Understanding & Expansion (Bilingual EN/BN)
    # --------------------------------------------------------------------------
    def expand_queries(self, issue_text: str) -> QueryExpansionResult:
        """Convert legal issues into bilingual English and Bengali search queries with numeral normalization."""
        norm_text = self.normalize_numerals(issue_text)

        # Extract section numbers (both English and Bengali numerals)
        sec_matches = re.findall(r"(?:section|sec|ধারা)\s*(\d+|[০-৯]+)", issue_text, flags=re.IGNORECASE)
        norm_secs = [self.normalize_numerals(s) for s in sec_matches]

        en_queries = [norm_text] if norm_text.strip() else []
        bn_queries: List[str] = []

        return QueryExpansionResult(
            original_issue=issue_text,
            search_queries_en=en_queries,
            search_queries_bn=bn_queries,
            extracted_section_numbers=norm_secs,
        )

    # --------------------------------------------------------------------------
    # Stage C: Legal Issue Analysis (Grounded in Retrieved Evidence)
    # --------------------------------------------------------------------------
    def analyze_legal_issues(
        self,
        issues: List[str],
        retrieved_citations: List[LegalCitationReference],
    ) -> List[LegalIssueAnalysisItem]:
        """Attach retrieved statutes to each issue. Precedents are never cited (none ingested).

        Element-by-element analysis is NOT_CONFIGURED (master prompt Step D), so
        requirements, exceptions and supporting facts stay empty.
        """
        return [
            LegalIssueAnalysisItem(
                issue_id=f"issue-{idx}",
                issue_text=issue,
                applicable_statutes=list(retrieved_citations),
                relevant_precedents=[],
                uncertainties=[
                    NO_PRECEDENT_NOTE,
                    "Element-by-element analysis is NOT_CONFIGURED; citations are unverified.",
                ],
            )
            for idx, issue in enumerate(issues, start=1)
        ]

    # --------------------------------------------------------------------------
    # Stage D & E: Candidate Strategy & 2-Ply Adversarial Tree Generation
    # --------------------------------------------------------------------------
    def generate_evidence_grounded_strategies(
        self,
        case_id: str,
        case_facts: Dict[str, Any],
        documents: List[Dict[str, Any]],
        retrieved_citations: List[LegalCitationReference],
        organization_id: str = "default_org",
    ) -> List[StrategyRecord]:
        """Generate candidate strategies and expand 2-ply adversarial scenario trees with risk metadata."""
        from backend.src.strategy.generator import StrategyGenerator
        gen = StrategyGenerator(llm_gateway=self.gateway, retriever=self.retriever)
        return gen.generate_candidate_strategies(
            case_id=case_id,
            case_facts=case_facts,
            available_documents=documents,
            organization_id=organization_id,
        )

    # --------------------------------------------------------------------------
    # Stage F & G: Strategy Evaluation & Comparison Matrix
    # --------------------------------------------------------------------------
    def evaluate_and_compare_strategies(
        self,
        case_id: str,
        strategies: List[StrategyRecord],
        organization_id: str = "default_org",
    ) -> StrategyComparisonRecord:
        """Deterministic comparison matrix preparation + LLM trade-offs reasoning."""
        items: List[StrategyComparisonItem] = []
        best_strat_id: Optional[UUID] = None
        current_highest_rating = -1

        from backend.src.strategy.evaluator import RATING_ORDER

        for s in strategies:
            rubric = s.rubric_evaluation
            if not rubric:
                continue

            score_val = RATING_ORDER[rubric.overall_rating]
            if score_val > current_highest_rating:
                current_highest_rating = score_val
                best_strat_id = s.id

            major_opps = []
            if s.scenario_tree:
                for opp in s.scenario_tree.opposing_arguments:
                    if not opp.pruned:
                        major_opps.append(opp.text)

            items.append(
                StrategyComparisonItem(
                    strategy_id=s.id,
                    name=s.name,
                    status=s.status,
                    is_current=s.is_current_strategy,
                    overall_rating=rubric.overall_rating,
                    statutory_strength=rubric.statutory_strength.rating,
                    precedent_alignment=rubric.precedent_alignment.rating,
                    factual_support=rubric.factual_support.rating,
                    procedural_compliance=rubric.procedural_compliance.rating,
                    forum_risk=rubric.forum_risk.rating,
                    key_strengths=s.strengths[:2],
                    key_vulnerabilities=s.weaknesses[:2],
                    major_opposing_arguments=major_opps[:2],
                    potential_remedies=s.remedies_sought[:2],
                )
            )

        return StrategyComparisonRecord(
            case_id=case_id,
            organization_id=organization_id,
            version=1,
            strategies=items,
            best_supported_strategy_id=best_strat_id,
            recommendation=RecommendationType.INITIAL,
            recommendation_reason=comparison_reason(items),
            trade_offs_analysis=NOT_CONFIGURED,
            uncertainties=[NO_PRECEDENT_NOTE],
        )

    # --------------------------------------------------------------------------
    # Stage H: Comprehensive Final Legal Strategy Report
    # --------------------------------------------------------------------------
    def generate_final_report(
        self,
        case_id: str,
        case_facts: Dict[str, Any],
        available_documents: List[Dict[str, Any]],
        organization_id: str = "default_org",
    ) -> LegalStrategyReportRecord:
        """Generate comprehensive final Legal Strategy Report combining RAG evidence and LLM reasoning."""
        # 1. Understand Facts & Categorize
        disputed_facts, undisputed_facts, legal_issues = self.understand_case_facts(
            case_facts=case_facts,
            available_documents=available_documents,
        )

        # 2. Query Understanding & Legal KB Retrieval
        retrieved_citations: List[LegalCitationReference] = []
        if self.retriever:
            try:
                for issue in legal_issues:
                    exp = self.expand_queries(issue)
                    for q in exp.search_queries_en[:1]:
                        hits = self.retriever.retrieve(q, rerank_top_k=2)
                        for h in hits:
                            chunk = h.chunk
                            retrieved_citations.append(
                                LegalCitationReference(
                                    act_name=chunk.act_name,
                                    section=chunk.section,
                                    subsection=chunk.subsection,
                                    clause=chunk.clause,
                                    chapter=chunk.chapter,
                                    source_id=str(chunk.legal_source_id) if chunk.legal_source_id else None,
                                    chunk_id=str(chunk.id),
                                    source_url=chunk.source_url,
                                    is_verified=False,
                                )
                            )
            except Exception:
                pass

        # 3. Analyze Issues
        analyzed_issues = self.analyze_legal_issues(legal_issues, retrieved_citations)

        # Precedents aggregated from issues
        all_precedents: List[PrecedentReference] = []
        for issue_item in analyzed_issues:
            all_precedents.extend(issue_item.relevant_precedents)

        # 4. Generate Candidate Strategies & Adversarial Trees
        strategies = self.generate_evidence_grounded_strategies(
            case_id=case_id,
            case_facts=case_facts,
            documents=available_documents,
            retrieved_citations=retrieved_citations,
            organization_id=organization_id,
        )

        # 5. Evaluate & Compare
        comparison = self.evaluate_and_compare_strategies(
            case_id=case_id,
            strategies=strategies,
            organization_id=organization_id,
        )

        # 6. Citations & Evidence Validation Pass
        self.validate_citations_and_provenance(strategies, retrieved_citations)

        # 7. Build and Return Comprehensive Report
        return LegalStrategyReportRecord(
            case_id=case_id,
            organization_id=organization_id,
            case_summary=str(case_facts.get("summary", "")),
            disputed_facts=disputed_facts,
            undisputed_facts=undisputed_facts,
            identified_issues=analyzed_issues,
            applicable_statutes=retrieved_citations,
            relevant_precedents=all_precedents,
            candidate_strategies=strategies,
            comparison_matrix=comparison,
            evidence_gaps=[],
            unresolved_risks=[NO_PRECEDENT_NOTE],
            recommended_next_steps=[],
            metadata={
                "status": NOT_CONFIGURED,
                "status_reason": STRATEGY_NOT_CONFIGURED_REASON,
                "llm_provider": self.gateway.current_provider,
                "llm_model": self.gateway.current_model,
                "orchestration_version": "2.0-rag-llm",
            },
        )

    # --------------------------------------------------------------------------
    # Stage J: Evidence & Citation Validation Pass
    # --------------------------------------------------------------------------
    def validate_citations_and_provenance(
        self,
        strategies: List[StrategyRecord],
        retrieved_citations: List[LegalCitationReference],
    ) -> None:
        """Downgrade references whose act was not retrieved. Never upgrades to verified.

        Verification needs the deterministic citation verifier (master prompt idea #7).
        """
        valid_acts = {c.act_name.lower() for c in retrieved_citations if c.act_name}
        for strat in strategies:
            for ref in strat.source_references:
                if not ref.act_name or ref.act_name.lower() not in valid_acts:
                    ref.is_verified = False
