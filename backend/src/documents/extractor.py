"""Digital Text Extraction Engine for Legal Documents (TRD Section 5.2).

Extracts:
1. Digital PDFs page-by-page using PyMuPDF (fitz), preserving exact physical page numbers.
2. Character counts, word counts, and language detection (Bengali vs English).
3. Fallback routing: identifies sparse or image-only scanned pages for downstream OCR.
4. Word (.docx) documents preserving headings, paragraphs, and tables using python-docx.
"""

import io
import re
from typing import List, Tuple
from uuid import UUID
import docx
import fitz  # PyMuPDF
from backend.src.documents.schemas import ExtractedPage, ExtractionMethod, QualityFlag


class DigitalTextExtractor:
    """High-performance text extractor for case legal documents."""

    MIN_TEXT_CHARS_PER_PAGE = 40  # If page text is under 40 characters, flag for OCR review

    @staticmethod
    def detect_language(text: str) -> str:
        """Determines whether text is primarily Bengali, English, or Mixed."""
        bengali_chars = len(re.findall(r"[\u0980-\u09FF]", text))
        english_chars = len(re.findall(r"[a-zA-Z]", text))

        if bengali_chars > 0 and english_chars > 0:
            return "mixed"
        elif bengali_chars > 0:
            return "bn"
        return "en"

    @classmethod
    def extract_pdf(cls, file_bytes: bytes, document_id: UUID) -> List[ExtractedPage]:
        """Extracts text page-by-page from digital PDFs using PyMuPDF."""
        extracted_pages: List[ExtractedPage] = []

        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page_idx, page in enumerate(doc, start=1):
                raw_text = page.get_text("text").strip()
                char_count = len(raw_text)
                word_count = len(raw_text.split())

                # Check if page has embedded raster images (potential scanned page or stamped page)
                images = page.get_images()
                has_images = len(images) > 0

                # Determine quality flag & method
                if char_count < cls.MIN_TEXT_CHARS_PER_PAGE:
                    quality = QualityFlag.NEEDS_REVIEW
                    source_method = ExtractionMethod.TEXT_LAYER
                else:
                    quality = QualityFlag.GOOD
                    source_method = ExtractionMethod.TEXT_LAYER

                lang = cls.detect_language(raw_text)

                extracted_pages.append(
                    ExtractedPage(
                        document_id=document_id,
                        page_number=page_idx,
                        text=raw_text,
                        source_method=source_method,
                        ocr_confidence=1.0 if quality == QualityFlag.GOOD else 0.5,
                        quality_flag=quality,
                        language=lang,
                        char_count=char_count,
                        word_count=word_count,
                        has_images=has_images,
                    )
                )

        return extracted_pages

    @classmethod
    def extract_docx(cls, file_bytes: bytes, document_id: UUID) -> List[ExtractedPage]:
        """Extracts text from Word .docx documents preserving paragraphs and tables."""
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = []

        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                paragraphs.append(text)

        # Also extract text from any tables in the document
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)

        full_text = "\n\n".join(paragraphs)
        char_count = len(full_text)
        word_count = len(full_text.split())
        lang = cls.detect_language(full_text)

        # Word documents are mapped to a single unified page 1 (or logical pages)
        return [
            ExtractedPage(
                document_id=document_id,
                page_number=1,
                text=full_text,
                source_method=ExtractionMethod.DOCX_PARSER,
                ocr_confidence=1.0,
                quality_flag=QualityFlag.GOOD if char_count > 0 else QualityFlag.NEEDS_REVIEW,
                language=lang,
                char_count=char_count,
                word_count=word_count,
                has_images=False,
            )
        ]
