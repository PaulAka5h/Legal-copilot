# ==============================================================================
# Makefile for AI Legal Copilot for Bangladesh
# ==============================================================================

.PHONY: help infra-up infra-down infra-logs backend-dev backend-stop backend-test frontend-dev frontend-stop frontend-build scraper-run ingest-legal-kb db-status clean

help:
	@echo "Available commands for AI Legal Copilot:"
	@echo ""
	@echo "  --- Infrastructure (Docker) ---"
	@echo "  make infra-up          Start PostgreSQL (pgvector), Redis, and MinIO containers"
	@echo "  make infra-down        Stop infrastructure containers"
	@echo "  make infra-logs        View live logs from infrastructure containers"
	@echo ""
	@echo "  --- Backend (FastAPI & RAG) ---"
	@echo "  make backend-dev       Start FastAPI development server on http://localhost:8000"
	@echo "  make backend-stop      Stop running backend server (frees port 8000)"
	@echo "  make backend-test      Run the full backend test suite with pytest"
	@echo "  make test-strategy     Run Chess Strategy Engine CLI verification"
	@echo "  make test-report       Run RAG + LLM Full Legal Strategy Report verification"
	@echo "  make test-gemini-live  Run Live Gemini API (gemini-2.5-flash) End-to-End Test"
	@echo ""
	@echo "  --- Frontend (Next.js) ---"
	@echo "  make frontend-dev      Start Next.js frontend development server on http://localhost:3000"
	@echo "  make frontend-stop     Stop running frontend dev server (frees port 3000)"
	@echo "  make frontend-build    Build Next.js frontend for production"
	@echo ""
	@echo "  --- Data & Knowledge Base ---"
	@echo "  make ingest-legal-kb   Batch-ingest scraped Bangladesh Acts into PostgreSQL pgvector"
	@echo "  make db-status         Check total seeded Acts, sections, and vector chunks in pgvector"
	@echo "  make scraper-run       Resume/run Bangladesh law scraper in data-scrapper/"
	@echo ""

# ------------------------------------------------------------------------------
# Docker Infrastructure
# ------------------------------------------------------------------------------
infra-up:
	@echo "Starting Docker Compose services (PostgreSQL + pgvector, Redis, MinIO)..."
	docker compose -f compose.yaml up -d
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 2
	@echo "Services running. PostgreSQL on 5432, Redis on 6379, MinIO on 9000/9001."

infra-down:
	@echo "Stopping Docker Compose services..."
	docker compose -f compose.yaml down

infra-logs:
	docker compose -f compose.yaml logs -f

# ------------------------------------------------------------------------------
# Backend (FastAPI, Pytest, Uvicorn)
# ------------------------------------------------------------------------------
backend-dev:
	@echo "Starting FastAPI backend server on http://localhost:8000 (Docs at /docs)..."
	cd backend && PYTHONPATH=.. uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

backend-stop:
	@echo "Stopping backend server on port 8000..."
	@fuser -k 8000/tcp 2>/dev/null || pkill -f "uvicorn src.main:app" 2>/dev/null || echo "No server was running on port 8000."
	@echo "Backend server stopped."

backend-test:
	@echo "Running backend test suite..."
	cd backend && PYTHONPATH=.. uv run pytest tests/ -v

test-llm:
	@echo "Testing LLM Case Analysis & Fact Extraction..."
	cd backend && PYTHONPATH=.. uv run python -c '\
from src.analysis.engine import CaseAnalysisEngine; \
engine = CaseAnalysisEngine(); \
chunks = [{"id": "c1", "filename": "cheque.pdf", "page": 1, "text": "Cheque 4928192 for BDT 1,500,000 on 10 Jan 2023."}]; \
res = engine.analyze_case("case-demo", document_chunks=chunks); \
print("\n[1] CLIENT POSITION:\n", res.client_position); \
print("\n[2] TIMELINE:"); \
[print(f"  * {e.event_date}: {e.title} (Page {e.source_page})") for e in res.timeline]; \
print("\n[3] CONTRADICTIONS:"); \
[print(f"  * {c.issue}: {c.statement_a} vs {c.statement_b}") for c in res.contradictions]; \
print("\n[4] VERIFIED BANGLADESH STATUTE CITATIONS:"); \
[print(f"  * {cit.act_name}, Section {cit.section} ({cit.source_url})") for cit in res.citations]; \
print("\nSUCCESS: LLM response parsed and verified!")'

