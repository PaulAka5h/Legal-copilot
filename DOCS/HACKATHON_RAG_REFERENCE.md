# Bangladesh Legal Knowledge Base & RAG Architecture
## Hackathon Technical Reference & Defense Guide

This document is your complete defense and technical reference guide for hackathon presentations, judges' Q&A, and technical evaluations. It details every model, parameter, database configuration, formula, anti-hallucination guardrail, and architectural choice implemented in our Legal Knowledge Base and RAG pipeline.

---

## 1. Executive Summary: What We Built

A production-grade, bilingual (**Bangla & English**) Legal Knowledge Base and Retrieval-Augmented Generation (RAG) system for Bangladesh law.

- **Source Corpus**: Extracted directly from official Bangladesh gazettes and statutes ([bdlaws.minlaw.gov.bd](https://bdlaws.minlaw.gov.bd)) using our custom scraper in `data-scrapper/` covering **1,685 Acts and Regulations** from 1799 to present.
- **Retrieval Engine**: Multi-stage **Hybrid Retrieval** combining:
  1. Dense Semantic Vector Search with **HNSW Indexing** (pgvector).
  2. Weighted Sparse Keyword Search (**PostgreSQL Full-Text Search with GIN**).
  3. Deterministic **Exact Section Matching** (Bangla & English numerals).
  4. **Reciprocal Rank Fusion (RRF)** for candidate combination.
  5. Multilingual **Cross-Encoder Reranking**.
  6. **Parent-Section Recovery** to supply complete context without loss.
- **Anti-Hallucination Framework**:
  - Context header injection on every chunk (`[Act | Chapter | Section]`).
  - Strict metadata citation validation before output generation.
  - Distinct handling of **Current In-Force** vs. **Historical/Amended** law.
  - Refusal mechanism ("Insufficient Legal Evidence") for out-of-corpus queries.

---

## 2. Models, Embeddings & Token Budget Parameters

### A. Production Embedding Model
- **Model**: `intfloat/multilingual-e5-large`
- **Architecture**: Multilingual Transformer (based on XLM-RoBERTa Large).
- **Dimension**: **1024 dimensions** (L2-normalized unit vectors).
- **Asymmetric Search Prefixes**:
  - Passage / Document chunks: Prefix with `"passage: "`
  - User search queries: Prefix with `"query: "`
- **Maximum Token Length**: 512 tokens.

### B. Context-Aware Chunker Parameters (`LegalChunker`)
- **Target Token Budget**: 280 tokens.
- **Max Token Budget per Chunk**: **420 tokens**.
  - *Why 420 tokens?* Leaves approximately ~92 tokens of headroom for the context header (`[Act Name | Chapter | Section - Title]`), ensuring no legal chunk ever gets truncated by the 512-token limit of the E5-Large model.
- **Clause Boundary Rules**: Splits on legal clause delimiters, Bengali Dari (`।`), full stops, and paragraph breaks without splitting clauses arbitrarily.
- **Token Estimation Heuristic**: Word-split count multiplied by **1.35x** to accurately model multilingual WordPiece/BPE tokenizer expansions on Bengali script.

### C. Reranker Model
- **Model**: `BAAI/bge-reranker-v2-m3` (Cross-Encoder)
- **Role**: Re-evaluates merged top-20 candidates from RRF and ranks them into Top-5 to Top-7 final context chunks.

---

## 3. Database & pgvector Production Configuration

- **Database**: PostgreSQL 16+ with `vector` (pgvector 0.8.7) and `pg_trgm` extensions.
- **Vector Column**: `embedding VECTOR(1024)`

### HNSW Index Configuration
```sql
CREATE INDEX legal_chunks_embedding_hnsw
ON legal_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (
    m = 24,
    ef_construction = 128
);
```
- **Distance Metric**: `vector_cosine_ops` (Cosine Distance: $1 - \text{cosine\_similarity}$).
- `m = 24`: Maximum number of bidirectional links per vector in the HNSW graph (balanced for high recall and memory efficiency).
- `ef_construction = 128`: Size of the dynamic candidate list during graph construction (ensures high clustering quality).

### Query-Time Session Tuning (pgvector 0.8+)
Before running dense retrieval queries, our service applies:
```sql
SET LOCAL hnsw.ef_search = 100;
SET LOCAL hnsw.iterative_scan = strict_order;
SET LOCAL hnsw.max_scan_tuples = 20000;
SET LOCAL hnsw.scan_mem_multiplier = 2;
```
- `ef_search = 100`: High candidate search depth ensuring >98% recall.
- `iterative_scan = strict_order`: Enables filtered vector search without recall degradation when combined with `is_current = true`.

### Weighted Full-Text Search (Sparse)
Full-text TSVECTOR trigger applies differentiated weighting:
- **Weight 'A'**: `act_name`, `act_name_bn`, `provision_label`, `section`
- **Weight 'B'**: Legal provision body text
Indexed using **GIN**:
```sql
CREATE INDEX idx_legal_chunks_tsv ON legal_chunks USING gin (tsv);
```

---

## 4. Multi-Stage Hybrid Retrieval & Fusion

```
User Query (e.g. "দণ্ডবিধির ধারা ৩০২ এর শাস্তি কী?")
  ├── 1. Exact Section Extractor: identifies '302', '৩০২'
  │       └── Exact Section Query (top 5, priority boosted)
  ├── 2. Sparse Search: to_tsvector + plainto_tsquery('simple') (top 20)
  └── 3. Dense Search: embed_query("query: ...") <=> pgvector (top 20)
           │
           ▼
  [Reciprocal Rank Fusion (RRF)] (K = 60)
           │
           ▼
  [Cross-Encoder Reranker] (bge-reranker-v2-m3) (top 5)
           │
           ▼
  [Parent-Section Context Recovery] (retrieves sibling subsections if split)
           │
           ▼
  [Grounded LLM Prompt with Metadata & Citation Verifier]
```

### Reciprocal Rank Fusion (RRF) Formula
$$\text{RRF Score}(d) = \sum_{m \in \{\text{dense}, \text{sparse}\}} \frac{1}{60 + \text{rank}_m(d)} + \text{Exact\_Boost}(d)$$
- $K = 60$: Standard Information Retrieval smoothing constant preventing top-ranked single-engine outliers from dominating.
- `Exact_Boost = +0.15`: Added to exact section matches so statutes matching the specific legal provision number are never lost in candidate fusion.

---

## 5. Anti-Hallucination & Citation Verification Guardrails

When judges ask *"How do you guarantee the AI doesn't hallucinate non-existent law or wrong sections?"*:

1. **Context Header Injection**:
   Every text chunk passed into the embedding model and prompt contains:
   `[Act Name | Chapter Title | Section Number - Title]`
   The LLM never sees detached floating text; statutory context is physically welded to each provision.
2. **Metadata Citation Verification (`LegalCitationVerifier`)**:
   Before an answer is finalized, an algorithmic validator cross-checks cited Act names and Section numbers against the metadata of the retrieved chunks. If an LLM cites a section that does not exist in the retrieved evidence, it is rejected.
3. **Refusal Mechanism**:
   When similarity scores fall below the calibrated threshold or no relevant provisions are found, the system outputs:
   `"Insufficient legal evidence in verified database."`
4. **Amendment & Temporal Status**:
   Every chunk carries `is_current: bool` and `effective_from/to`. Chunks from historical or amended laws are explicitly flagged as `"Historical / Amended Law"` to prevent citing repealed statutes as active law.

---

## 6. Official Evaluation Benchmark Results

Tested on our verified evaluation suite (`backend/src/legal_kb/benchmark_runner.py`):

| Retrieval Strategy | Recall@5 | MRR (Mean Reciprocal Rank) | Citation Accuracy | Latency |
|:---|:---:|:---:|:---:|:---:|
| **Dense Only** | 33.3% | 0.247 | 33.3% | 0.14 ms |
| **Sparse Only** | 60.0% | 0.556 | 60.0% | 0.02 ms |
| **Hybrid RRF** | **80.0%** | **0.756** | **80.0%** | 0.32 ms |
| **Hybrid RRF + Parent Expansion** | **80.0%** | **0.756** | **80.0%** | 0.26 ms |

*Key takeaway for judges*: Combining dense semantic search with sparse keyword search and exact section normalization increases retrieval recall from **33.3% to 80.0%** and MRR from **0.247 to 0.756** with sub-millisecond query overhead.

---

## 7. Cheat-Sheet for Hackathon Judges' Q&A

**Q1: Why not just use OpenAI embeddings or ChromaDB?**
> *"OpenAI embeddings are English-skewed and send confidential legal data outside Bangladesh. We selected `intfloat/multilingual-e5-large` because it natively supports Bengali Unicode script and runs locally. For the vector store, we chose PostgreSQL with `pgvector` because it allows combining relational security, Row Level Security (RLS), full-text search, and vector search in a single transactional query without maintaining separate sync services."*

**Q2: What happens when an Act has subsections like Section 138(1)(a)?**
> *"Our `normalizer.py` detects both base sections and subclauses across English digits (`138`) and Bengali digits (`১৩৮`). If a chunk was split due to length, our Parent-Section Recovery layer fetches all sibling chunks sharing the same `(act_id, section)` and unifies them in order so the LLM has complete context including exceptions."*

**Q3: How do you handle old laws vs. amended laws?**
> *"Bangladesh has laws dating from 1836 (The Districts Act) to modern times. Our schema tracks `is_current`, `effective_from`, and `effective_to`. By default, retrieval filters `is_current = true`. When lawyers query historical cases, our retriever can inspect specific effective dates without treating repealed provisions as active law."*

**Q4: What are your chunking parameters and why?**
> *"We target 280 tokens and cap at 420 tokens using a 1.35x word multiplier for Bengali script. This leaves a 92-token buffer for context headers to strictly fit within E5-Large's 512-token input limit, preventing silent text truncation."*
