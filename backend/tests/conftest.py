import os
import secrets
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from psycopg2 import connect
from sqlalchemy.engine import make_url

from app.config import Settings
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_ORIGIN = "http://localhost:3000"

load_dotenv(BACKEND_DIR / ".env")
# Tests never reach external providers and never see provider keys, whatever .env says.
for _secret in ("GEMINI_API_KEY",):
    os.environ.pop(_secret, None)
os.environ["LLM_PROVIDER"] = "mock"
os.environ["LLM_APPROVED_PROVIDERS"] = "mock"
# The suite runs with TEST_EMBEDDING_PROVIDER (default e5_small_onnx, the product default;
# legal_copilot_test must be embedded with that model). TEST_EMBEDDING_PROVIDER=hf_api runs
# the hf_api code path; its HTTP call never leaves the machine: _mock_hf_api answers it.
os.environ["EMBEDDING_PROVIDER"] = os.environ.get("TEST_EMBEDDING_PROVIDER", "e5_small_onnx")
if os.environ["EMBEDDING_PROVIDER"] == "hf_api":
    os.environ["HF_API_TOKEN"] = "hf_mock_token_for_tests"


def _hf_api_mock_transport():
    """Answers feature-extraction like the HF API: token-level e5-large vectors.

    Uses the local model when the `ml` group is installed, so recall tests keep
    real vectors; otherwise a deterministic hash vector (enough for unit paths).
    """
    import hashlib
    import json

    import httpx

    from app.rag.ingest.chunking import EMBEDDING_MODEL, MAX_TOKENS

    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
        model.max_seq_length = MAX_TOKENS
    except ImportError:
        model = None

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "router.huggingface.co"
        text = json.loads(request.content)["inputs"]
        if model is not None:
            tokens = model.encode([text], output_value="token_embeddings", convert_to_numpy=False,
                                  show_progress_bar=False)[0]
            return httpx.Response(200, json=[tokens.float().tolist()])
        digest = hashlib.sha256(text.encode()).digest()
        return httpx.Response(200, json=[[(digest[i % 32] - 127.5) / 128 for i in range(1024)]])

    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True, scope="session")
def _mock_hf_api():
    if os.environ.get("EMBEDDING_PROVIDER") != "hf_api":
        yield
        return
    from app.rag.search import providers

    mock = _hf_api_mock_transport()
    original = providers.HFApiQueryEmbedder.__init__

    def patched(self, token, timeout=30.0, transport=None, retry_wait=2.0):
        original(self, token, timeout, transport or mock, retry_wait)

    providers.HFApiQueryEmbedder.__init__ = patched
    providers.get_query_embedder.cache_clear()
    try:
        yield
    finally:
        providers.HFApiQueryEmbedder.__init__ = original
        providers.get_query_embedder.cache_clear()


@pytest.fixture
def local_app_user_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    url = make_url(database_url)
    if (
        url.drivername != "postgresql+asyncpg"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or url.username != "app_user"
        or url.database not in {"legal_copilot", "legal_copilot_test"}
        or not url.password
    ):
        pytest.fail(
            "TEST_DATABASE_URL must target the local Compose database as app_user"
        )
    return database_url


@pytest.fixture(autouse=True, scope="function")
def _clear_login_rate_limits():
    """Clear the IP-based login rate limit table before each test so tests
    running through Starlette TestClient (all from the same host) do not
    exhaust the per-IP attempt counter."""
    with connect(
        host="localhost", port=5433, user="postgres",
        password="local-development-placeholder", dbname="legal_copilot_test"
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.auth_login_ip_limits")
        conn.commit()
    yield


@pytest.fixture
def api_client(local_app_user_database_url: str):
    app = create_app(
        Settings(
            app_env="test",
            database_url=local_app_user_database_url,
            app_origin=APP_ORIGIN,
            session_cookie_secure=True,
            minio_bucket=os.getenv("TEST_MINIO_BUCKET") or None,
            # Tests never call external providers, whatever backend/.env says.
            llm_provider="mock",
            llm_approved_providers="mock",
        )
    )
    client = TestClient(
        app,
        base_url="https://testserver",
    )
    with client:
        yield client
