"""Reranker module for multilingual legal candidate reranking.

Supports:
1. BaseReranker (Abstract interface)
2. MockReranker (Heuristic-based deterministic scoring for tests)
3. CrossEncoderReranker (Using 'BAAI/bge-reranker-v2-m3')
"""

from abc import ABC, abstractmethod
from typing import List, Tuple
from backend.src.legal_kb.vector_store import VectorSearchResult


class BaseReranker(ABC):
    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: List[VectorSearchResult],
        top_k: int = 5,
    ) -> List[VectorSearchResult]:
        """Reranks candidate search results against the query and returns top-k."""
        pass


class MockReranker(BaseReranker):
    """Deterministic mock reranker for unit testing and offline development."""

    def rerank(
        self,
        query: str,
        candidates: List[VectorSearchResult],
        top_k: int = 5,
    ) -> List[VectorSearchResult]:
        if not candidates:
            return []

        # Score based on keyword overlap + existing fusion score
        query_words = set(query.lower().split())
        scored = []
        for c in candidates:
            chunk_words = set(c.chunk.text.lower().split())
            overlap = len(query_words.intersection(chunk_words))
            # New score combines semantic fusion score + keyword boost
            boosted_score = c.score + (overlap * 0.1)
            scored.append((c, boosted_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for cand, new_score in scored[:top_k]:
            cand.score = new_score
            results.append(cand)
        return results


class CrossEncoderReranker(BaseReranker):
    """Production cross-encoder reranker using 'BAAI/bge-reranker-v2-m3'."""

    DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"

    def __init__(self, model_name: str = DEFAULT_MODEL):
        from sentence_transformers import CrossEncoder

        self.model_name = model_name
        self.model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        candidates: List[VectorSearchResult],
        top_k: int = 5,
    ) -> List[VectorSearchResult]:
        if not candidates:
            return []

        pairs = [[query, c.chunk.text] for c in candidates]
        scores = self.model.predict(pairs)

        ranked_pairs = list(zip(candidates, scores))
        ranked_pairs.sort(key=lambda x: x[1], reverse=True)

        results: List[VectorSearchResult] = []
        for cand, score in ranked_pairs[:top_k]:
            cand.score = float(score)
            results.append(cand)
        return results
