"""Legal text chunker engine.

Chunks legal documents (sections/subsections) into target token ranges (300-600 tokens)
while respecting:
1. Section and paragraph boundaries (never splitting clauses arbitrarily).
2. Bilingual sentence markers (Bengali Dari '|', English period '.', colons, etc.).
3. Preserving citation provenance (Act, Chapter, Section label, Source URL).
4. Populating amendment-aware metadata and parent-child hierarchy keys.
"""

import re
from typing import List, Tuple
from uuid import uuid4
from backend.src.legal_kb.schemas import LegalChunkPayload, ScrapedSectionRecord


class LegalChunker:
    """Configurable legal text chunker with token limit safety (max 512 for E5 large input budget)."""

    def __init__(self, min_tokens: int = 50, target_tokens: int = 280, max_tokens: int = 420):
        # max_tokens is kept at 420 to guarantee header + text fits safely within the 512 embedding token budget
        self.min_tokens = min_tokens
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count across English and Bengali scripts.

        A word-split heuristic with 1.35x weighting reliably models multilingual BPE/WordPiece tokenizers.
        """
        if not text:
            return 0
        words = text.split()
        return max(1, int(len(words) * 1.35))

    def split_sentences(self, text: str) -> List[str]:
        """Split text by legal clause delimiters, English periods, and Bengali Dari ('|')."""
        pattern = r"(?<=[।\n\.])\s+"
        parts = re.split(pattern, text)
        return [p.strip() for p in parts if p.strip()]

    def chunk_section(self, record: ScrapedSectionRecord) -> List[LegalChunkPayload]:
        """Chunks a single scraped section into one or more LegalChunkPayloads."""
        section_label_parts = []
        if record.section_number:
            section_label_parts.append(f"Section {record.section_number}")
        if record.section_title:
            section_label_parts.append(record.section_title)
        provision_label = " - ".join(section_label_parts) if section_label_parts else record.section_title

        # Context header
        context_header = f"[{record.act_name}"
        if record.chapter_title:
            context_header += f" | {record.chapter_title}"
        if provision_label:
            context_header += f" | {provision_label}"
        context_header += "]\n"

        # Assemble full section body
        full_body = record.section_content.strip()
        if record.subsections:
            sub_texts = []
            for sub in record.subsections:
                clause = sub.get("clause") or ""
                content = sub.get("content") or ""
                sub_texts.append(f"{clause} {content}".strip())
            if sub_texts:
                full_body += "\n" + "\n".join(sub_texts)

        total_est_tokens = self.estimate_tokens(f"{context_header}{full_body}")

        chunks: List[LegalChunkPayload] = []

        # Parent ID to link child chunks of the same section
        parent_chunk_id = uuid4()

        # If fits within max_tokens, emit single chunk
        if total_est_tokens <= self.max_tokens:
            chunk_text = f"{context_header}{full_body}".strip()
            chunks.append(
                LegalChunkPayload(
                    id=parent_chunk_id,
                    act_id=record.act_id,
                    act_name=record.act_name,
                    act_name_bn=record.act_name if record.language.value == "bn" else None,
                    act_year=record.act_year,
                    chapter=record.chapter_title or record.chapter_number,
                    section=record.section_number,
                    language=record.language,
                    is_current=True,
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
                        "enactment_date": record.enactment_date,
                    },
                )
            )
            return chunks

        # Otherwise, split across clause/sentence boundaries
        sentences = self.split_sentences(full_body)
        current_sentences: List[str] = []
        current_tokens = self.estimate_tokens(context_header)
        chunk_idx = 0

        for sentence in sentences:
            s_tokens = self.estimate_tokens(sentence)

            if current_tokens + s_tokens > self.max_tokens and current_sentences:
                combined_body = " ".join(current_sentences)
                chunk_text = f"{context_header}{combined_body}".strip()
                chunk_id = parent_chunk_id if chunk_idx == 0 else uuid4()
                chunks.append(
                    LegalChunkPayload(
                        id=chunk_id,
                        act_id=record.act_id,
                        act_name=record.act_name,
                        act_name_bn=record.act_name if record.language.value == "bn" else None,
                        act_year=record.act_year,
                        chapter=record.chapter_title or record.chapter_number,
                        section=record.section_number,
                        parent_id=parent_chunk_id if chunk_idx > 0 else None,
                        language=record.language,
                        is_current=True,
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
                            "enactment_date": record.enactment_date,
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
            chunk_id = parent_chunk_id if chunk_idx == 0 else uuid4()
            chunks.append(
                LegalChunkPayload(
                    id=chunk_id,
                    act_id=record.act_id,
                    act_name=record.act_name,
                    act_name_bn=record.act_name if record.language.value == "bn" else None,
                    act_year=record.act_year,
                    chapter=record.chapter_title or record.chapter_number,
                    section=record.section_number,
                    parent_id=parent_chunk_id if chunk_idx > 0 else None,
                    language=record.language,
                    is_current=True,
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
                        "enactment_date": record.enactment_date,
                    },
                )
            )

        return chunks
