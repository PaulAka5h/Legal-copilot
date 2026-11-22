# Approved Providers

This file is the single list of external services that may receive project data. The LLM gateway reads the approved list from configuration (`LLM_APPROVED_PROVIDERS`) and refuses to send case content to anything not on it.

Last updated: 2026-11-21

## Current state

| Provider | Purpose | Data allowed | Status |
|---|---|---|---|
| mock | Tests and local development | Synthetic only | Approved for all non-production use |
| Ollama (local, OpenAI-compatible API at `LLM_BASE_URL=http://localhost:11434/v1`) | LLM for fact extraction | Client case data, **development only**; runs on this machine, no data leaves it | Approved by Arafath 2026-11-20 for development; see review record. Production use needs a full review |
| Google Gemini API (free tier), model from `GEMINI_MODEL`, then `GEMINI_FALLBACK_MODEL` | LLM for fact extraction, case analysis, strategy (`app/ai/llm.py`), and search query rewriting (`app/rag/search/query_rewrite.py`, `SEARCH_QUERY_REWRITE`: the text of legal searches and of analysed case facts) | **SYNTHETIC SAMPLE DATA ONLY** (`SAMPLE_DATA_NOT_REAL_LAW`). Never client documents. Refused in production by code | Enabled by Arafath 2026-11-20 for the demo. Free-tier terms allow Google to use submitted data to improve its products, which is why only synthetic data is allowed. Fallback chain: `GEMINI_MODEL` (429/503 retried at 2 s, 5 s, 10 s) -> `GEMINI_FALLBACK_MODEL` -> mock, within a 100 s per-request budget; mock output is labelled `ai_mock`; the answering model is logged (`llm.answered`) and stored with the analysis |
| (none yet) | External LLM for client data | None | No external provider has been reviewed or approved for client case data |
| self-hosted `intfloat/multilingual-e5-small`, ONNX int8 (`EMBEDDING_PROVIDER=e5_small_onnx`, default) | Embeddings: legal knowledge base and queries (Render demo: inside the container) | Runs on our own hardware or the app server; no external data transfer | Chosen by the project owner 2026-11-22. Model files downloaded from Hugging Face at a pinned revision with pinned SHA-256 (build time only) |
| self-hosted `intfloat/multilingual-e5-large` | Embeddings | Runs on our own hardware; no external data transfer | In use for the legal knowledge base (public statute text only) |
| self-hosted `BAAI/bge-reranker-v2-m3` (optional) | Reranking legal search results | Runs on our own hardware; no external data transfer | Optional via `RERANKER_PROVIDER`; default is the mock reranker |
| Kaggle Notebooks (GPU compute) | Running the same e5-large model for the legal knowledge base | Public statute text from `legal_chunks` only (exported by `app.rag.embed export`); never case documents, client data, or prompts | Directed by Arafath 2026-11-20 for legal KB embeddings only; review checklist below not completed |
| (none yet) | OCR | None | Local Tesseract is the default; no cloud OCR approved |
| Hugging Face Inference API (`hf-inference` provider), same `intfloat/multilingual-e5-large` model | Query embeddings when `EMBEDDING_PROVIDER=hf_api` (Render free demo, no torch) | **SYNTHETIC SAMPLE DATA ONLY**: the text of legal searches and of case facts used as analysis queries leaves the server. Refused when `APP_ENV=production` by code | Directed by the project owner 2026-11-21 for the free Render demo; review checklist not completed. **Replaced by Gemini embeddings the same day** (token invalidated by the owner); the code path remains, refused in production |
| Google Gemini API (free tier), embedding model from `GEMINI_EMBEDDING_MODEL` (`gemini-embedding-001`, 1024 dims) | Embeddings when `EMBEDDING_PROVIDER=gemini` (Render free demo): legal search queries and case facts used as analysis queries (`RETRIEVAL_QUERY`), and the public statute text of the legal knowledge base (`RETRIEVAL_DOCUMENT`, `python -m app.rag.embed reembed`) | **SYNTHETIC SAMPLE DATA ONLY** (`SAMPLE_DATA_NOT_REAL_LAW`) plus public statute text. Never client documents. Refused when `APP_ENV=production` by code, same rule as `hf_api` | Directed by the project owner 2026-11-21 for the free Render demo (branch `deploy/render`); review checklist not completed. Same free-tier terms as the Gemini LLM row (Google may use submitted data). Search refuses to compare vectors from different models (503 `EMBEDDING_MODEL_MISMATCH`) |
| Neon (managed Postgres, free plan) | Database for the Render demo | Synthetic only (demo lawyer, `SAMPLE_DATA_NOT_REAL_LAW` case, public statute text) | Directed by the project owner 2026-11-21 for the demo; review checklist not completed. RLS stays forced (see `deploy/neon_setup.md`) |
| Backblaze B2 (S3-compatible, free tier) | Original uploaded documents for the Render demo | Synthetic only | Directed by the project owner 2026-11-21 for the demo; review checklist not completed |
| Render (free web service) | Hosts the demo API container | Synthetic only (processes all demo requests in memory) | Directed by the project owner 2026-11-21 for the demo; review checklist not completed |

Until a provider passes the review below, the platform runs with the mock provider or with synthetic data only. Real client documents must not be uploaded to any environment that can reach an unapproved provider.

## Data allowed per provider

Use one of these values in the table above:

| Value | Meaning |
|---|---|
| Synthetic only | Fake data created for tests and demos |
| Consented demo data | Real documents from a person who gave written consent for demo use |
| Client case data | Real client material, after a full review and counsel sign-off |

## Review checklist

Complete one copy of this checklist per provider and per product tier. Save the answers in section "Review records" below. Do not approve a provider with open items.

