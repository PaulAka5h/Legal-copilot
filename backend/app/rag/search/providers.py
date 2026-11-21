"""Query embedder and reranker providers for legal search.

EMBEDDING_PROVIDER selects the query embedder:
- `local` (default): intfloat/multilingual-e5-large via sentence-transformers on
  this server. Needs the optional `ml` dependency group (torch).
- `hf_api`: the same e5 model on the Hugging Face Inference API (hf-inference
  provider); same vectors as `local`.
- `gemini`: GEMINI_EMBEDDING_MODEL (gemini-embedding-001) on the Gemini API, a
  different model: the knowledge base must be re-embedded with it
  (`python -m app.rag.embed reembed`). See gemini_embeddings.py for the recipe.
hf_api and gemini send the query text off the server, so they are approved for
synthetic demo data only and refused when APP_ENV=production (DOCS/providers.md).

Every embedder reports (model_name, embedding_version); search refuses to compare
it against chunks embedded with anything else (EmbeddingModelMismatch, 503).

Each provider is created once per process. The reranker defaults to `mock`, which
keeps the fused order; RERANKER_PROVIDER=bge-reranker-v2-m3 uses the cross-encoder.
"""

import math
import os
import time
from functools import lru_cache
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.config import Settings
from app.rag.ingest.chunking import EMBEDDING_MODEL, EMBEDDING_VERSION, MAX_TOKENS
from app.rag.search.errors import EmbeddingModelMismatch, EmbeddingUnavailable, ProviderNotConfigured
from app.rag.search.gemini_embeddings import GEMINI_EMBEDDING_VERSION, GeminiEmbeddingClient, GeminiQueryEmbedder
from app.rag.text import nfc

QUERY_PREFIX = "query: "
EMBEDDING_DIM = 1024
EMBEDDING_PROVIDERS = ("local", "hf_api", "gemini")
OFF_SERVER_PROVIDERS = ("hf_api", "gemini")
HF_FEATURE_EXTRACTION_URL = (
    f"https://router.huggingface.co/hf-inference/models/{EMBEDDING_MODEL}/pipeline/feature-extraction"
)
HF_RETRY_STATUSES = {429, 502, 503, 504}  # cold start / rate limit / gateway
HF_ATTEMPTS = 3
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
RERANKER_CHOICES = ("mock", "bge-reranker-v2-m3")


__all__ = ["EmbeddingModelMismatch", "EmbeddingUnavailable", "ProviderNotConfigured"]


@dataclass(frozen=True)
class EmbeddingTarget:
    """The (model, version) that chunk vectors and query vectors must share."""

    provider: str
    model: str
    version: int


def embedding_target(settings: Settings) -> EmbeddingTarget:
    if settings.embedding_provider == "gemini":
        return EmbeddingTarget("gemini", settings.gemini_embedding_model, GEMINI_EMBEDDING_VERSION)
    return EmbeddingTarget(settings.embedding_provider, EMBEDDING_MODEL, EMBEDDING_VERSION)


def gemini_client(settings: Settings, **kwargs: Any) -> GeminiEmbeddingClient:
    if not settings.gemini_api_key:
        raise ProviderNotConfigured("GEMINI_API_KEY is required for EMBEDDING_PROVIDER=gemini")
    return GeminiEmbeddingClient(settings.gemini_api_key.get_secret_value(), settings.gemini_embedding_model,
                                 timeout=settings.gemini_embedding_timeout_seconds, **kwargs)


class QueryEmbedder(Protocol):
    model_name: str
    embedding_version: int

    def embed_query(self, query: str) -> list[float]: ...


class Reranker(Protocol):
    name: str

    def scores(self, query: str, passages: list[str], fused: list[float]) -> list[float]: ...


class E5QueryEmbedder:
    model_name = EMBEDDING_MODEL
    embedding_version = EMBEDDING_VERSION

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


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if not norm or not math.isfinite(norm):
        raise EmbeddingUnavailable("Embedding API returned a zero or non-finite vector")
    return [v / norm for v in vector]


def _depth(value: Any) -> int:
    depth = 0
    while isinstance(value, list) and value:
        value, depth = value[0], depth + 1
    return depth


