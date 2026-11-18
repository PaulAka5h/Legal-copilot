"""Integration test connecting to PostgreSQL + pgvector testing real SQL, HNSW index and FTS."""

from pathlib import Path
import psycopg
import pytest
from backend.src.legal_kb.chunker import LegalChunker
from backend.src.legal_kb.embeddings import MockEmbeddingProvider
from backend.src.legal_kb.migrations import CREATE_LEGAL_KB_TABLES_SQL
from backend.src.legal_kb.retriever import LegalHybridRetriever
from backend.src.legal_kb.schemas import LegalLanguage, ScrapedSectionRecord
from backend.src.legal_kb.vector_store import PgVectorStore

DB_URL = "postgresql://researchsphere:devpassword@localhost:5433/legal_copilot_test"


@pytest.fixture(scope="module")
def postgres_pgvector_store():
    # Attempt connection to local test database
    try:
        with psycopg.connect(DB_URL, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_LEGAL_KB_TABLES_SQL)
    except Exception as e:
        pytest.skip(f"PostgreSQL container not accessible on localhost:5433: {e}")

    store = PgVectorStore(db_url=DB_URL)
    embedding_provider = MockEmbeddingProvider(dimension=1024)

    # Seed with verified test legal chunks
    sections = [
        ScrapedSectionRecord(
            document_id="bd-act-11-sec-302-en",
            act_id="11",
            act_name="The Penal Code, 1860",
            language=LegalLanguage.EN,
            section_number="302",
            section_title="Punishment for murder",
            section_content="Whoever commits murder shall be punished with death, or imprisonment for life, and shall also be liable to fine.",
            subsections=[],
            source_url="https://bdlaws.minlaw.gov.bd/act-11/section-302.html",
            content_hash="h302-pg",
        ),
        ScrapedSectionRecord(
            document_id="bd-act-25-sec-138-en",
            act_id="25",
            act_name="The Negotiable Instruments Act, 1881",
            language=LegalLanguage.EN,
            section_number="138",
            section_title="Dishonour of cheque for insufficiency of funds",
            section_content="Where any cheque drawn by a person on an account maintained by him with a banker for payment of any amount of money is returned unpaid.",
            subsections=[],
            source_url="https://bdlaws.minlaw.gov.bd/act-25/section-138.html",
            content_hash="h138-pg",
        ),
        ScrapedSectionRecord(
            document_id="bd-act-11-sec-302-bn",
            act_id="11",
            act_name="দণ্ডবিধি, ১৮৬০",
            language=LegalLanguage.BN,
            section_number="৩০২",
            section_title="খুনের শাস্তি",
            section_content="যাবজ্জীবন কারাদণ্ড অথবা মৃত্যুদণ্ড এবং অর্থদণ্ডে দণ্ডিত হইবে।",
            subsections=[],
            source_url="https://bdlaws.minlaw.gov.bd/act-11/section-302.html",
            content_hash="h302-pg-bn",
        ),
    ]

    chunker = LegalChunker(max_tokens=400)
    all_chunks = []
    for s in sections:
        all_chunks.extend(chunker.chunk_section(s))

    embeddings = embedding_provider.embed_documents([c.text for c in all_chunks])
    store.add_chunks(all_chunks, embeddings)

    return store, embedding_provider, all_chunks


def test_pgvector_insertion_and_dense_search(postgres_pgvector_store):
    store, embedding_provider, all_chunks = postgres_pgvector_store
    # With MockEmbeddingProvider (hash-based unit vectors for test suites),
    # querying with the exact passage text guarantees cosine similarity == 1.0
    q_vec = embedding_provider.embed_documents([all_chunks[0].text])[0]
    results = store.search_dense(q_vec, top_k=2)

    assert len(results) > 0
    assert any("302" in (r.chunk.section or "") for r in results)
    assert results[0].score > 0.99


def test_pgvector_sparse_fts_search(postgres_pgvector_store):
    store, *_ = postgres_pgvector_store
    results = store.search_sparse("cheque dishonour unpaid", top_k=2)

    assert len(results) > 0
    assert any("138" in (r.chunk.section or "") for r in results)


def test_pgvector_exact_section_search(postgres_pgvector_store):
    store, *_ = postgres_pgvector_store
    results = store.search_exact_section("302")

    assert len(results) > 0
    assert any("302" in (r.chunk.section or "") for r in results)


def test_pgvector_hybrid_retriever_e2e(postgres_pgvector_store):
    store, embedding_provider, _ = postgres_pgvector_store
    retriever = LegalHybridRetriever(vector_store=store, embedding_provider=embedding_provider)

    results = retriever.retrieve("What does Section 138 say?", rerank_top_k=2)
    assert len(results) > 0
    assert any("138" in (r.chunk.section or "") for r in results)
