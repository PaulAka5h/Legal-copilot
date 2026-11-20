# Master Prompt — PokkhoAI (Legal-copilot): RAG + Case Analysis + Strategy Engine

You are working in the `Legal-copilot` repository (PokkhoAI): a decision-support platform for Bangladeshi lawyers. Before writing any code:

1. Read `AGENTS.md`, every file in `DOCS/` (PRD, TRD, SystemArchitecture, database, AI_AGENTS, Security, status, providers, backend_orchestration), and `SKILLS_AND_AGENTS.md`.
2. Inspect `data-scrapper/` code (NOT `data/raw/`, `data/processed/acts/`, `sections.jsonl`, `checkpoints.json`, `data/failed/`, `data/reports/`, `logs/`, or any `node_modules/`). To learn the dataset format, read only the first 3 lines of `data-scrapper/data/processed/sections.jsonl` with `head -n 3`.
3. Inspect `backend/`, `infra/`, `docker-compose*`, and `frontend/src/lib/api/*` + `frontend/src/lib/mock/*` (these define the shapes the UI expects).
4. Write a short gap report to `DOCS/status.md`: what exists, what is missing, what conflicts with this prompt. Then present a plan and **wait for my approval before coding**.

The Legal Product Rules in `AGENTS.md` override everything in this prompt. If something here conflicts with them, follow AGENTS.md and tell me.

---

## Fixed technical decisions

- **DB:** PostgreSQL + pgvector (existing Docker Compose). Alembic migrations only.
- **Embeddings:** `intfloat/multilingual-e5-large` via `sentence-transformers`, 1024-dim, `normalize_embeddings=True`.
  - Stored text MUST be prefixed `"passage: "`; search text MUST be prefixed `"query: "`.
  - Max 512 tokens: sub-chunk long sections (~300–400 words, ~15% overlap). Bangla tokenizes heavier; measure with the model tokenizer, not word counts.
  - Every chunk text starts with a header: `"{act_title} ({year}) — Section {number}: {heading}\n"`.
  - Embedding runs in the worker process, batched, resumable, idempotent (content hash → skip if unchanged).
  - Record `embedding_model` + `embedding_version` per row so re-embedding is possible.
- **Search:** hybrid = pgvector HNSW (`vector_cosine_ops`) + Postgres full-text (`'simple'` config, no Bangla stemmer) fused with Reciprocal Rank Fusion (k=60), then a cross-encoder reranker (`BAAI/bge-reranker-v2-m3`, behind a provider interface with a mock).
- **LLM:** behind the provider interface; default = mock provider. Only providers listed in `DOCS/providers.md`. If none approved, stub returns `NOT_CONFIGURED`.
- **Python:** FastAPI + uv, follow AGENTS.md backend conventions (Annotated, OpenAPI docs, problem+json, UTC).

---

## Idea-level changes to apply (design decisions)

1. **Lawyer-confirmed facts gate.** Fact extraction produces a structured `facts` draft (parties, dates, places, acts/omissions, documents, relief sought), each with source document + page. Analysis runs only on facts the lawyer confirmed or edited. Keep statement types separate (document says / lawyer entered / AI inference / assumption / prediction).
2. **Statutes ≠ precedents.** The scraper covers Acts only. Add a `legal_sources.source_type` (`statute`, `judgment`, `rule`, `ordinance`). Until judgments are ingested, the strategy engine must say "no precedent in knowledge base" instead of citing any case. Never cite a case that isn't in the DB.
3. **Time-aware law.** Store `effective_from`, `effective_to`, `status` (in_force/amended/repealed) per section where the scraper provides it; otherwise `unknown` and flag it. Retrieval filters by the incident date. Show "amendment status unknown" warnings.
4. **Cross-language linking.** Link the bn and en versions of the same act/section (`canonical_section_id`). Retrieve in both languages, dedupe by canonical id, answer in the lawyer's chosen language, cite both.
5. **Element-by-element violation analysis.** For each candidate offence/cause of action: list the legal ingredients from the retrieved section text, map each ingredient to a confirmed fact (or `missing`), and grade with strong / moderate / weak / insufficient information + reasons. No percentages.
6. **Chess-style strategy engine = bounded game tree.**
   - Root: current case state (facts + hearing history).
   - Each node: `move` (e.g. bail, quash, written statement, compromise, counter-case, adjournment), `legal_basis[]` (citations), `procedural_requirements`, `likely_opposing_responses[]` (child nodes), `our_counter[]`, `risk`, `cost/time` (low/med/high), `strength` label.
   - Max depth 3 plies, max 3–4 branches per node. Every node's legal basis must pass citation verification or be marked `unverified`.
   - Store trees versioned (never overwrite). Frontend renders as an expandable tree.
