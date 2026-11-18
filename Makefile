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
