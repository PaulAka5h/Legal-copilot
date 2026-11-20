import os

import pytest


@pytest.fixture(scope="session")
def counter():
    try:
        from app.rag.ingest.chunking import load_counter

        return load_counter()
    except Exception as error:  # tokenizer files not cached and no network
        pytest.skip(f"e5 tokenizer unavailable: {type(error).__name__}")


@pytest.fixture
def ingest_url() -> str:
    url = os.getenv("LEGAL_INGEST_TEST_DATABASE_URL")
    if not url or not url.endswith("/legal_copilot_test"):
        pytest.skip("LEGAL_INGEST_TEST_DATABASE_URL must point at legal_copilot_test")
    return url
