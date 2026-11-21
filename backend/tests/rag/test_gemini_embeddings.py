"""EMBEDDING_PROVIDER=gemini: request shape, normalization, batching, retries, gating,
the provider-aware analysis threshold, and the embedding-model mismatch guard.

No network: the Gemini API is replaced by httpx.MockTransport.
"""

import asyncio
import json
import math
import unicodedata

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import DEFAULT_MIN_SIMILARITY, Settings
from app.main import create_app
from app.rag.ingest.chunking import EMBEDDING_MODEL, EMBEDDING_VERSION
from app.rag.search.errors import EmbeddingModelMismatch, EmbeddingUnavailable, ProviderNotConfigured
from app.rag.search.gemini_embeddings import (
    GEMINI_BATCH_MAX,
    GEMINI_DIM,
    GEMINI_EMBEDDING_VERSION,
    GeminiDocumentEmbedder,
    GeminiEmbeddingClient,
    GeminiEmbeddingError,
    GeminiQueryEmbedder,
)
from app.rag.search.providers import build_query_embedder, embedding_target
from app.rag.search.retrieval import check_embedding_model

KEY = "gm_test_key"


def _values(seed: float) -> list[float]:
    return [seed * 0.01 + i / (GEMINI_DIM * 3) for i in range(GEMINI_DIM)]


def _ok(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    return httpx.Response(200, json={"embeddings": [{"values": _values(i + 1)} for i in range(len(body["requests"]))]})


def _client(handler, sleeps=None, **kwargs) -> GeminiEmbeddingClient:
    record = sleeps.append if sleeps is not None else (lambda s: None)
    return GeminiEmbeddingClient(KEY, "gemini-embedding-001", transport=httpx.MockTransport(handler),
                                 sleep=record, **kwargs)


def _norm(v):
    return math.sqrt(sum(x * x for x in v))


# ---------------------------------------------------------------- request shape
@pytest.mark.parametrize(("embedder_cls", "task"), [(GeminiQueryEmbedder, "RETRIEVAL_QUERY"),
                                                    (GeminiDocumentEmbedder, "RETRIEVAL_DOCUMENT")])
def test_request_uses_task_type_dimension_nfc_and_key_header(embedder_cls, task):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(url=str(request.url), key=request.headers.get("x-goog-api-key"),
                    auth=request.headers.get("authorization"), body=json.loads(request.content))
        return _ok(request)

    decomposed = unicodedata.normalize("NFD", "চেক ডিসঅনার")
    embedder = embedder_cls(_client(handler))
    vector = embedder.embed_query(decomposed) if task == "RETRIEVAL_QUERY" else embedder.embed([decomposed])[0]
    assert seen["url"].endswith("/v1beta/models/gemini-embedding-001:batchEmbedContents")
    assert seen["key"] == KEY and seen["auth"] is None and KEY not in seen["url"]
    (req,) = seen["body"]["requests"]
    assert req["model"] == "models/gemini-embedding-001"
    assert req["taskType"] == task and req["outputDimensionality"] == 1024
    text = req["content"]["parts"][0]["text"]
    assert text == unicodedata.normalize("NFC", decomposed)  # NFC, and no e5 "query: "/"passage: " prefix
    assert len(vector) == GEMINI_DIM


def test_truncated_vectors_are_l2_normalized():
    raw = _values(1)
    assert _norm(raw) != pytest.approx(1.0)
    (vector,) = _client(_ok).embed(["x"], "RETRIEVAL_DOCUMENT")
    assert _norm(vector) == pytest.approx(1.0)
    assert vector[7] == pytest.approx(raw[7] / _norm(raw))


def test_large_inputs_are_batched_in_order():
    sizes = []

    def handler(request: httpx.Request) -> httpx.Response:
        texts = [r["content"]["parts"][0]["text"] for r in json.loads(request.content)["requests"]]
        sizes.append(len(texts))
        return httpx.Response(200, json={"embeddings": [{"values": _values(int(t))} for t in texts]})

    texts = [str(i) for i in range(2 * GEMINI_BATCH_MAX + 30)]
    vectors = _client(handler).embed(texts, "RETRIEVAL_DOCUMENT")
    assert sizes == [GEMINI_BATCH_MAX, GEMINI_BATCH_MAX, 30]
    expected = _values(137)
    assert vectors[137][0] == pytest.approx(expected[0] / _norm(expected))


@pytest.mark.parametrize("payload", [
    {"embeddings": [{"values": [0.1] * 768}]},  # wrong dimension
    {"embeddings": [{"values": [0.0] * GEMINI_DIM}]},  # zero vector
    {"embeddings": []},  # count mismatch
    {"error": "x"},
])
def test_bad_payloads_raise(payload):
    with pytest.raises(GeminiEmbeddingError):
        _client(lambda r: httpx.Response(200, json=payload)).embed(["x"], "RETRIEVAL_QUERY")


# ---------------------------------------------------------------- retries
def test_429_is_retried_with_server_delay_then_backoff():
    calls, sleeps = [], []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": {"code": 429, "details": [
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "17s"}]}})
        if len(calls) == 2:
            return httpx.Response(503, json={"error": {"code": 503}})
        return _ok(request)

    assert len(_client(handler, sleeps, backoff=1.0, attempts=4).embed(["x"], "RETRIEVAL_QUERY")) == 1
    assert sleeps == [17.0, 2.0]  # server's RetryInfo, then exponential backoff (1, 2, 4 ...)


