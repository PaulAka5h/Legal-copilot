"""Embedding service module for PokkhoAI RAG.

Supports:
1. MockEmbeddingProvider: Deterministic embeddings for fast unit tests without GPU/network.
2. SentenceTransformersEmbeddingProvider: Multilingual sentence embeddings using
   'intfloat/multilingual-e5-large' (1024-dimension, normalized).
   Strict requirement:
   - Document prefix: "passage: "
   - Query prefix: "query: "
   - Input token truncation safety (max 512 tokens).
"""

from abc import ABC, abstractmethod
import hashlib
from typing import List, Union
import numpy as np


class BaseEmbeddingProvider(ABC):
    """Abstract embedding provider interface."""

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Compute normalized vector embeddings for documents/passages (e.g. prefix 'passage: ')."""
        pass

    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """Compute normalized vector embedding for a single user query (e.g. prefix 'query: ')."""
        pass

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Backward-compatible alias for embed_documents."""
        return self.embed_documents(texts)

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimension."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the embedding model."""
        pass


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic mock embedding provider for tests and offline development."""

    def __init__(self, dimension: int = 1024, model_name: str = "mock-multilingual-e5"):
        self._dim = dimension
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return self._model_name

    def _generate_vector(self, text: str) -> List[float]:
        seed = int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)
        vec = rng.randn(self._dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._generate_vector(f"passage: {t}") for t in texts]

    def embed_query(self, query: str) -> List[float]:
        return self._generate_vector(f"query: {query}")


class SentenceTransformersEmbeddingProvider(BaseEmbeddingProvider):
    """Production multilingual embedding provider using intfloat/multilingual-e5-large."""

    DEFAULT_MODEL = "intfloat/multilingual-e5-large"

    def __init__(self, model_name: str = DEFAULT_MODEL, max_seq_length: int = 512):
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name
        self._max_seq_length = max_seq_length
        self._model = SentenceTransformer(model_name)
        if hasattr(self._model, "max_seq_length"):
            self._model.max_seq_length = max_seq_length
        self._dim = self._model.get_sentence_embedding_dimension()

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # Enforce "passage: " prefix for asymmetric E5 models
        prefix = "passage: " if "e5" in self._model_name.lower() else ""
        prefixed_texts = [f"{prefix}{t}" for t in texts]

        embeddings = self._model.encode(
            prefixed_texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        # Enforce "query: " prefix for asymmetric E5 models
        prefix = "query: " if "e5" in self._model_name.lower() else ""
        prefixed_query = f"{prefix}{query}"

        embedding = self._model.encode(
            [prefixed_query],
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return embedding[0].tolist()
