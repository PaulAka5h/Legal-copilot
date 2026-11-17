"""Legal text chunker engine.

Chunks legal documents (sections/subsections) into target token ranges (300-600 tokens)
while respecting:
1. Section and paragraph boundaries (never splitting clauses arbitrarily).
2. Bilingual sentence markers (Bengali Dari '|', English period '.', colons, etc.).
3. Preserving citation provenance (Act, Chapter, Section label, Source URL).
"""

import re
from typing import List, Tuple
from backend.src.legal_kb.schemas import LegalChunkPayload, ScrapedSectionRecord


class LegalChunker:
    """Configurable legal text chunker."""

    def __init__(self, min_tokens: int = 50, target_tokens: int = 350, max_tokens: int = 600):
        self.min_tokens = min_tokens
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count across English and Bengali scripts.

        A word-split heuristic with 1.3x weighting reliably models multilingual BPE/WordPiece tokenizers.
        """
        if not text:
            return 0
        words = text.split()
        return max(1, int(len(words) * 1.3))

    def split_sentences(self, text: str) -> List[str]:
        """Split text by legal clause delimiters, English periods, and Bengali Dari ('|')."""
        # Matches newline blocks, Bengali Dari ('|'), or English period followed by space
        pattern = r"(?<=[।\n\.])\s+"
        parts = re.split(pattern, text)
        return [p.strip() for p in parts if p.strip()]

    def chunk_section(self, record: ScrapedSectionRecord) -> List[LegalChunkPayload]:
        """Chunks a single scraped section into one or more LegalChunkPayloads."""
        # Provision label header (e.g., "Section 138: Dishonour of Cheque")
        section_label_parts = []
        if record.section_number:
            section_label_parts.append(f"Section {record.section_number}")
        if record.section_title:
            section_label_parts.append(record.section_title)
        provision_label = " - ".join(section_label_parts) if section_label_parts else record.section_title

        # Base context prefix to ensure every chunk contains unambiguous provenance
        context_header = f"[{record.act_name}"
        if record.chapter_title:
            context_header += f" | {record.chapter_title}"
        if provision_label:
            context_header += f" | {provision_label}"
        context_header += "]\n"

        # Assemble full section body (including subsections if present)
        full_body = record.section_content.strip()
        if record.subsections:
            sub_texts = []
            for sub in record.subsections:
                clause = sub.get("clause") or ""
                content = sub.get("content") or ""
                sub_texts.append(f"{clause} {content}".strip())
            if sub_texts:
                full_body += "\n" + "\n".join(sub_texts)

        total_est_tokens = self.estimate_tokens(full_body)

        chunks: List[LegalChunkPayload] = []

        # If entire section fits within max_tokens, emit as a single coherent chunk
        if total_est_tokens <= self.max_tokens:
            chunk_text = f"{context_header}{full_body}".strip()
            chunks.append(
                LegalChunkPayload(
                    provision_label=provision_label,
                    chunk_index=0,
                    text=chunk_text,
                    token_count=self.estimate_tokens(chunk_text),
                    source_url=record.source_url,
                    content_hash=record.content_hash,
                    metadata={
                        "act_id": record.act_id,
                        "act_name": record.act_name,
                        "act_year": record.act_year,
                        "language": record.language.value,
                        "chapter_title": record.chapter_title,
                        "section_number": record.section_number,
                    },
                )
            )
            return chunks

        # Otherwise, split by clauses/sentences and accumulate chunks
        sentences = self.split_sentences(full_body)
        current_sentences: List[str] = []
        current_tokens = self.estimate_tokens(context_header)
        chunk_idx = 0

        for sentence in sentences:
            s_tokens = self.estimate_tokens(sentence)

            if current_tokens + s_tokens > self.max_tokens and current_sentences:
                # Flush current chunk
                combined_body = " ".join(current_sentences)
                chunk_text = f"{context_header}{combined_body}".strip()
                chunks.append(
                    LegalChunkPayload(
                        provision_label=provision_label,
                        chunk_index=chunk_idx,
                        text=chunk_text,
                        token_count=self.estimate_tokens(chunk_text),
                        source_url=record.source_url,
                        content_hash=record.content_hash,
                        metadata={
                            "act_id": record.act_id,
                            "act_name": record.act_name,
                            "act_year": record.act_year,
                            "language": record.language.value,
                            "chapter_title": record.chapter_title,
                            "section_number": record.section_number,
                        },
                    )
                )
                chunk_idx += 1
                current_sentences = [sentence]
                current_tokens = self.estimate_tokens(context_header) + s_tokens
            else:
                current_sentences.append(sentence)
                current_tokens += s_tokens

        if current_sentences:
            combined_body = " ".join(current_sentences)
            chunk_text = f"{context_header}{combined_body}".strip()
            chunks.append(
                LegalChunkPayload(
                    provision_label=provision_label,
                    chunk_index=chunk_idx,
                    text=chunk_text,
                    token_count=self.estimate_tokens(chunk_text),
                    source_url=record.source_url,
                    content_hash=record.content_hash,
                    metadata={
                        "act_id": record.act_id,
                        "act_name": record.act_name,
                        "act_year": record.act_year,
                        "language": record.language.value,
                        "chapter_title": record.chapter_title,
                        "section_number": record.section_number,
                    },
                )
            )

        return chunks
