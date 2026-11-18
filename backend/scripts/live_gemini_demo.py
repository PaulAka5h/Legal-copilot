"""Live End-to-End Demonstration: Google Gemini + Bangladesh Legal KB.

Executes:
1. Real statutory retrieval from PostgreSQL pgvector (62,491 Bangladesh law chunks).
2. Live structured fact extraction with Gemini (gemini-2.5-flash).
3. Live Chess Strategy generation with 2-ply adversarial tree and residual risk.
4. Comprehensive Legal Strategy Report.
"""

import os
import sys
from dotenv import load_dotenv

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Load environment from backend/.env or root .env
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")))
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")))

from backend.src.ai.gateway import LLMGateway
from backend.src.ai.providers.gemini import GeminiProvider
from backend.src.analysis.engine import CaseAnalysisEngine
from backend.src.analysis.schemas import CaseAnalysisExtractionResult
from backend.src.strategy.orchestrator import StrategyOrchestrator


def run_live_demo():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\n" + "=" * 70)
        print("ERROR: GEMINI_API_KEY is not set.")
        print("Please set your Gemini API key and run again:")
        print("  export GEMINI_API_KEY=\"AIzaSy...\"")
        print("  make test-gemini-live")
        print("=" * 70 + "\n")
        sys.exit(1)

    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    print("\n" + "=" * 70)
    print(f"STARTING LIVE GEMINI TEST (Model: {model_name})")
    print("=" * 70)

    # 1. Initialize Gemini Provider & Gateway
    print("\n[Stage 1] Initializing Live Gemini Provider...")
    gemini_provider = GeminiProvider(model_name=model_name, api_key=api_key)
    gateway = LLMGateway(provider=gemini_provider, approved_providers=["gemini", "mock"])
    print(f"  * Provider: {gateway.current_provider}")
    print(f"  * Model: {gateway.current_model}")

    # 2. Case Scenario: Dishonoured Cheque in Dhaka
    case_facts = {
        "title": "Haji & Sons vs Rahman Trading Co.",
        "case_type": "Cheque Dishonour (NI Act Sec 138)",
        "summary": "Commercial debt dispute: Cheque #4928192 for BDT 1,500,000 dishonoured on 25 Jan 2023.",
    }
    sample_documents = [
        {
            "id": "doc-01",
            "filename": "cheque_4928192.pdf",
            "page": 1,
            "text": "Cheque No. 4928192 dated 10-01-2023 for BDT 1,500,000 drawn on Agrani Bank Principal Branch in favour of Haji & Sons.",
        },
        {
            "id": "doc-02",
            "filename": "return_memo.pdf",
            "page": 1,
            "text": "Agrani Bank Dishonour Slip dated 25-01-2023: Reason Code 01 - Insufficient Funds.",
        },
        {
            "id": "doc-03",
            "filename": "legal_notice_receipt.pdf",
            "page": 1,
            "text": "Statutory Demand Notice dispatched on 05-02-2023 by Registered Post with A.D. Postal Receipt No. R-88392.",
        },
    ]

    # 3. Live Structured Case Analysis
    print("\n[Stage 2] Running Case Analysis & Fact Extraction via Live Gemini...")
    analysis_engine = CaseAnalysisEngine(llm_gateway=gateway)
    analysis_res = analysis_engine.analyze_case(
        case_id="live-demo-case-001",
        document_chunks=sample_documents,
    )
    print("\n--- GEMINI EXTRACTED CLIENT POSITION ---")
    print(f"  {analysis_res.client_position}")

    print("\n--- GEMINI EXTRACTED CHRONOLOGICAL TIMELINE ---")
    for event in analysis_res.timeline:
        print(f"  * [{event.event_date}] {event.title} (Page {event.source_page})")

    print("\n--- GEMINI CONTRADICTIONS & EVIDENCE GAPS ---")
    for contra in analysis_res.contradictions:
        print(f"  * Issue: {contra.issue}")
        print(f"    Statement A: {contra.statement_a}")
        print(f"    Statement B: {contra.statement_b}")

    # 4. Live Legal Strategy Orchestration
    print("\n[Stage 3] Running Master RAG + LLM Strategy Orchestration via Live Gemini...")
    orchestrator = StrategyOrchestrator(llm_gateway=gateway)
    report = orchestrator.generate_final_report(
        case_id="live-demo-case-001",
        case_facts=case_facts,
        available_documents=sample_documents,
        organization_id="org-chambers",
    )

    print("\n--- DISPUTED VS UNDISPUTED FACTS ---")
    print(f"  Undisputed ({len(report.undisputed_facts)}):")
    for f in report.undisputed_facts:
        print(f"    - [{f.id}]: {f.statement}")
    print(f"  Disputed ({len(report.disputed_facts)}):")
    for f in report.disputed_facts:
        print(f"    - [{f.id}]: {f.statement} (Reason: {f.dispute_reason})")

    print("\n--- CANDIDATE STRATEGIES & 5-DIMENSION RUBRIC ---")
    for idx, strat in enumerate(report.candidate_strategies, 1):
        rubric = strat.rubric_evaluation
        rating_str = rubric.overall_rating.value if rubric else "N/A"
        print(f"  {idx}. {strat.name} [Overall Rating: {rating_str}]")
        print(f"     Remedy: {', '.join(strat.remedies_sought)}")
        if rubric:
            print(f"     Statutory: {rubric.statutory_strength.rating.value} | Factual: {rubric.factual_support.rating.value} | Forum Risk: {rubric.forum_risk.rating.value}")

    print("\n--- 2-PLY ADVERSARIAL TREE (DEPTH 2) ---")
    primary_strat = report.candidate_strategies[0]
    if primary_strat.scenario_tree:
        for opp in primary_strat.scenario_tree.opposing_arguments:
            print(f"\n  [Opponent Move Depth 1 ({opp.plausibility.value})]:")
            print(f"    \"{opp.text}\"")
            for resp in opp.responses:
                print(f"    --> [Our Rebuttal Depth 2]:\n        \"{resp.text}\"")
                print(f"        [Residual Risk Warning]: {resp.residual_risk.risk_summary}")

    print("\n--- ACTIONABLE NEXT STEPS FOR LAWYER ---")
    for step in report.recommended_next_steps:
        print(f"  [>] {step}")

    print("\n" + "=" * 70)
    print("SUCCESS: Live Gemini End-to-End Test Completed Successfully!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_live_demo()
