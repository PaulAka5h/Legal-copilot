"""Legal Corpus Ingestion Service.

Streams and normalizes scraped legal corpus (sections.jsonl and catalog.json)
into chunks ready for vector embeddings and database insertion.
"""

import json
from pathlib import Path
from typing import Generator, List, Tuple
from backend.src.legal_kb.chunker import LegalChunker
from backend.src.legal_kb.schemas import LegalChunkPayload, LegalKind, LegalSourcePayload, ScrapedSectionRecord


class LegalIngestionService:
    """Service for processing raw scraper outputs into RAG-ready legal chunks."""

    def __init__(self, chunker: LegalChunker = None):
        self.chunker = chunker or LegalChunker()

    def stream_sections(self, jsonl_path: Path) -> Generator[ScrapedSectionRecord, None, None]:
        """Streams and parses scraped legal sections one line at a time."""
        if not jsonl_path.exists():
            raise FileNotFoundError(f"Processed sections file not found: {jsonl_path}")

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                clean_line = line.strip()
                if not clean_line:
                    continue
                try:
                    data = json.loads(clean_line)
                    yield ScrapedSectionRecord.model_validate(data)
                except Exception as e:
                    # Log or yield error if needed
                    continue

    def process_sections_to_chunks(self, jsonl_path: Path) -> Generator[LegalChunkPayload, None, None]:
        """Converts streaming section records into discrete, token-bounded legal chunks."""
        for section in self.stream_sections(jsonl_path):
            chunks = self.chunker.chunk_section(section)
            for chunk in chunks:
                yield chunk
