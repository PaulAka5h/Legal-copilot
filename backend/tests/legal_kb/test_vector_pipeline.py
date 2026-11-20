"""Tests for Embedding and Vector Store pipeline."""

from pathlib import Path
import pytest
from backend.src.legal_kb.embeddings import MockEmbeddingProvider
from backend.src.legal_kb.pipeline import LegalVectorIngestionPipeline
from backend.src.legal_kb.schemas import LegalChunkPayload
from backend.src.legal_kb.vector_store import InMemoryVectorStore


def test_mock_embedding_provider():
    provider = MockEmbeddingProvider(dimension=512)
    texts = ["Section 138 of Negotiable Instruments Act", "The Penal Code section 302 murder"]
    embeddings = provider.embed_texts(texts)

    assert len(embeddings) == 2
    assert len(embeddings[0]) == 512
    # Deterministic check
    emb_repeat = provider.embed_texts(["Section 138 of Negotiable Instruments Act"])
    assert embeddings[0] == emb_repeat[0]


def test_in_memory_vector_store():
    store = InMemoryVectorStore()
    provider = MockEmbeddingProvider(dimension=128)

    c1 = LegalChunkPayload(
        provision_label="Section 138",
        chunk_index=0,
        text="Dishonour of cheque for insufficiency of funds in accounts.",
        token_count=10,
        source_url="https://bdlaws.minlaw.gov.bd/act-1/sec-138.html",
        content_hash="h1",
        metadata={"act_name": "Negotiable Instruments Act"},
    )
    c2 = LegalChunkPayload(
        provision_label="Section 300",
        chunk_index=0,
        text="Culpable homicide is murder except under specific exceptions.",
        token_count=10,
        source_url="https://bdlaws.minlaw.gov.bd/act-11/sec-300.html",
        content_hash="h2",
        metadata={"act_name": "Penal Code"},
    )

    embs = provider.embed_texts([c1.text, c2.text])
    store.add_chunks([c1, c2], embs)

    # Search with exact text
    q_emb = provider.embed_texts(["cheque dishonour funds"])[0]
    results = store.search(q_emb, top_k=2)

    assert len(results) == 2
    assert results[0].score >= results[1].score


def test_full_ingestion_pipeline_with_real_dataset():
    dataset_file = Path(__file__).resolve().parents[3] / "data-scrapper" / "data" / "processed" / "sections.jsonl"
    if not dataset_file.exists():
        pytest.skip("Scraped dataset file not found")

    vector_store = InMemoryVectorStore()
    embedding_provider = MockEmbeddingProvider(dimension=128)
    pipeline = LegalVectorIngestionPipeline(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        batch_size=10,
    )

    # Ingest 30 chunks
    ingested = pipeline.ingest_from_file(dataset_file, max_chunks=30)
    assert ingested >= 30

    # Query vector store
    q_emb = embedding_provider.embed_texts(["Penal Code section"])[0]
    results = vector_store.search(q_emb, top_k=3)
    assert len(results) == 3
    assert results[0].chunk.text
