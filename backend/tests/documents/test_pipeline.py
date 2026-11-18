"""Comprehensive tests for Phase 3 Document Processing Pipeline & OCR Engine."""

import io
from uuid import uuid4
import fitz
from PIL import Image
import pytest
from backend.src.documents.ocr import OCREngine
from backend.src.documents.pipeline import DocumentProcessingPipeline
from backend.src.documents.schemas import DocumentStatus, ExtractionMethod, QualityFlag


@pytest.fixture
def sample_pdf_bytes():
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text(
        (50, 50),
        "SPECIAL POWER OF ATTORNEY\nKnown all men by these presents that I, Md. Rafiqul Islam, appoint my advocate...",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def sample_image_bytes():
    img = Image.new("RGB", (200, 100), color="white")
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def test_ocr_image_preprocessing(sample_image_bytes):
    processed = OCREngine.preprocess_image(sample_image_bytes)
    assert processed.mode == "L"
    assert processed.size == (200, 100)


def test_ocr_engine_fallback(sample_image_bytes):
    ocr = OCREngine(confidence_threshold=0.7)
    text, conf, flag = ocr.extract_from_image(sample_image_bytes)
    assert conf >= 0.0
    assert flag in (QualityFlag.GOOD, QualityFlag.NEEDS_REVIEW)


def test_full_pipeline_with_pdf(sample_pdf_bytes):
    pipeline = DocumentProcessingPipeline()
    case_id = uuid4()
    meta, pages, chunks = pipeline.process_document(
        file_bytes=sample_pdf_bytes,
        filename="power_of_attorney.pdf",
        case_id=case_id,
    )

    assert meta.case_id == case_id
    assert meta.original_filename == "power_of_attorney.pdf"
    assert meta.total_pages == 1
    assert meta.status in (DocumentStatus.READY, DocumentStatus.NEEDS_REVIEW)

    assert len(pages) == 1
    assert "POWER OF ATTORNEY" in pages[0].text
    assert pages[0].page_number == 1

    assert len(chunks) >= 1
    assert chunks[0].page_number == 1
    assert chunks[0].case_id == case_id


def test_full_pipeline_with_image(sample_image_bytes):
    pipeline = DocumentProcessingPipeline()
    case_id = uuid4()
    meta, pages, chunks = pipeline.process_document(
        file_bytes=sample_image_bytes,
        filename="evidence_receipt.png",
        case_id=case_id,
    )

    assert meta.mime_type == "image/png"
    assert len(pages) == 1
    assert pages[0].source_method == ExtractionMethod.OCR
    assert len(chunks) == 1
