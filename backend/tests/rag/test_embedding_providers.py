"""EMBEDDING_PROVIDER=local|hf_api: request shape, pooling, errors, gating, lazy imports.

No network: the Hugging Face API is replaced by httpx.MockTransport.
"""

import json
import math
import os
import subprocess
import sys
import unicodedata
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.rag.search import providers
from app.rag.search.providers import (
    EMBEDDING_DIM,
    HF_FEATURE_EXTRACTION_URL,
    EmbeddingUnavailable,
    HFApiQueryEmbedder,
    ProviderNotConfigured,
    build_query_embedder,
    pooled_vector,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _vec(seed: float) -> list[float]:
    return [seed + i / EMBEDDING_DIM for i in range(EMBEDDING_DIM)]


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _embedder(handler, **kwargs) -> HFApiQueryEmbedder:
    return HFApiQueryEmbedder("hf_test_token", transport=httpx.MockTransport(handler), retry_wait=0, **kwargs)


# ---------------------------------------------------------------- pooling
@pytest.mark.parametrize(
    "payload",
    [_vec(1), [_vec(1)], [[_vec(1)]]],
    ids=["flat", "batch-of-one", "nested-batch"],
)
def test_pooled_payloads_are_normalized(payload):
    out = pooled_vector(payload)
    assert len(out) == EMBEDDING_DIM
    assert _norm(out) == pytest.approx(1.0)
    expected = _vec(1)
    assert out[5] == pytest.approx(expected[5] / _norm(expected))


@pytest.mark.parametrize("wrap", [False, True], ids=["tokens", "batch-of-tokens"])
def test_token_level_payload_is_mean_pooled(wrap):
    tokens = [_vec(1), _vec(3)]
    out = pooled_vector([tokens] if wrap else tokens)
    mean = _vec(2)
    assert out[0] == pytest.approx(mean[0] / _norm(mean))
    assert _norm(out) == pytest.approx(1.0)


@pytest.mark.parametrize("payload", [[1.0] * 768, [[1.0] * 10, [1.0] * 10], [0.0] * EMBEDDING_DIM, {"error": "x"}, []])
def test_bad_payloads_raise(payload):
    with pytest.raises(EmbeddingUnavailable):
        pooled_vector(payload)


# ---------------------------------------------------------------- HTTP client
def test_request_uses_query_prefix_nfc_and_bearer_token():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=[_vec(1)])

    decomposed = unicodedata.normalize("NFD", "চেক ডিসঅনার")
    vector = _embedder(handler).embed_query(decomposed)
    assert seen["url"] == HF_FEATURE_EXTRACTION_URL
    assert "intfloat/multilingual-e5-large" in seen["url"]
    assert seen["auth"] == "Bearer hf_test_token"
    assert seen["body"]["inputs"] == "query: " + unicodedata.normalize("NFC", decomposed)
    assert seen["body"]["truncate"] is True
    assert len(vector) == EMBEDDING_DIM and _norm(vector) == pytest.approx(1.0)


def test_cold_start_503_is_retried():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(503, json={"error": "loading"})
        return httpx.Response(200, json=[_vec(1)])

    assert len(_embedder(handler).embed_query("cheque")) == EMBEDDING_DIM
    assert len(calls) == 3


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_not_retried_and_raise(status):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(status, json={"error": "nope"})

    with pytest.raises(EmbeddingUnavailable, match=str(status)):
        _embedder(handler).embed_query("cheque")
    assert len(calls) == 1


def test_network_error_raises_after_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(EmbeddingUnavailable, match="unreachable"):
        _embedder(handler).embed_query("cheque")


def test_error_message_never_contains_token_or_query():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad token hf_test_token for query: secret facts")

    with pytest.raises(EmbeddingUnavailable) as error:
        _embedder(handler).embed_query("secret facts")
    assert "hf_test_token" not in str(error.value) and "secret" not in str(error.value)