def pooled_vector(payload: Any) -> list[float]:
    """One sentence vector from a feature-extraction response for a single input.

    Accepts [dim], [[dim]] (already pooled) or [[tokens][dim]] / [tokens][dim]
    (token level: mean-pooled; one unpadded input, so every token counts).
    Returns the L2-normalized vector.
    """
    depth = _depth(payload)
    if depth == 3 and len(payload) == 1:
        payload, depth = payload[0], 2
    if depth == 2 and len(payload) == 1:
        payload, depth = payload[0], 1
    if depth == 2:  # tokens x dim
        if any(len(row) != EMBEDDING_DIM for row in payload):
            raise EmbeddingUnavailable("Embedding API returned rows of the wrong size")
        payload = [sum(column) / len(payload) for column in zip(*payload)]
    elif depth != 1:
        raise EmbeddingUnavailable("Embedding API returned an unexpected shape")
    if len(payload) != EMBEDDING_DIM:
        raise EmbeddingUnavailable(f"Embedding API returned {len(payload)} dims, expected {EMBEDDING_DIM}")
    try:
        vector = [float(v) for v in payload]
    except (TypeError, ValueError) as error:
        raise EmbeddingUnavailable("Embedding API returned non-numeric values") from error
    return _l2_normalize(vector)


class HFApiQueryEmbedder:
    """multilingual-e5-large on the Hugging Face Inference API (feature-extraction).

    Sends "query: " + NFC(query), truncated to the model's 512 tokens like the
    local embedder, then mean-pools (if needed) and L2-normalizes. The token and
    the query text are never logged.
    """

    model_name = EMBEDDING_MODEL
    embedding_version = EMBEDDING_VERSION

    def __init__(self, token: str, timeout: float = 30.0, transport: httpx.BaseTransport | None = None,
                 retry_wait: float = 2.0) -> None:
        self._headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self._retry_wait = retry_wait

    def embed_query(self, query: str) -> list[float]:
        body = {"inputs": QUERY_PREFIX + nfc(query), "normalize": False, "truncate": True}
        for attempt in range(1, HF_ATTEMPTS + 1):
            try:
                response = self._client.post(HF_FEATURE_EXTRACTION_URL, json=body, headers=self._headers)
            except httpx.HTTPError as error:
                if attempt == HF_ATTEMPTS:
                    raise EmbeddingUnavailable(f"Embedding API unreachable: {type(error).__name__}") from error
            else:
                if response.status_code == 200:
                    try:
                        return pooled_vector(response.json())
                    except ValueError as error:
                        raise EmbeddingUnavailable("Embedding API returned invalid JSON") from error
                if response.status_code not in HF_RETRY_STATUSES or attempt == HF_ATTEMPTS:
                    raise EmbeddingUnavailable(f"Embedding API answered HTTP {response.status_code}")
            time.sleep(self._retry_wait * attempt)
        raise EmbeddingUnavailable("Embedding API failed")  # unreachable; keeps type checkers happy


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


def build_query_embedder(settings: Settings) -> QueryEmbedder:
    provider = settings.embedding_provider
    if provider in OFF_SERVER_PROVIDERS and settings.app_env == "production":
        raise ProviderNotConfigured(f"{provider} sends query text off the server; not approved in production")
    if provider == "gemini":
        # Interactive: three short tries (about 3 s), then 503 rather than a hung request.
        return GeminiQueryEmbedder(gemini_client(settings, attempts=3, backoff=1.0, max_wait=4.0))
    if provider == "hf_api":
        if not settings.hf_api_token:
            raise ProviderNotConfigured("HF_API_TOKEN is required for EMBEDDING_PROVIDER=hf_api")
        return HFApiQueryEmbedder(settings.hf_api_token.get_secret_value(), settings.hf_api_timeout_seconds)
    try:
        return E5QueryEmbedder()  # imports torch/sentence-transformers only here
    except ImportError as error:
        raise ProviderNotConfigured(
            "EMBEDDING_PROVIDER=local needs the 'ml' dependency group (uv sync --group ml); "
            "or set EMBEDDING_PROVIDER=hf_api or gemini"
        ) from error
    except Exception as error:  # ml group not installed, model files missing, out of memory
        raise ProviderNotConfigured(f"Query embedder unavailable: {type(error).__name__}") from error


@lru_cache(maxsize=1)
def get_query_embedder() -> QueryEmbedder:
    return build_query_embedder(Settings())


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
