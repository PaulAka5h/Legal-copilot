"""Benchmark Evaluation Runner for Bangladesh Legal RAG.

Compares:
1. Dense Retrieval Only
2. Sparse FTS Retrieval Only
3. Hybrid Retrieval with RRF
4. Hybrid Retrieval with RRF + Parent Section Expansion

Evaluates:
- Recall@5
- Precision@5
- MRR (Mean Reciprocal Rank)
- Citation Accuracy
- Latency (ms)
"""

import time
from typing import Dict, List
import pandas as pd
from backend.src.legal_kb.benchmark_data import BENCHMARK_DATASET, LegalBenchmarkQuery
from backend.src.legal_kb.chunker import LegalChunker
from backend.src.legal_kb.embeddings import MockEmbeddingProvider
from backend.src.legal_kb.prompts import LegalCitationVerifier
from backend.src.legal_kb.reranker import MockReranker
from backend.src.legal_kb.retriever import LegalHybridRetriever
from backend.src.legal_kb.schemas import LegalLanguage, ScrapedSectionRecord
from backend.src.legal_kb.vector_store import InMemoryVectorStore


def run_legal_rag_benchmark() -> pd.DataFrame:
    # 1. Setup in-memory store populated with core provisions
    store = InMemoryVectorStore()
    embedding_provider = MockEmbeddingProvider(dimension=128)

    sample_provisions = [
        ("The Penal Code, 1860", "300", "Murder definition", "Except in cases hereinafter excepted, culpable homicide is murder under grave and sudden provocation."),
        ("The Penal Code, 1860", "302", "Punishment for murder", "Whoever commits murder shall be punished with death or imprisonment for life."),
        ("The Penal Code, 1860", "378", "Theft", "Whoever intending to take dishonestly any movable property out of possession of any person."),
        ("The Penal Code, 1860", "379", "Punishment for theft", "Whoever commits theft shall be punished with imprisonment up to three years or fine."),
        ("The Penal Code, 1860", "420", "Cheating and dishonestly inducing delivery", "Whoever cheats and thereby dishonestly induces the person deceived to deliver property."),
        ("The Penal Code, 1860", "405", "Criminal breach of trust", "Whoever being entrusted with property dishonestly misappropriates it."),
        ("The Penal Code, 1860", "384", "Punishment for extortion", "Whoever commits extortion shall be punished with imprisonment up to three years."),
        ("The Penal Code, 1860", "323", "Voluntarily causing hurt", "Whoever voluntarily causes hurt shall be punished with imprisonment up to one year."),
        ("The Penal Code, 1860", "100", "Right of private defence", "The right of private defence of the body extends to causing death under deadly apprehension."),
        ("The Negotiable Instruments Act, 1881", "138", "Dishonour of cheque", "Dishonour of cheque for insufficiency of funds in account."),
    ]

    chunker = LegalChunker(max_tokens=400)
    all_chunks = []
    for act, sec, title, body in sample_provisions:
        rec = ScrapedSectionRecord(
            document_id=f"act-{sec}",
            act_id="11" if "Penal" in act else "25",
            act_name=act,
            language=LegalLanguage.EN,
            section_number=sec,
            section_title=title,
            section_content=body,
            source_url=f"https://bdlaws.minlaw.gov.bd/sec-{sec}.html",
            content_hash=f"hash-{sec}",
        )
        all_chunks.extend(chunker.chunk_section(rec))

    embeddings = embedding_provider.embed_documents([c.text for c in all_chunks])
    store.add_chunks(all_chunks, embeddings)

    retriever = LegalHybridRetriever(
        vector_store=store,
        embedding_provider=embedding_provider,
        reranker=MockReranker(),
    )

    strategies = ["Dense Only", "Sparse Only", "Hybrid RRF", "Hybrid RRF + Parent Expansion"]
    metrics = {s: {"hits_at_5": 0, "mrr_sum": 0.0, "total_eval": 0, "verified_citations": 0, "total_time": 0.0} for s in strategies}

    eval_queries = [q for q in BENCHMARK_DATASET if q.should_answer and q.expected_section]

    for q in eval_queries:
        for strat in strategies:
            start_t = time.perf_counter()
            if strat == "Dense Only":
                q_vec = embedding_provider.embed_query(q.query)
                results = store.search_dense(q_vec, top_k=5)
            elif strat == "Sparse Only":
                results = store.search_sparse(q.query, top_k=5)
            elif strat == "Hybrid RRF":
                results = retriever.retrieve(q.query, rerank_top_k=5, expand_parent_sections=False)
            else:  # Hybrid RRF + Parent Expansion
                results = retriever.retrieve(q.query, rerank_top_k=5, expand_parent_sections=True)

            elapsed = (time.perf_counter() - start_t) * 1000  # ms
            metrics[strat]["total_time"] += elapsed
            metrics[strat]["total_eval"] += 1

            # Evaluate Recall@5 and MRR
            found_rank = None
            for rank, r in enumerate(results, start=1):
                if r.chunk.section == q.expected_section or f"section {q.expected_section}" in (r.chunk.provision_label or "").lower():
                    found_rank = rank
                    break

            if found_rank is not None:
                metrics[strat]["hits_at_5"] += 1
                metrics[strat]["mrr_sum"] += 1.0 / found_rank

                # Check citation verifiability
                is_valid, _ = LegalCitationVerifier.verify_citation(
                    citation_act=q.expected_act,
                    citation_section=q.expected_section,
                    retrieved_chunks=[r.chunk for r in results],
                )
                if is_valid:
                    metrics[strat]["verified_citations"] += 1

    report_rows = []
    for strat, m in metrics.items():
        total = m["total_eval"]
        recall_5 = (m["hits_at_5"] / total) if total else 0.0
        mrr = (m["mrr_sum"] / total) if total else 0.0
        cite_acc = (m["verified_citations"] / total) if total else 0.0
        avg_lat = m["total_time"] / total if total else 0.0

        report_rows.append({
            "Retrieval Configuration": strat,
            "Recall@5": f"{recall_5 * 100:.1f}%",
            "MRR": f"{mrr:.3f}",
            "Citation Accuracy": f"{cite_acc * 100:.1f}%",
            "Avg Latency (ms)": f"{avg_lat:.2f} ms",
        })

    return pd.DataFrame(report_rows)


if __name__ == "__main__":
    df = run_legal_rag_benchmark()
    print("\n" + df.to_markdown(index=False))