# ---------------------------------------------------------------- selection and gating
def test_hf_api_is_selected_with_a_token():
    settings = Settings(_env_file=None, embedding_provider="hf_api", hf_api_token="hf_x")
    assert isinstance(build_query_embedder(settings), HFApiQueryEmbedder)


def test_hf_api_without_token_is_not_configured(monkeypatch):
    monkeypatch.delenv("HF_API_TOKEN", raising=False)
    with pytest.raises(ProviderNotConfigured, match="HF_API_TOKEN"):
        build_query_embedder(Settings(_env_file=None, embedding_provider="hf_api"))


def test_hf_api_is_refused_in_production():
    settings = Settings(_env_file=None, app_env="production", embedding_provider="hf_api", hf_api_token="hf_x")
    with pytest.raises(ProviderNotConfigured, match="production"):
        build_query_embedder(settings)


def test_local_without_ml_group_is_not_configured(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)  # import fails like a slim image
    with pytest.raises(ProviderNotConfigured, match="ml"):
        build_query_embedder(Settings(_env_file=None, embedding_provider="local"))


def test_default_provider_is_local(monkeypatch):
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    assert Settings(_env_file=None).embedding_provider == "local"


def test_app_import_does_not_load_torch():
    code = (
        "import sys, app.main; "
        "bad = [m for m in ('torch', 'sentence_transformers', 'transformers') if m in sys.modules]; "
        "print(bad); sys.exit(1 if bad else 0)"
    )
    env = {**os.environ, "EMBEDDING_PROVIDER": "hf_api"}
    result = subprocess.run([sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_runtime_embedding_failure_is_a_503_problem():
    app = create_app(Settings(_env_file=None, app_env="test"))

    @app.get("/_boom")
    def boom() -> None:
        raise EmbeddingUnavailable("Embedding API answered HTTP 503")

    response = TestClient(app, raise_server_exceptions=False).get("/_boom")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "NOT_CONFIGURED" in response.json()["detail"]


def test_get_query_embedder_reads_environment(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hf_api")
    monkeypatch.setenv("HF_API_TOKEN", "hf_env")
    monkeypatch.setenv("APP_ENV", "development")
    providers.get_query_embedder.cache_clear()
    try:
        assert isinstance(providers.get_query_embedder(), HFApiQueryEmbedder)
    finally:
        providers.get_query_embedder.cache_clear()


# ---------------------------------------------------------------- Neon URLs
def test_neon_libpq_url_is_translated_for_asyncpg():
    from app.database import asyncpg_url

    url = asyncpg_url(
        "postgresql+asyncpg://app_user:pw@ep-x.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    )
    assert dict(url.query) == {"ssl": "require"}
    assert dict(asyncpg_url("postgresql+asyncpg://app_user:pw@localhost/db").query) == {}
    with pytest.raises(ValueError):
        asyncpg_url("postgresql+asyncpg://app_user:pw@h/db?sslmode=bogus")


# ---------------------------------------------------------------- B2 storage
@pytest.mark.parametrize("endpoint", ["https://s3.us-west-004.backblazeb2.com", "s3.us-west-004.backblazeb2.com/bucket"])
def test_storage_endpoint_must_be_host_only(endpoint):
    from app.documents.storage import MinioStore, StorageNotConfigured

    settings = Settings(_env_file=None, minio_endpoint=endpoint, minio_access_key="k", minio_secret_key="s",
                        minio_bucket="b", minio_secure=True)
    with pytest.raises(StorageNotConfigured, match="host"):
        MinioStore(settings)


def test_b2_style_storage_settings_reach_the_client():
    from app.documents.storage import MinioStore

    settings = Settings(_env_file=None, minio_endpoint="s3.us-west-004.backblazeb2.com", minio_access_key="k",
                        minio_secret_key="s", minio_bucket="pokkho-demo", minio_secure=True,
                        minio_region="us-west-004")
    store = MinioStore(settings)
    assert store.client._base_url.is_https
    assert store.client._base_url.host == "s3.us-west-004.backblazeb2.com"
    assert store.client._base_url.region == "us-west-004"