test-strategy:
	@echo "Testing Chess-Inspired Legal Strategy Engine..."
	cd backend && PYTHONPATH=.. uv run python -c '\
from src.strategy.engine import StrategyEngine; \
engine = StrategyEngine(); \
strats = engine.generate_strategies_for_case("case-demo-strat", {"case_type": "Cheque Dishonour"}, [{"filename": "cheque.pdf", "text": "Cheque 4928192"}]); \
print(f"\n[1] GENERATED {len(strats)} CANDIDATE STRATEGIES (DYNAMIC K):"); \
[print(f"  * {s.name} (Status: {s.status.value}, Rating: {s.rubric_evaluation.overall_rating.value})") for s in strats]; \
comp = engine.get_latest_comparison("case-demo-strat"); \
print("\n[2] STRATEGY COMPARISON & REASONED RECOMMENDATION:"); \
print("  Recommendation:", comp.recommendation_reason); \
print("  Trade-offs:", comp.trade_offs_analysis); \
print("\n[3] ADVERSARIAL SCENARIO TREE (DEPTH 2):"); \
tree = strats[0].scenario_tree; \
[print(f"  [Opponent Depth 1 ({opp.plausibility.value})]: {opp.text}\n    -> [Our Rebuttal Depth 2]: {opp.responses[0].text[:85]}...\n       [Residual Risk]: {opp.responses[0].residual_risk.risk_summary}") for opp in tree.opposing_arguments]; \
print("\nSUCCESS: Chess Strategy Engine verified!")'

test-report:
	@echo "Testing Full RAG + LLM Legal Strategy Report Orchestration..."
	cd backend && PYTHONPATH=.. uv run python -c '\
from src.strategy.orchestrator import StrategyOrchestrator; \
orch = StrategyOrchestrator(); \
rep = orch.generate_final_report("case-report-demo", {"case_type": "Cheque Dishonour", "summary": "Commercial debt dispute on cheque #4928192"}, [{"filename": "cheque.pdf", "text": "Cheque 4928192"}]); \
print("\n[1] CASE SUMMARY:\n ", rep.case_summary); \
print(f"\n[2] MATERIAL FACTS (UNDISPUTED: {len(rep.undisputed_facts)}, DISPUTED: {len(rep.disputed_facts)}):"); \
[print(f"  * [Undisputed {f.id}]: {f.statement} ({f.source_document})") for f in rep.undisputed_facts]; \
[print(f"  * [Disputed {f.id}]: {f.statement} (Reason: {f.dispute_reason})") for f in rep.disputed_facts]; \
print(f"\n[3] LEGAL ISSUES & PRECEDENT ANALYSIS ({len(rep.identified_issues)} issues):"); \
[print(f"  * {i.issue_text} -> Statute: {i.applicable_statutes[0].act_name if i.applicable_statutes else None}") for i in rep.identified_issues]; \
print(f"\n[4] CANDIDATE STRATEGIES GENERATED: {len(rep.candidate_strategies)}"); \
[print(f"  * {s.name} ({s.rubric_evaluation.overall_rating.value if s.rubric_evaluation else None})") for s in rep.candidate_strategies]; \
print(f"\n[5] RECOMMENDED NEXT STEPS ({len(rep.recommended_next_steps)}):"); \
[print(f"  - {step}") for step in rep.recommended_next_steps]; \
print("\nSUCCESS: RAG + LLM Legal Strategy Report verified!")'

test-gemini-live:
	@echo "Running Live Gemini API End-to-End Demonstration..."
	cd backend && PYTHONPATH=.. uv run python scripts/live_gemini_demo.py

# ------------------------------------------------------------------------------
# Frontend (Next.js)
# ------------------------------------------------------------------------------
frontend-dev:
	@echo "Starting Next.js frontend on http://localhost:3000..."
	cd frontend && npm run dev

frontend-stop:
	@echo "Stopping frontend server on port 3000..."
	@fuser -k 3000/tcp 2>/dev/null || pkill -f "next-server" 2>/dev/null || echo "No server was running on port 3000."
	@echo "Frontend server stopped."

frontend-build:
	@echo "Building frontend..."
	cd frontend && npm run build

# ------------------------------------------------------------------------------
# Data Scraper & Legal Knowledge Base
# ------------------------------------------------------------------------------
ingest-legal-kb:
	@echo "Ingesting scraped legal dataset into PostgreSQL pgvector..."
	cd backend && PYTHONPATH=.. uv run python -m src.legal_kb.ingest_all

db-status:
	@echo "Querying PostgreSQL pgvector chunk and act statistics..."
	@docker exec -it $$(docker ps -qf "name=postgres") psql -U postgres -d legal_copilot -c "\
		SELECT count(*) AS total_chunks, count(DISTINCT act_id) AS total_acts, count(DISTINCT section) AS total_sections FROM legal_chunks;" 2>/dev/null || \
	docker exec -it 3cfd4cd523d9 psql -U researchsphere -d legal_copilot_test -c "\
		SELECT count(*) AS total_chunks, count(DISTINCT act_id) AS total_acts, count(DISTINCT section) AS total_sections FROM legal_chunks;"

scraper-run:
	@echo "Running Bangladesh Laws Scraper..."
	cd data-scrapper && ./venv/bin/python main.py

clean:
	@echo "Cleaning Python caches..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
