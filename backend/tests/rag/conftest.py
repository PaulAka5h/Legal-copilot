import pytest


@pytest.fixture(scope="session")
def counter():
    try:
        from app.rag.ingest.chunking import load_counter

        return load_counter()
    except Exception as error:  # tokenizer files not cached and no network
        pytest.skip(f"e5 tokenizer unavailable: {type(error).__name__}")
