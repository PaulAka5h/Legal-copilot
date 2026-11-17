"""Comprehensive tests for Hybrid Retrieval, Exact Section Search, RRF, and Citation Verification."""

from pathlib import Path
import pytest
from backend.src.legal_kb.benchmark_data import BENCHMARK_DATASET
from backend.src.legal_kb.chunker import LegalChunker
from backend.src.legal_kb.embeddings import MockEmbeddingProvider
from backend.src.legal_kb.normalizer import extract_section_numbers, normalize_to_bn_digits, normalize_to_en_digits
from backend.src.legal_kb.prompts import LegalCitationVerifier, build_legal_rag_prompt
from backend.src.legal_kb.reranker import MockReranker
from backend.src.legal_kb.retriever import LegalHybridRetriever
from backend.src.legal_kb.schemas import LegalChunkPayload, LegalLanguage, ScrapedSectionRecord
from backend.src.legal_kb.vector_store import InMemoryVectorStore


@pytest.fixture
def populated_vector_store():
    store = InMemoryVectorStore()
    embedding_provider = MockEmbeddingProvider(dimension=128)

    sample_sections = [
        ScrapedSectionRecord(
            document_id="penal-300",
            act_id="11",
            act_name="The Penal Code, 1860",
            language=LegalLanguage.EN,
            section_number="300",
            section_title="Murder",
            section_content="Except in the cases hereinafter excepted, culpable homicide is murder, if the act by which the death is caused is done with the intention of causing death.",
            subsections=[{"clause": "Exception 1", "content": "Grave and sudden provocation."}],
            source_url="https://bdlaws.minlaw.gov.bd/act-11/section-300.html",
            content_hash="h300",
        ),
        ScrapedSectionRecord(
            document_id="penal-302",
            act_id="11",
            act_name="The Penal Code, 1860",
            language=LegalLanguage.EN,
            section_number="302",
            section_title="Punishment for murder",
            section_content="Whoever commits murder shall be punished with death, or imprisonment for life, and shall also be liable to fine.",
            subsections=[],
            source_url="https://bdlaws.minlaw.gov.bd/act-11/section-302.html",
            content_hash="h302",
        ),
        ScrapedSectionRecord(
            document_id="ni-138",
            act_id="25",
            act_name="The Negotiable Instruments Act, 1881",
            language=LegalLanguage.EN,
            section_number="138",
            section_title="Dishonour of cheque for insufficiency, etc., of funds in the account",
            section_content="Where any cheque drawn by a person on an account maintained by him with a banker for payment of any amount of money to another person from out of that account is returned by the bank unpaid...",
            subsections=[],
            source_url="https://bdlaws.minlaw.gov.bd/act-25/section-138.html",
            content_hash="h138",
        ),
        ScrapedSectionRecord(
            document_id="penal-302-bn",
            act_id="11",
            act_name="দণ্ডবিধি, ১৮৬০",
            language=LegalLanguage.BN,
            section_number="৩০২",
            section_title="খুনের শাস্তি",
            section_content="যাবজ্জীবন কারাদণ্ড অথবা মৃত্যুদণ্ড এবং অর্থদণ্ডে দণ্ডিত হইবে।",
            subsections=[],
            source_url="https://bdlaws.minlaw.gov.bd/act-11/section-302.html",
            content_hash="h302bn",
        ),
    ]

    chunker = LegalChunker(max_tokens=400)
    all_chunks = []
    for s in sample_sections:
        all_chunks.extend(chunker.chunk_section(s))

    texts = [c.text for c in all_chunks]
    embeddings = embedding_provider.embed_documents(texts)
    store.add_chunks(all_chunks, embeddings)

    return store, embedding_provider


def test_digit_normalization():
    assert normalize_to_en_digits("ধারা ৩০২") == "ধারা 302"
    assert normalize_to_bn_digits("Section 302") == "Section ৩০২"

    extracted = extract_section_numbers("দণ্ডবিধির ধারা ৩০২ এর বিধান")
    assert "302" in extracted
    assert "৩০২" in extracted

    extracted_en = extract_section_numbers("Under Section 138(1)(a) of NI Act")
    assert "138" in extracted_en


def test_exact_section_retrieval(populated_vector_store):
    store, _ = populated_vector_store
    results = store.search_exact_section("302")
    assert len(results) > 0
    assert any(r.chunk.section == "302" or r.chunk.section == "৩০২" for r in results)


def test_rrf_hybrid_retriever(populated_vector_store):
    store, embedding_provider = populated_vector_store
    reranker = MockReranker()
    retriever = LegalHybridRetriever(
        vector_store=store,
        embedding_provider=embedding_provider,
        reranker=reranker,
        rrf_k=60,
    )

    query = "What is the punishment under Section 302 of the Penal Code?"
    results = retriever.retrieve(query=query, rerank_top_k=3)

    assert len(results) > 0
    top_chunk = results[0].chunk
    # Exact section match or high relevance for 302
    assert "302" in (top_chunk.section or "") or "302" in (top_chunk.provision_label or "")


def test_parent_section_expansion(populated_vector_store):
    store, embedding_provider = populated_vector_store
    retriever = LegalHybridRetriever(
        vector_store=store,
        embedding_provider=embedding_provider,
    )

    # Section 300 contains Exception 1
    query = "What is murder under Section 300?"
    results = retriever.retrieve(query=query, rerank_top_k=2, expand_parent_sections=True)

    assert len(results) > 0
    assert any("300" in (r.chunk.section or "") for r in results)


def test_citation_verifier(populated_vector_store):
    store, _ = populated_vector_store
    chunks = store._chunks

    valid, msg = LegalCitationVerifier.verify_citation(
        citation_act="The Penal Code, 1860",
        citation_section="302",
        retrieved_chunks=chunks,
    )
    assert valid is True

    # Test fabricated citation rejection
    invalid, msg = LegalCitationVerifier.verify_citation(
        citation_act="The French Commercial Code",
        citation_section="999",
        retrieved_chunks=chunks,
    )
    assert invalid is False


def test_prompt_generation_with_insufficient_evidence():
    prompt = build_legal_rag_prompt("Some fictional query", retrieved_results=[])
    assert "INSUFFICIENT EVIDENCE" in prompt
