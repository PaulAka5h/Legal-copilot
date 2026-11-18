"""Comprehensive tests for Document Validator, Digital Text Extractor, and Case Chunker."""

import io
from uuid import uuid4
import docx
import fitz
from PIL import Image
import pypdf
import pytest
from backend.src.documents.chunker import CaseDocumentChunker
from backend.src.documents.extractor import DigitalTextExtractor
from backend.src.documents.schemas import ExtractionMethod, QualityFlag
from backend.src.documents.validator import DocumentValidationError, DocumentValidator


@pytest.fixture
def sample_pdf_bytes():
    """Generates a clean in-memory PDF with 2 pages of legal text."""
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text(
        (50, 50),
        "FIRST INFORMATION REPORT (FIR)\nPolice Station: Dhanmondi, Dhaka.\nCase No: 42/2026.\nUnder Section 420 and 406 of The Penal Code.",
    )
    page2 = doc.new_page()
    page2.insert_text(
        (50, 50),
        "WITNESS TESTIMONY AND EVIDENCE REPORT\nWitness Name: Md. Karim Ullah.\nAccused unlawfully took advance money under false business pretext.",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def sample_docx_bytes():
    """Generates a clean in-memory Word .docx file."""
    doc = docx.Document()
    doc.add_heading("LEGAL NOTICE", level=1)
    doc.add_paragraph("Whereas our client entered into an agreement dated 15th January 2026.")
    doc.add_paragraph("You are hereby demanded to refund the advance money within 15 days.")
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


@pytest.fixture
def sample_png_bytes():
    """Generates a clean 100x100 PNG image."""
    img = Image.new("RGB", (100, 100), color="white")
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def test_validator_detects_pdf_and_checks_pages(sample_pdf_bytes):
    mime = DocumentValidator.validate_file(sample_pdf_bytes, "fir_report.pdf")
    assert mime == "application/pdf"


def test_validator_rejects_empty_file():
    with pytest.raises(DocumentValidationError) as exc:
        DocumentValidator.validate_file(b"", "empty.pdf")
    assert exc.value.code == "EMPTY_FILE"


def test_validator_rejects_unsupported_format():
    with pytest.raises(DocumentValidationError) as exc:
        DocumentValidator.validate_file(b"MZ\x90\x00\x03fake_executable", "malware.exe")
    assert exc.value.code == "UNSUPPORTED_MIME_TYPE"


def test_validator_detects_docx_and_png(sample_docx_bytes, sample_png_bytes):
    mime_docx = DocumentValidator.validate_file(sample_docx_bytes, "contract.docx")
    assert "openxmlformats" in mime_docx

    mime_png = DocumentValidator.validate_file(sample_png_bytes, "scan.png")
    assert mime_png == "image/png"


def test_digital_extractor_pdf(sample_pdf_bytes):
    doc_id = uuid4()
    pages = DigitalTextExtractor.extract_pdf(sample_pdf_bytes, doc_id)

    assert len(pages) == 2
    # Page 1: English FIR
    assert pages[0].page_number == 1
    assert "FIRST INFORMATION REPORT" in pages[0].text
    assert pages[0].language == "en"
    assert pages[0].quality_flag == QualityFlag.GOOD

    # Page 2: Witness Statement
    assert pages[1].page_number == 2
    assert "WITNESS TESTIMONY" in pages[1].text


def test_digital_extractor_docx(sample_docx_bytes):
    doc_id = uuid4()
    pages = DigitalTextExtractor.extract_docx(sample_docx_bytes, doc_id)

    assert len(pages) == 1
    assert "LEGAL NOTICE" in pages[0].text
    assert pages[0].source_method == ExtractionMethod.DOCX_PARSER


def test_case_document_chunker(sample_pdf_bytes):
    doc_id = uuid4()
    case_id = uuid4()
    pages = DigitalTextExtractor.extract_pdf(sample_pdf_bytes, doc_id)

    chunker = CaseDocumentChunker(max_tokens=400)
    all_chunks = []
    for p in pages:
        all_chunks.extend(chunker.chunk_page(p, case_id=case_id))

    assert len(all_chunks) == 2
    # Ensure physical page boundaries are strictly preserved
    assert all_chunks[0].page_number == 1
    assert all_chunks[0].case_id == case_id
    assert all_chunks[0].document_id == doc_id
    assert all_chunks[1].page_number == 2
