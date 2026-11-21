# Evaluation results

Generated 2026-11-20 14:29 UTC by `uv run python -m eval.run --provider mock --provider gemini --write` against the local approved knowledge base. Fact patterns: `backend/eval/fact_patterns.jsonl` (synthetic, SAMPLE_DATA_NOT_REAL_LAW).

Schema validity is the share of model answers that validated (after one retry) among the answers the provider returned; provider errors (free-tier rate limits, 5xx) are counted separately and fall back to the labelled mock. ai_output_rate is the share of patterns where both analysis and strategy came from the model. The mock is 1.0 by definition. Citation verification is the deterministic verifier (Step D). Reranker: mock (fused order); abstain threshold: cosine similarity 0.79.

| Metric | mock | gemini (gemini-3.5-flash-lite) |
|---|---|---|
| patterns | 30 | 30 |
| recall_at_5 | 0.8 | 0.8 |
| recall_at_10 | 0.867 | 0.867 |
| recall_at_10_en | 0.789 | 0.789 |
| recall_at_10_bn | 1.0 | 1.0 |
| mrr_at_10 | 0.67 | 0.67 |
| abstain_rate | 0.033 | 0.033 |
| citation_verification_pass_rate | 1.0 | 0.833 |
| analysis_schema_validity | 1.0 | 1.0 |
| strategy_schema_validity | 1.0 | 0.375 |
| analysis_provider_errors | 0 | 9 |
| strategy_provider_errors | 0 | 21 |
| ai_output_rate | 1.0 | 0.103 |
| strategy_node_verification_rate | 1.0 | 0.963 |
| seconds | 17.7 | 793.4 |

Retrieval misses at 10 (mock run): en-09, en-10, en-13, en-14

## Reading the results (2026-11-20)

- Retrieval is the same for both providers (the model is not involved): Recall@10 0.867 (Bangla 1.0, English 0.789), MRR@10 0.67. The four English misses are Contract Act ss. 15/17 and Specific Relief Act ss. 9/12. The cause has not been investigated yet; trying a cross-encoder reranker is a candidate next step.
- One pattern abstains (`insufficient_information`): 0.033.
- Gemini free tier: most mock fallbacks are provider errors (rate limits and 5xx: 9 of 29 analysis calls, 21 of 29 strategy calls), not invalid output. Every analysis answer the model returned validated. Strategy answers validated 3 of 8 times; the nested 3-ply schema is the weak point. Only 10% of patterns got both analysis and strategy from the model. Every fallback is labelled `ai_mock` in the product.
- Citation verification on Gemini output: 0.833. Failed citations are kept, marked unverified and capped at `insufficient`. They are never shown as verified.
- The mock column checks the pipeline end to end; its schema validity and verification rates are 1.0 by construction.

## Gemini embeddings vs e5 on the 19-Act demo knowledge base (2026-11-21)

`uv run python -m eval.retrieval --only-acts-in-db --unrelated 12` against two copies of
the same 19 approved Acts (717 chunks, `deploy/demo_acts.txt`), one embedded with
`intfloat/multilingual-e5-large`, one with `gemini-embedding-001` (1024 dims, v1). Only
queries whose expected Acts are in the set: 13 fact patterns (8 en, 5 bn) and 20 search
queries (18 en, 2 bn). Mock reranker, k = 10. Raw output: `backend/eval/results/retrieval_{e5,gemini}_subset19.json`.

| Set (n) | Recall@5 e5 | Recall@5 Gemini | Recall@10 e5 | Recall@10 Gemini | MRR@10 e5 | MRR@10 Gemini |
|---|---|---|---|---|---|---|
| facts, all (13) | 0.846 | 0.923 | 0.923 | 1.0 | 0.718 | 0.725 |
| facts, en (8) | 0.75 | 0.875 | 0.875 | 1.0 | 0.604 | 0.616 |
| facts, bn (5) | 1.0 | 1.0 | 1.0 | 1.0 | 0.9 | 0.9 |
| search, all (20) | 0.85 | 0.9 | 0.95 | 1.0 | 0.75 | 0.753 |
| search, en (18) | 0.944 | 0.889 | 0.944 | 1.0 | 0.819 | 0.807 |
| search, bn (2) | 0.0 | 1.0 | 1.0 | 1.0 | 0.121 | 0.267 |