def test_wait_is_capped_and_attempts_are_bounded():
    sleeps = []
    handler = lambda r: httpx.Response(429, headers={"retry-after": "300"}, json={})  # noqa: E731
    with pytest.raises(GeminiEmbeddingError, match="429"):
        _client(handler, sleeps, attempts=3, max_wait=4.0).embed(["x"], "RETRIEVAL_QUERY")
    assert sleeps == [4.0, 4.0]


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_not_retried(status):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(status, json={"error": {"message": f"bad key {KEY} for secret facts"}})

    with pytest.raises(GeminiEmbeddingError) as error:
        _client(handler).embed(["secret facts"], "RETRIEVAL_QUERY")
    assert len(calls) == 1
    assert KEY not in str(error.value) and "secret" not in str(error.value)


def test_gemini_failure_is_a_503_problem():
    assert issubclass(GeminiEmbeddingError, EmbeddingUnavailable)


# ---------------------------------------------------------------- selection and gating
def test_gemini_is_selected_with_a_key_and_model_from_settings():
    settings = Settings(_env_file=None, embedding_provider="gemini", gemini_api_key="k",
                        gemini_embedding_model="gemini-embedding-002")
    embedder = build_query_embedder(settings)
    assert isinstance(embedder, GeminiQueryEmbedder)
    assert (embedder.model_name, embedder.embedding_version) == ("gemini-embedding-002", GEMINI_EMBEDDING_VERSION)


def test_gemini_without_key_is_not_configured(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ProviderNotConfigured, match="GEMINI_API_KEY"):
        build_query_embedder(Settings(_env_file=None, embedding_provider="gemini"))


def test_gemini_is_refused_in_production():
    settings = Settings(_env_file=None, app_env="production", embedding_provider="gemini", gemini_api_key="k")
    with pytest.raises(ProviderNotConfigured, match="production"):
        build_query_embedder(settings)


def test_model_name_must_be_bare():
    with pytest.raises(ValueError):
        GeminiEmbeddingClient(KEY, "../models/x?key=1")


