# AI agents inside PokkhoAI

What each AI component does as implemented (Steps B–F), what it may read, what it writes, and which Legal Product Rule (AGENTS.md) each guard enforces. Nothing here is legal advice; every AI output is a lawyer-reviewed draft (Rule 5).

## Shared machinery

| Piece | Code | Notes |
|---|---|---|
| LLM provider | `app/ai/llm.py` | `LLM_PROVIDER` = `mock`, `ollama` or `gemini`; only providers listed in `LLM_APPROVED_PROVIDERS` and `DOCS/providers.md` run (Rule 10). Gemini is free tier, **synthetic sample data only**, and refused in production. Fallback chain: configured provider → mock (development only). Temperature 0, JSON-schema output. |
| Structured output | `app/ai/structured.py` | `generate_structured` validates the model output with Pydantic, retries once, then falls back to the deterministic mock builder. Mock output is labelled `origin = ai_mock`; in production a missing provider is `NOT_CONFIGURED`, never a silent mock. |
| Retrieval | `app/rag/search/` | Hybrid search over approved, current Act versions only: multilingual-e5-large dense (HNSW) + `'simple'` full-text with English/Bangla stopwords, RRF k=60, optional reranker, in-force filter by incident date. |
| Citation verifier | `app/rag/verifier.py` | Deterministic, no model: the cited chunk exists, its version is approved and current, it is in force on the incident date, and the quote is found in the chunk text (`app/rag/quote_locator.py`: exact, then normalized for whitespace, quotes, dashes, danda, ZWJ/ZWNJ and English case, then a strict fuzzy match, ratio >= 0.9 on quotes of 20+ characters and 4+ words). A found quote is **replaced by the exact span from the database** (warning `quote_repaired:normalized|fuzzy`), so a stored quote is always an exact substring of the source; a quote that is not found is dropped (null) and its citation or element is `unverified`. Findings with any unverified part are capped at `insufficient`; the analysis abstains only when no finding has a verified citation. (Rules 1, 2) |
| Scrub | `app/rag/verifier.py` | Removes probability language ("70% chance", "likely to win") and case-law citations; when no judgments are loaded, adds "No precedent in knowledge base". (Rules 1, 4) |
| Prompt hygiene | all agents | Document text is passed as quoted data with an instruction that it is never instructions (Rule 9). Prompts and document text are never logged; `ai_runs` stores provider, model, prompt version and an input hash. |

## 1. Fact extraction (Step C)

- **Input:** current `extracted_pages` of a processed document (max 150 pages per run).
- **Output:** draft `case_facts` with `statement_type = document_says`, each with a `case_fact_sources` row pinning the page version and a quote.
- **Guards:** deterministic quote check (quote must appear in the page and be at least 20 characters and 4 words); facts are drafts until a lawyer reviews them; only lawyer-reviewed or lawyer-entered facts reach analysis through the `case_facts_for_analysis` view. Requires `can_run_ai`.

## 2. Case analysis (Step D) — `app/case_analysis/`

- **Input:** only `case_facts_for_analysis`; the fact-set hash is stored with the result.
- **Process:** several queries per fact → retrieval with the incident-date filter → abstain if no source passes the similarity threshold (`ANALYSIS_MIN_SIMILARITY`; per embedding model: e5 0.79, Gemini 0.624) → the prompt numbers each provision's sentences `[S1]…` and asks for verbatim quotes plus `quote_ref` sentence numbers (hints for the verifier, `case-analysis-v2`) → model drafts findings element by element → verifier → scrub.
- **Output:** versioned `case_analyses` row. Each `ViolationFinding` has `statement_type = ai_inference`, strength `strong`/`moderate`/`weak`/`insufficient` (Rule 4), elements mapped to fact ids, and verified citations. Status `insufficient_information` when it abstains.
- **API:** `POST/GET /api/v1/lawyer/cases/{id}/analysis`, `/versions`, `/versions/{n}`.

## 3. Strategy tree (Step E) — `app/strategy_tree/`

- **Input:** one analysis version and its verified sources.
- **Process:** 3-ply game tree (our move → opponent/court response → our reply), 3–4 moves at the root and up to 3 branches per node. Every node carries legal basis, requirements, risk, cost, time, strength and reasons, and goes through the verifier; a node whose legal basis fails verification is marked unverified and capped at `insufficient`.
- **Never:** percentages, predicted outcomes, or precedent claims ("No precedent in knowledge base").
- **API:** `POST/GET /api/v1/lawyer/cases/{id}/strategy`, `/versions`, `/versions/{n}`, `/compare?base=&target=`. Lawyer only (Rule 8).

## 4. Hearing reassessment (Step F) — `app/hearing_updates/`

- **Input:** a lawyer-entered hearing update (order text, notes, next date, whether the lawyer confirms it).
- **Process:** append the update to the timeline → store the order text as a `lawyer_entered` fact → re-run analysis and strategy → diff against the previous versions.
- **Output:** `HearingReassessment` (finding changes, closed and new options, tree version, tasks). A date found in the order text by code is a **draft suggestion only**; a confirmed hearing is created only when the lawyer confirms the date (Rule 5). A plain-language client summary (order and confirmed date, no analysis or strategy) is saved as a **draft** client update; the client sees it only after the lawyer publishes it (Rule 8).
- **API:** `/api/v1/lawyer/cases/{id}/hearings`, `/hearings/timeline`, `/hearings/{hearing_id}/updates`, `/reassessments`.

## Evaluation

`cd backend && uv run python -m eval.run [--provider gemini] --write` runs the synthetic labelled set (`backend/eval/fact_patterns.jsonl`, SAMPLE_DATA_NOT_REAL_LAW) and writes `DOCS/eval_results.md`: Recall@5/10, MRR, abstain rate, citation-verification pass rate, and analysis/strategy schema-validity rate.

## Known limits

- The Penal Code is not in the knowledge base (bdlaws was unreachable); criminal-offence analysis is limited to the loaded Acts.
- The reranker is the mock (fused order) unless a cross-encoder is configured; the abstain decision uses dense similarity.
- No judgments are loaded, so the system never cites precedent.