7. **Deterministic citation verifier (code, not LLM).** After every LLM output: each cited `chunk_id`/section must exist in the DB, be in force on the relevant date (or flagged), and any quoted text must be a substring (normalized whitespace/Unicode NFC) of the stored text. Failures → strip the claim or label `unverified`. Plus an optional LLM faithfulness pass (claim ↔ chunk support).
8. **Abstain threshold.** If top reranker score < configurable threshold, return `insufficient_information` with what is missing. No answer from model memory.
9. **Hearing reassessment as a diff.** On each new hearing (order text, notes, next date): append to the timeline, re-run retrieval + analysis on updated facts, and output: what changed, options now closed, new options, updated tree version, task list. Next hearing date stays lawyer-confirmed (AI suggests only).
10. **Deadlines in code.** Limitation periods and procedural deadlines are computed by deterministic code from a curated, cited rules table — never by the LLM. Missing rule → `NOT_CONFIGURED`.
11. **Prompt-injection safety.** Document text goes into a clearly delimited data block; system prompt states it is untrusted data. Retrieval always filtered by case in SQL with RLS.
12. **Evaluation harness.** `backend/eval/`: a labelled set (start with 30–50 fact patterns, marked `SAMPLE_DATA_NOT_REAL_LAW` if synthetic) with expected sections. Report Recall@5/10, MRR, citation-verification pass rate, abstain rate. Run in CI on the mock + local models.

---

## Build order (one step at a time; stop for my review after each)

**Step A — Ingestion pipeline (`backend/app/rag/ingest/`)**
- Read scraper JSON/JSONL output (stream, don't load whole file). Validate with the scraper's validator; reject invalid records into a report.
- Upsert acts → sections → chunks; compute content hash; enqueue embedding jobs.
- Migration: `legal_sources`, `legal_sections`, `legal_chunks(embedding vector(1024), tsv tsvector GENERATED ... 'simple', effective_from, effective_to, status, canonical_section_id, source_url, content_hash, embedding_model)`; HNSW + GIN + btree indexes.
- CLI: `uv run python -m app.rag.ingest --input ... --language bn|en --limit N --dry-run`.
- Tests: Bangla UTF-8 round-trip, idempotent re-run, sub-chunking under 512 tokens, prefix applied.

**Step B — Retrieval service**
- `retrieve(query, language, incident_date, k)` → hybrid RRF SQL → reranker → top-N with scores and provenance.
- `SET hnsw.ef_search = 100` per session.
- Endpoint `POST /lawyer/cases/{case_id}/research/search` (auth + case membership checked).
- Tests: known-section queries return expected section in top 10 (use real scraped sections, not invented ones).

**Step C — Fact extraction + confirmation**
- From case documents (existing upload/OCR pipeline) → structured facts draft with page refs → lawyer confirm/edit endpoint → versioned.

**Step D — Case analysis**
- Multi-query generation from confirmed facts → retrieval → element-by-element analysis (JSON schema, Pydantic-validated) → citation verifier → store versioned.
- Match the shapes the frontend already uses in `frontend/src/lib/mock/*` (e.g. `verification: "verified" | "unverified"`); extend the OpenAPI schema and regenerate the client.

**Step E — Strategy engine (game tree)** as described in idea #6, with verifier on every node.

**Step F — Hearing reassessment** as described in idea #9, plus client-visible summary (client sees only approved, client-visible fields).

**Step G — Eval harness + DOCS update** (`DOCS/status.md`, `DOCS/AI_AGENTS.md`, `DOCS/database.md`).

---

## Output contracts (Pydantic, strict)

```text
Citation { chunk_id, act_title, section, language, source_url, quote?, verified: bool, in_force_status }
ViolationFinding { offence_or_claim, section_citation: Citation, elements: [{ element, matched_fact_id | null, status: met|missing|disputed }], strength: strong|moderate|weak|insufficient, reasons[] , statement_type: "ai_inference" }
StrategyNode { id, parent_id, ply, actor: us|opponent|court, move, legal_basis: Citation[], requirements[], risk, cost, time, strength, reasons[], verified: bool, children: StrategyNode[] }
HearingReassessment { hearing_id, changes[], closed_options[], new_options[], tree_version, tasks[], suggested_next_date (draft only) }
```

## Rules for you (Claude Code)

- Small focused commits; run tests + isolation tests after each step; update `DOCS/status.md`.
- No invented law in code, fixtures, prompts, or examples. Synthetic legal text must be labelled `SAMPLE_DATA_NOT_REAL_LAW`.
- Never log document text or prompts.
- Do not claim something works until it's tested. If a model/provider/dataset is missing, stub with `NOT_CONFIGURED`.
- Ask me before: adding a new AI provider, changing the DB schema beyond this plan, or deleting anything.