| # | Question | Answer | Evidence (link or document) |
|---|---|---|---|
| 1 | Where is data processed and stored (country and region)? | | |
| 2 | Is submitted data retained? For how long? Can retention be turned off or minimized? | | |
| 3 | Is submitted data used to train models? Is that off by contract or by account setting? | | |
| 4 | Who at the provider can access submitted data, and under what controls? | | |
| 5 | Is there a data processing agreement? | | |
| 6 | What are the breach notification terms and timelines? | | |
| 7 | Does the provider offer encryption in transit and at rest? | | |
| 8 | Can we get deletion of submitted data on request? | | |
| 9 | Does the provider log prompts and outputs? Can logging be disabled? | | |
| 10 | Which sub-processors does the provider use? | | |
| 11 | Do the terms fit a lawyer's professional confidentiality duties? (needs counsel) | | |
| 12 | Does any Bangladeshi data protection or transfer rule apply to this transfer? (needs counsel) | | |
| 13 | Is the model's Bangla reading and writing good enough on our evaluation set? | | |
| 14 | Are structured outputs reliable enough for our schemas? | | |
| 15 | Cost per case analysis and per strategy run within budget? | | |

## Approval rules

1. A provider is approved by name, product, and region. A change in any of these needs a new review.
2. Approval states which data class is allowed (synthetic, consented demo, client case data).
3. Approval is recorded below with the date, the reviewer, and the counsel sign-off where required.
4. The approved list in the deployment configuration must match this file. A mismatch is a defect.
5. Review again when the provider changes its terms, when we change region, or at least once a year.
6. Client data is never used to train or fine-tune any model unless a separate written authorization, a lawful basis, and safeguards are recorded here.

## Minimum content rule

Even for an approved provider, send only what the task needs: the retrieved passages and the question, not whole case files. Strip names and contact details when they are not needed for the task. The gateway records which passages were sent in `ai_runs` as IDs and hashes, not as text.

## Model selection record

Model choice is made by testing, not by reputation. Record each comparison here.

| Date | Candidate (provider, model) | Bangla reading | English reading | Structured output reliability | Citation accuracy | Cost per run | Latency | Notes |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

Run the evaluation set from `Skills and agents.md` section 7 for every candidate and on every model change.

## Embedding and OCR choices

| Component | Candidates to test | Chosen | Reason |
|---|---|---|---|
| Embeddings | A multilingual model with Bangla support, such as BGE-M3 or multilingual-e5 | `intfloat/multilingual-e5-large`, self-hosted (2026-11-20, master prompt) | Runs locally via sentence-transformers; weights downloaded once from Hugging Face, no project data leaves the server. Retrieval quality on a labelled bn/en set is still to be measured (Step G eval) |
| OCR | Tesseract with Bengali and English data; a cloud OCR only if local accuracy is not good enough | Not chosen | Test on real scanned papers; a cloud OCR needs a full review |

## Review records

```
Provider and product: Ollama, local server, OpenAI-compatible chat completions API
Region: the developer's own machine (localhost); no network egress for model calls
Data class approved: Client case data, development environment only
Review date: 2026-11-20
Reviewer: Arafath (Backend Dev 2)
Counsel sign-off (name, date): not recorded; required before any production use with client data
Checklist answers:
  1 Where processed: on the local machine only. 2 Retention: none by our code; Ollama keeps no prompt store
  (keep OLLAMA_DEBUG off so prompts are not written to its logs). 3 Training: no. 4 Access: the machine's user.
  5 DPA: not applicable (no third party). 6 Breach terms: not applicable. 7 Encryption: localhost traffic only;
  disk encryption is the machine owner's responsibility. 8 Deletion: local. 9 Logging: our gateway never logs
  prompts or document text. 10 Sub-processors: none. 11-12 Counsel: pending. 13-15: to be measured on our eval set.
Conditions: LLM_BASE_URL must point at localhost (enforced in code); model weights are downloaded once;
  structured output requested with a JSON schema and validated with Pydantic.
Next review due: before production use, or on any change of host, model, or data class.
```

Template for each record:

```
Provider and product:
Region:
Data class approved:
Review date:
Reviewer:
Counsel sign-off (name, date) or "not required for this data class":
Checklist answers: (link to the filled table)
Conditions: (for example "retention disabled", "zero data retention enabled")
Next review due:
```

```
Provider and product: Google Gemini API (Generative Language API), free tier
Region: Google-managed; not controlled
Data class approved: Synthetic only (SAMPLE_DATA_NOT_REAL_LAW). Real client documents must not be uploaded to any
  environment where LLM_PROVIDER=gemini.
Review date: 2026-11-20
Reviewer: Arafath (Backend Dev 2)
Counsel sign-off: not required for synthetic data; required (and not given) for any other data class
Conditions: refused when APP_ENV=production (enforced in code); key in a header, never in URLs or logs;
  Settings.gemini_api_key is a SecretStr; temperature 0; JSON-schema output validated with Pydantic;
  tests never call Gemini (conftest removes the key).
Incident 2026-11-20: the key was printed in a pytest failure message during development; reprs were fixed
  (SecretStr, repr=False). The key must be rotated.
Next review due: before any non-synthetic use.
```

## Environment settings

```
LLM_PROVIDER=mock
LLM_APPROVED_PROVIDERS=mock
# Development with the approved local Ollama server:
# LLM_PROVIDER=ollama
# LLM_APPROVED_PROVIDERS=mock,ollama
# LLM_BASE_URL=http://localhost:11434/v1
# LLM_MODEL=<local model name>
```

Change these only after a review record exists in this file.
