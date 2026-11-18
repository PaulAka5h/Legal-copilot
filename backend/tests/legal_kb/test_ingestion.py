"""Tests for Legal KB chunking and ingestion service."""

from pathlib import Path
import pytest
from backend.src.legal_kb.chunker import LegalChunker
from backend.src.legal_kb.schemas import LegalLanguage, ScrapedSectionRecord
from backend.src.legal_kb.service import LegalIngestionService


@pytest.fixture
def sample_english_section():
    return ScrapedSectionRecord(
        document_id="bd-act-11-sec-300-en",
        act_id="11",
        act_name="The Penal Code, 1860",
        act_number="XLV",
        act_year="1860",
        language=LegalLanguage.EN,
        chapter_number="Chapter XVI",
        chapter_title="OF OFFENCES AFFECTING THE HUMAN BODY",
        section_number="300",
        section_title="Murder",
        section_content="Except in the cases hereinafter excepted, culpable homicide is murder, if the act by which the death is caused is done with the intention of causing death.",
        subsections=[
            {"clause": "Exception 1", "content": "When culpable homicide is not murder under grave and sudden provocation."}
        ],
        source_url="https://bdlaws.minlaw.gov.bd/act-11/section-34500.html",
        content_hash="abc123hash",
    )


@pytest.fixture
def sample_bengali_section():
    return ScrapedSectionRecord(
        document_id="bd-act-11-sec-300-bn",
        act_id="11",
        act_name="দণ্ডবিধি, ১৮৬০",
        act_number="XLV",
        act_year="1860",
        language=LegalLanguage.BN,
        chapter_number="অধ্যায় ১৬",
        chapter_title="মানবদেহ সংক্রান্ত অপরাধ",
        section_number="৩০০",
        section_title="খুন",
        section_content="ব্যতিক্রমসমূহ ব্যতিরেকে, যখন কোন কাজের দ্বারা মৃত্যু সংঘটিত হয় এবং কাজটি মৃত্যু ঘটানোর অভিপ্রায়ে করা হয়, তখন অপরাধজনক নরহত্যা খুন বলে গণ্য হইবে।",
        subsections=[],
        source_url="https://bdlaws.minlaw.gov.bd/act-11/section-34500.html",
        content_hash="def456hash",
    )


def test_chunker_single_section(sample_english_section):
    chunker = LegalChunker(max_tokens=500)
    chunks = chunker.chunk_section(sample_english_section)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert "The Penal Code, 1860" in chunk.text
    assert "Section 300 - Murder" in chunk.text
    assert "Exception 1" in chunk.text
    assert chunk.source_url == sample_english_section.source_url
    assert chunk.chunk_index == 0


def test_chunker_bengali_support(sample_bengali_section):
    chunker = LegalChunker(max_tokens=500)
    chunks = chunker.chunk_section(sample_bengali_section)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert "দণ্ডবিধি, ১৮৬০" in chunk.text
    assert "খুন বলে গণ্য হইবে" in chunk.text
    assert chunk.metadata["language"] == "bn"


def test_chunker_splits_oversize_text(sample_english_section):
    # Set a tiny max_tokens threshold to force splitting
    chunker = LegalChunker(max_tokens=25)
    chunks = chunker.chunk_section(sample_english_section)

    assert len(chunks) > 1
    for idx, c in enumerate(chunks):
        assert c.chunk_index == idx
        assert "The Penal Code, 1860" in c.text  # Context header preserved on each chunk


def test_real_dataset_streaming():
    real_jsonl = Path("/home/arafath/ai-builders/Legal-copilot/data-scrapper/data/processed/sections.jsonl")
    if not real_jsonl.exists():
        pytest.skip("Scraped dataset file not found")

    service = LegalIngestionService()
    chunk_count = 0
    for chunk in service.process_sections_to_chunks(real_jsonl):
        chunk_count += 1
        assert chunk.text
        assert chunk.source_url.startswith("https://")
        assert chunk.token_count > 0
        if chunk_count >= 15:  # Verify first 15 chunks stream cleanly
            break

    assert chunk_count == 15
