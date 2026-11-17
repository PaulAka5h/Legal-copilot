"""Hybrid Retrieval and Reciprocal Rank Fusion (RRF) Engine.

Combines:
1. Dense Vector Search (E5 large cosine similarity)
2. Sparse Keyword Retrieval (PostgreSQL full-text search)
3. Exact Section Identifier Search (Section 302, ধারা ৩০২, etc.)
4. Reciprocal Rank Fusion (RRF Score = SUM(1 / (60 + rank)))
5. Multilingual Reranker (bge-reranker-v2-m3)
6. Complete Parent-Section Context Recovery
"""

from typing import Any, Dict, List, Optional
from backend.src.legal_kb.embeddings import BaseEmbeddingProvider
from backend.src.legal_kb.normalizer import extract_section_numbers
from backend.src.legal_kb.reranker import BaseReranker
from backend.src.legal_kb.schemas import LegalChunkPayload
from backend.src.legal_kb.vector_store import BaseVectorStore, VectorSearchResult


class LegalHybridRetriever:
    """Production-grade hybrid legal retriever combining vector, keyword, and exact section matching."""

    def __init__(
        self,
        vector_store: BaseVectorStore,
        embedding_provider: BaseEmbeddingProvider,
        reranker: Optional[BaseReranker] = None,
        rrf_k: int = 60,
    ):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.reranker = reranker
        self.rrf_k = rrf_k

    def rrf_fuse(
        self,
        dense_results: List[VectorSearchResult],
        sparse_results: List[VectorSearchResult],
        exact_results: List[VectorSearchResult],
        top_k: int = 25,
    ) -> List[VectorSearchResult]:
        """Combines multiple ranked lists using Reciprocal Rank Fusion:

        RRF Score = SUM(1 / (K + rank))
        Exact section matches receive an explicit priority rank boost.
        """
        scores: Dict[str, float] = {}
        chunk_map: Dict[str, LegalChunkPayload] = {}

        # 1. Exact matches get priority placement (rank 0 equivalent boost)
        for rank, res in enumerate(exact_results):
            cid = str(res.chunk.id)
            chunk_map[cid] = res.chunk
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (self.rrf_k + rank)) + 0.15

        # 2. Dense results
        for rank, res in enumerate(dense_results):
            cid = str(res.chunk.id)
            chunk_map[cid] = res.chunk
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (self.rrf_k + rank))

        # 3. Sparse keyword results
        for rank, res in enumerate(sparse_results):
            cid = str(res.chunk.id)
            chunk_map[cid] = res.chunk
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (self.rrf_k + rank))

        sorted_chunks = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        merged: List[VectorSearchResult] = []
        for cid, score in sorted_chunks[:top_k]:
            merged.append(
                VectorSearchResult(
                    chunk=chunk_map[cid],
                    score=score,
                    retrieval_type="rrf_hybrid",
                )
            )

        return merged

    def retrieve(
        self,
        query: str,
        dense_k: int = 20,
        sparse_k: int = 20,
        rerank_top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        expand_parent_sections: bool = True,
        similarity_threshold: Optional[float] = None,
    ) -> List[VectorSearchResult]:
        """Executes full hybrid retrieval pipeline:

        1. Exact section extraction & lookup
        2. Sparse keyword retrieval
        3. Dense semantic vector retrieval (using query: prefix)
        4. Reciprocal Rank Fusion
        5. Multilingual Cross-Encoder Reranking
        6. Parent Section Assembly
        """
        # Step 1: Exact Section matching
        candidate_sections = extract_section_numbers(query)
        exact_results: List[VectorSearchResult] = []
        for sec in candidate_sections:
            exact_hits = self.vector_store.search_exact_section(
                section_number=sec,
                act_id=filters.get("act_id") if filters else None,
                top_k=5,
                filters=filters,
            )
            exact_results.extend(exact_hits)

        # Step 2: Sparse keyword search
        sparse_results = self.vector_store.search_sparse(
            query_text=query,
            top_k=sparse_k,
            filters=filters,
        )

        # Step 3: Dense vector search
        query_vec = self.embedding_provider.embed_query(query)
        dense_results = self.vector_store.search_dense(
            query_embedding=query_vec,
            top_k=dense_k,
            filters=filters,
        )

        # Step 4: RRF Fusion
        fused_candidates = self.rrf_fuse(
            dense_results=dense_results,
            sparse_results=sparse_results,
            exact_results=exact_results,
            top_k=30,
        )

        # Step 5: Optional Cross-Encoder Reranking
        if self.reranker and fused_candidates:
            final_candidates = self.reranker.rerank(
                query=query,
                candidates=fused_candidates,
                top_k=rerank_top_k,
            )
        else:
            final_candidates = fused_candidates[:rerank_top_k]

        # Step 6: Similarity Threshold Calibration check (if configured)
        if similarity_threshold is not None:
            # Calibrate cutoff without discarding exact section matches
            final_candidates = [
                c for c in final_candidates
                if c.score >= similarity_threshold or c.retrieval_type == "exact"
            ]

        # Step 7: Complete Parent-Section Context Recovery (if requested)
        if expand_parent_sections and final_candidates:
            seen_sections = set()
            expanded_results: List[VectorSearchResult] = []

            for cand in final_candidates:
                sec_key = f"{cand.chunk.act_id}:{cand.chunk.section}"
                if sec_key in seen_sections:
                    expanded_results.append(cand)
                    continue

                seen_sections.add(sec_key)
                family_chunks = self.vector_store.get_parent_section_chunks(cand.chunk)

                if len(family_chunks) > 1:
                    # Combine all sibling subsections in order
                    combined_text_parts = [c.text for c in family_chunks]
                    unified_chunk = cand.chunk.model_copy()
                    unified_chunk.text = "\n---\n".join(combined_text_parts)
                    expanded_results.append(
                        VectorSearchResult(
                            chunk=unified_chunk,
                            score=cand.score,
                            retrieval_type=f"{cand.retrieval_type}+parent_expanded",
                        )
                    )
                else:
                    expanded_results.append(cand)

            return expanded_results

        return final_candidates
