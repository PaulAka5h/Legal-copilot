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

- Retrieval is the same for both providers (the model is not involved): Recall@10 0.867 (Bangla 1.0, English 0.789), MRR@10 0.67. The four English misses are Contract Act ss. 15/17 and Specific Relief Act ss. 9/12: these short definition sections lose to longer neighbouring sections. A cross-encoder reranker is the next step.
- One pattern abstains (`insufficient_information`): 0.033.
- Gemini free tier: most mock fallbacks are provider errors (rate limits and 5xx: 9 of 29 analysis calls, 21 of 29 strategy calls), not invalid output. Every analysis answer the model returned validated. Strategy answers validated 3 of 8 times; the nested 3-ply schema is the weak point. Only 10% of patterns got both analysis and strategy from the model. Every fallback is labelled `ai_mock` in the product.
- Citation verification on Gemini output: 0.833. Failed citations are kept, marked unverified and capped at `insufficient`. They are never shown as verified.
- The mock column checks the pipeline end to end; its schema validity and verification rates are 1.0 by construction.
