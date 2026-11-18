"""Pipeline orchestrator for streaming scraper JSONL into Vector Database."""

from pathlib import Path
from typing import Optional
from backend.src.legal_kb.embeddings import BaseEmbeddingProvider
from backend.src.legal_kb.service import LegalIngestionService
from backend.src.legal_kb.vector_store import BaseVectorStore


class LegalVectorIngestionPipeline:
    """Streams data-scrapper/ section files, chunks them, computes embeddings, and stores in Vector DB."""

    def __init__(
        self,
        vector_store: BaseVectorStore,
        embedding_provider: BaseEmbeddingProvider,
        ingestion_service: Optional[LegalIngestionService] = None,
        batch_size: int = 64,
    ):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.ingestion_service = ingestion_service or LegalIngestionService()
        self.batch_size = batch_size

    def ingest_from_file(self, jsonl_path: Path, max_chunks: Optional[int] = None) -> int:
        """Processes chunks in batches with embeddings and commits them to the vector store."""
        total_chunks = 0
        batch_chunks = []
        batch_texts = []

        for chunk in self.ingestion_service.process_sections_to_chunks(jsonl_path):
            chunk.metadata["embedding_model"] = self.embedding_provider.model_name
            batch_chunks.append(chunk)
            batch_texts.append(chunk.text)

            if len(batch_chunks) >= self.batch_size:
                embeddings = self.embedding_provider.embed_texts(batch_texts)
                self.vector_store.add_chunks(batch_chunks, embeddings)
                total_chunks += len(batch_chunks)
                batch_chunks = []
                batch_texts = []

            if max_chunks and total_chunks + len(batch_chunks) >= max_chunks:
                break

        if batch_chunks:
            embeddings = self.embedding_provider.embed_texts(batch_texts)
            self.vector_store.add_chunks(batch_chunks, embeddings)
            total_chunks += len(batch_chunks)

        return total_chunks
