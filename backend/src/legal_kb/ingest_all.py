"""Batch Ingestion script to ingest the full scraped Bangladesh legal dataset into PostgreSQL pgvector.

Usage:
    PYTHONPATH=.. python -m src.legal_kb.ingest_all --limit 500 --batch-size 64 --db-url "..."
"""

import argparse
import os
from pathlib import Path
import time
from backend.src.legal_kb.embeddings import MockEmbeddingProvider, SentenceTransformersEmbeddingProvider
from backend.src.legal_kb.migrations import CREATE_LEGAL_KB_TABLES_SQL
from backend.src.legal_kb.pipeline import LegalVectorIngestionPipeline
from backend.src.legal_kb.service import LegalIngestionService
from backend.src.legal_kb.vector_store import PgVectorStore
import psycopg

# No credential fallback: pass --db-url or set DATABASE_URL.
DEFAULT_DB_URL = os.environ.get("DATABASE_URL")
DEFAULT_JSONL_PATH = (
    Path(__file__).resolve().parents[3] / "data-scrapper" / "data" / "processed" / "sections.jsonl"
)


def main():
    parser = argparse.ArgumentParser(description="Ingest scraped Bangladesh Acts into PostgreSQL pgvector")
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL_PATH, help="Path to sections.jsonl")
    parser.add_argument(
        "--db-url", type=str, default=DEFAULT_DB_URL, required=DEFAULT_DB_URL is None,
        help="PostgreSQL connection string (defaults to DATABASE_URL)",
    )
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding & DB batch size")
    parser.add_argument("--limit", type=int, default=None, help="Max chunks to ingest (None for all)")
    parser.add_argument("--use-real-model", action="store_true", help="Load real multilingual-e5-large model")
    args = parser.parse_args()

    print("=" * 60)
    print("Bangladesh Legal Knowledge Base - Batch Ingestion Pipeline")
    print("=" * 60)
    print(f"Dataset path: {args.jsonl}")
    print(f"Batch size:   {args.batch_size}")
    print(f"Chunk limit:  {args.limit if args.limit else 'ALL available chunks'}")
    print(f"Embedding:    {'intfloat/multilingual-e5-large' if args.use_real_model else 'MockEmbeddingProvider (1024-dim fast dev)'}")
    print("-" * 60)

    if not args.jsonl.exists():
        print(f"ERROR: Dataset file not found at {args.jsonl}")
        return

    # 1. Initialize tables & HNSW indexes in PostgreSQL
    print("1. Initializing PostgreSQL tables & HNSW vector indexes...")
    with psycopg.connect(args.db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_LEGAL_KB_TABLES_SQL)
    print("   ✓ Tables, triggers, and HNSW indexes verified.")

    # 2. Setup Vector Store & Embedding Provider
    vector_store = PgVectorStore(db_url=args.db_url)
    if args.use_real_model:
        print("2. Loading multilingual-e5-large sentence transformer...")
        embedding_provider = SentenceTransformersEmbeddingProvider()
    else:
        print("2. Initializing deterministic MockEmbeddingProvider (1024-dim)...")
        embedding_provider = MockEmbeddingProvider(dimension=1024)

    # 3. Run Ingestion Pipeline
    print("3. Streaming sections and embedding chunks into pgvector...")
    pipeline = LegalVectorIngestionPipeline(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        ingestion_service=LegalIngestionService(),
        batch_size=args.batch_size,
    )

    start_time = time.time()
    total_ingested = pipeline.ingest_from_file(args.jsonl, max_chunks=args.limit)
    elapsed = time.time() - start_time

    print("-" * 60)
    print(f"SUCCESS: Successfully ingested {total_ingested} legal chunks into pgvector!")
    print(f"Total time: {elapsed:.2f} seconds ({total_ingested / max(elapsed, 0.001):.1f} chunks/sec)")
    print("=" * 60)


if __name__ == "__main__":
    main()