Stop rule (Gemini more than 10 points below e5 on overall Recall@5 or @10): not triggered.
Small sample (33 queries, 7 Bangla), so these numbers say "no regression", not "better".

Abstain threshold. Each query's best cosine through the analysis path
(`case_analysis.service._retrieve`), relevant = the 33 queries above, unrelated = 12
off-topic statements (`eval/unrelated_facts.jsonl`, 6 en + 6 bn):

| Model | Lowest relevant | Highest unrelated | Chosen threshold |
|---|---|---|---|
| e5 (same subset) | 0.7997 | 0.7766 | 0.788 (production keeps 0.79) |
| gemini-embedding-001 v1 | 0.6582 | 0.5893 | **0.624** (midpoint of the gap) |

Gemini's cosine scale is lower, so the e5 value would have made the analysis abstain on
every query. `DEFAULT_MIN_SIMILARITY["gemini"] = 0.624` in `app/config.py`; it applies
when `EMBEDDING_PROVIDER=gemini` and `ANALYSIS_MIN_SIMILARITY` is unset. On the full 29
Acts with e5 the relevant and unrelated ranges overlap slightly (0.776 vs 0.782,
`retrieval_e5.json`); recalibrate when the knowledge base grows.

## e5-small (ONNX int8) vs Gemini on the 19-Act set (2026-11-22)

Same 717 chunks and the same 33 relevant queries (13 fact patterns + 20 search questions; 26 en, 7 bn) as the
Gemini run above; `eval/retrieval.py --only-acts-in-db --unrelated 12`. SAMPLE_DATA_NOT_REAL_LAW.

| Configuration | Recall@5 | Recall@10 | MRR@10 | bn Recall@10 |
|---|---|---|---|---|
| gemini-embedding-001, RRF k=60 1:1 | 0.909 | 1.000 | 0.742 | 1.000 |
| e5-large, RRF k=60 1:1 | 0.848 | 0.939 | 0.737 | 1.000 |
| e5-small int8, RRF k=60 1:1 | 0.788 | 0.879 | 0.680 | 0.714 |
| e5-small fp32 (sentence-transformers), k=60 1:1 | 0.788 | 0.848 | — | — |
| e5-small int8, k=30, dense weight 1.5 | 0.818 | 0.909 | 0.741 | 0.714 |
| e5-small int8, k=30/1.5 + LLM query rewrite, 5 runs: mean (min-max) | 0.903 | 0.945 (0.909-0.970) | 0.708 | 0.943 (0.857-1.000) |
| e5-large, k=30/1.5 (no rewrite) | 0.879 | 0.970 | 0.811 | 1.000 |

- Not kept: a pg_trgm Bangla trigram list (no change: both Bangla misses ask in Bangla about English-only Acts,
  Divorce Act s.43 and Police Act s.29, which no Bangla keyword list can reach) and an Act title + heading list
  (Recall@10 down to 0.79-0.85 at every weight).
- Query rewriting (gemini-3.5-flash-lite, `app/rag/search/query_rewrite.py`): one LLM call per new search
  query and one per fact in an analysis (statement only), cached per process. Gemini is not deterministic at
  temperature 0, so the rewrites, and Recall@10, vary by one query (3 points) between runs. 33 rewrites took
  35-41 requests (2-8 retries after 429 in the eval; the app does not retry, it searches the plain query).
- Calibration with rewriting: relevant best cosine >= 0.83, off-topic <= 0.81, threshold 0.82 (a narrow gap).
- Stop rule (within 5 points of Gemini on Recall@10 and bn >= 0.85): bn met; Recall@10 mean 0.945 = 5.5 points
  below, met in 2 of 5 runs. Full-corpus work paused for a decision.