def test_embedding_target_per_provider():
    hf = embedding_target(Settings(_env_file=None, embedding_provider="hf_api"))
    assert (hf.model, hf.version) == (EMBEDDING_MODEL, EMBEDDING_VERSION)  # same e5 vectors as local
    local = embedding_target(Settings(_env_file=None, embedding_provider="local"))
    assert (local.model, local.version) == (EMBEDDING_MODEL, EMBEDDING_VERSION)
    gemini = embedding_target(Settings(_env_file=None, embedding_provider="gemini"))
    assert (gemini.model, gemini.version) == ("gemini-embedding-001", GEMINI_EMBEDDING_VERSION)


def test_analysis_threshold_follows_provider_unless_set(monkeypatch):
    monkeypatch.delenv("ANALYSIS_MIN_SIMILARITY", raising=False)
    for provider in ("local", "hf_api", "gemini"):
        settings = Settings(_env_file=None, embedding_provider=provider)
        assert settings.analysis_similarity_threshold == DEFAULT_MIN_SIMILARITY[provider]
    assert Settings(_env_file=None, embedding_provider="gemini",
                    analysis_min_similarity=0.5).analysis_similarity_threshold == 0.5


# ---------------------------------------------------------------- mismatch guard
class _Embedder:
    model_name, embedding_version = "gemini-embedding-001", 1


class _Session:
    def __init__(self, stored):
        self.stored = stored

    async def execute(self, statement, params):
        return list(self.stored)


@pytest.mark.parametrize("stored", [[], [("gemini-embedding-001", 1)]])
def test_matching_or_empty_knowledge_base_passes(stored):
    asyncio.run(check_embedding_model(_Session(stored), _Embedder(), ["v"]))


@pytest.mark.parametrize("stored", [
    [(EMBEDDING_MODEL, 1)],  # whole KB on e5
    [(EMBEDDING_MODEL, 1), ("gemini-embedding-001", 1)],  # half re-embedded
    [("gemini-embedding-001", 2)],  # same model, other recipe version
])
def test_mismatch_is_refused(stored):
    with pytest.raises(EmbeddingModelMismatch) as error:
        asyncio.run(check_embedding_model(_Session(stored), _Embedder(), ["v"]))
    assert "gemini-embedding-001 v1" in str(error.value)


def test_mismatch_is_a_clear_503_problem():
    app = create_app(Settings(_env_file=None, app_env="test"))

    @app.get("/_mismatch")
    def boom() -> None:
        raise EmbeddingModelMismatch("gemini-embedding-001", 1, [(EMBEDDING_MODEL, 1)])

    response = TestClient(app, raise_server_exceptions=False).get("/_mismatch")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    detail = response.json()["detail"]
    assert detail.startswith("EMBEDDING_MODEL_MISMATCH") and EMBEDDING_MODEL in detail


def test_bulk_client_paces_texts_per_minute():
    """Free tier counts every text as a request (100/min); bulk embedding must stay under it."""
    now, sends = [0.0], []

    def sleep(seconds):
        now[0] += seconds

    def handler(request):
        sends.append((now[0], len(json.loads(request.content)["requests"])))
        return _ok(request)

    client = GeminiEmbeddingClient(KEY, "gemini-embedding-001", transport=httpx.MockTransport(handler),
                                   sleep=sleep, clock=lambda: now[0], texts_per_minute=90)
    for _ in range(5):
        client.embed(["x"] * 30, "RETRIEVAL_DOCUMENT")
    for t, _ in sends:  # no 60-second window ever holds more than 90 texts
        assert sum(n for u, n in sends if t - 60 < u <= t) <= 90
    assert [round(t) for t, _ in sends] == [0, 0, 0, 60, 60]  # 60.5 s: the first window expires


def test_pacing_caps_the_batch_size():
    sizes = []

    def handler(request):
        sizes.append(len(json.loads(request.content)["requests"]))
        return _ok(request)

    now = [0.0]
    client = GeminiEmbeddingClient(KEY, "gemini-embedding-001", transport=httpx.MockTransport(handler),
                                   sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0],
                                   texts_per_minute=40)
    client.embed(["x"] * 100, "RETRIEVAL_DOCUMENT")
    assert sizes == [40, 40, 20]
