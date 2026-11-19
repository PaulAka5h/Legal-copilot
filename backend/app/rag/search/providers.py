"""Query embedder and reranker providers for legal search.

Both are self-hosted models (no data leaves the server). Each is loaded once per
process. The reranker defaults to `mock`, which keeps the fused order; set
RERANKER_PROVIDER=bge-reranker-v2-m3 to use the cross-encoder.
"""

import os
from functools import lru_cache
from typing import Protocol

from app.rag.ingest.chunking import EMBEDDING_MODEL, MAX_TOKENS
from app.rag.text import nfc

QUERY_PREFIX = "query: "
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
RERANKER_CHOICES = ("mock", "bge-reranker-v2-m3")


class ProviderNotConfigured(RuntimeError):
    """A model could not be loaded; endpoints answer NOT_CONFIGURED."""


class QueryEmbedder(Protocol):
    model_name: str

    def embed_query(self, query: str) -> list[float]: ...


class Reranker(Protocol):
    name: str

    def scores(self, query: str, passages: list[str], fused: list[float]) -> list[float]: ...


class E5QueryEmbedder:
    model_name = EMBEDDING_MODEL

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
        self.model.max_seq_length = MAX_TOKENS

    def embed_query(self, query: str) -> list[float]:
        vector = self.model.encode(
            [QUERY_PREFIX + nfc(query)], normalize_embeddings=True, convert_to_numpy=True,
            show_progress_bar=False,
        )[0]
        return vector.astype("float32").tolist()


class MockReranker:
    """Keeps the fused (RRF) order: the score is the fused score."""

    name = "mock"

    def scores(self, query: str, passages: list[str], fused: list[float]) -> list[float]:
        return list(fused)


class CrossEncoderReranker:
    name = "bge-reranker-v2-m3"

    def __init__(self) -> None:
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(RERANKER_MODEL, device="cpu", max_length=MAX_TOKENS)

    def scores(self, query: str, passages: list[str], fused: list[float]) -> list[float]:
        if not passages:
            return []
        q = nfc(query)
        return [float(s) for s in self.model.predict([(q, nfc(p)) for p in passages], show_progress_bar=False)]


@lru_cache(maxsize=1)
def get_query_embedder() -> QueryEmbedder:
    try:
        return E5QueryEmbedder()
    except Exception as error:  # model files missing, no network, out of memory
        raise ProviderNotConfigured(f"Query embedder unavailable: {type(error).__name__}") from error


@lru_cache(maxsize=2)
def get_reranker(name: str | None = None) -> Reranker:
    name = name or os.getenv("RERANKER_PROVIDER", "mock")
    if name not in RERANKER_CHOICES:
        raise ProviderNotConfigured(f"Unknown reranker {name!r}; choose one of {RERANKER_CHOICES}")
    if name == "mock":
        return MockReranker()
    try:
        return CrossEncoderReranker()
    except Exception as error:
        raise ProviderNotConfigured(f"Reranker unavailable: {type(error).__name__}") from error
