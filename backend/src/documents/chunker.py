"""Case-Scoped Document Chunker (TRD Section 5.4).

Chunks extracted client/case pages into 300-500 token segments while:
1. NEVER crossing physical page boundaries (so every claim links to exact page_number).
2. Attaching case_id, document_id, and character offsets (char_start, char_end).
3. Supporting both Bengali and English legal text splitting.
"""

from typing import List
from uuid import UUID, uuid4
from backend.src.documents.schemas import DocumentChunk, ExtractedPage
from backend.src.legal_kb.chunker import LegalChunker


class CaseDocumentChunker:
    """Chunks case documents strictly within physical page boundaries."""

    def __init__(self, target_tokens: int = 300, max_tokens: int = 500):
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self._token_estimator = LegalChunker.estimate_tokens

    def chunk_page(self, page: ExtractedPage, case_id: UUID) -> List[DocumentChunk]:
        """Splits an ExtractedPage into one or more DocumentChunks."""
        if not page.text.strip():
            return []

        chunks: List[DocumentChunk] = []
        text = page.text
        total_tokens = self._token_estimator(text)

        # Single chunk fits on page
        if total_tokens <= self.max_tokens:
            chunks.append(
                DocumentChunk(
                    case_id=case_id,
                    document_id=page.document_id,
                    page_number=page.page_number,
                    char_start=0,
                    char_end=len(text),
                    text=text,
                    token_count=total_tokens,
                    metadata={
                        "language": page.language,
                        "source_method": page.source_method.value,
                        "quality_flag": page.quality_flag.value,
                    },
                )
            )
            return chunks

        # Split across paragraphs or sentences without crossing page boundaries
        paragraphs = text.split("\n")
        current_paras = []
        current_tokens = 0
        char_start = 0

        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                continue

            p_tokens = self._token_estimator(p_clean)

            if current_tokens + p_tokens > self.max_tokens and current_paras:
                chunk_body = "\n".join(current_paras)
                char_end = char_start + len(chunk_body)
                chunks.append(
                    DocumentChunk(
                        case_id=case_id,
                        document_id=page.document_id,
                        page_number=page.page_number,
                        char_start=char_start,
                        char_end=char_end,
                        text=chunk_body,
                        token_count=current_tokens,
                        metadata={
                            "language": page.language,
                            "source_method": page.source_method.value,
                        },
                    )
                )
                char_start = char_end + 1
                current_paras = [p_clean]
                current_tokens = p_tokens
            else:
                current_paras.append(p_clean)
                current_tokens += p_tokens

        if current_paras:
            chunk_body = "\n".join(current_paras)
            char_end = char_start + len(chunk_body)
            chunks.append(
                DocumentChunk(
                    case_id=case_id,
                    document_id=page.document_id,
                    page_number=page.page_number,
                    char_start=char_start,
                    char_end=char_end,
                    text=chunk_body,
                    token_count=current_tokens,
                    metadata={
                        "language": page.language,
                        "source_method": page.source_method.value,
                    },
                )
            )

        return chunks
