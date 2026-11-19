"""Offload embedding to an external GPU (e.g. a Kaggle notebook) and import the result.

export: pending legal_chunks -> JSONL {chunk_id, text, content_hash, model, embedding_version}.
        Only public legal KB text (legal_chunks) is exported, never case data.
        `text` is the stored chunk text: NFC, header included, no "passage: " prefix.
import: parquet {chunk_id, content_hash, embedding, model, embedding_version} -> legal_chunks.
        Each row must match the chunk's current content_hash, model, and version and be a
        finite 1024-dim unit vector. Already-embedded chunks are left alone (idempotent).
        Anything else is rejected into a report by chunk_id and reason.
"""

import json
import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.rag.embed.worker import DIMENSION, vector_literal
from app.rag.ingest.chunking import EMBEDDING_MODEL, EMBEDDING_VERSION

NORM_TOLERANCE = 1e-3
IMPORT_BATCH = 500

_PENDING_ROWS = text(
    """
    SELECT id, text, content_hash FROM public.legal_chunks
    WHERE embedding IS NULL AND is_active
      AND embedding_model = :model AND embedding_version = :version
    ORDER BY id
    LIMIT :limit
    """
)
_CURRENT = text(
    """
    SELECT id, content_hash, embedding_model, embedding_version, embedding IS NOT NULL AS embedded
    FROM public.legal_chunks WHERE id = ANY(CAST(:ids AS uuid[]))
    FOR UPDATE
    """
)
_STORE = text(
    """
    UPDATE public.legal_chunks
    SET embedding = CAST(:embedding AS vector), embedding_model = :model,
        embedding_version = :version, embedded_at = now()
    WHERE id = :id AND embedding IS NULL AND content_hash = :content_hash
    """
)


async def export_pending(engine: AsyncEngine, out_path: Path, limit: int | None = None) -> int:
    """Write pending chunks to JSONL atomically; returns the number of rows."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    count = 0
    async with engine.connect() as conn:
        rows = await conn.execute(
            _PENDING_ROWS,
            {"model": EMBEDDING_MODEL, "version": EMBEDDING_VERSION, "limit": limit if limit else None},
        )
        with open(tmp, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps({
                    "chunk_id": str(row.id),
                    "text": row.text,
                    "content_hash": row.content_hash,
                    "model": EMBEDDING_MODEL,
                    "embedding_version": EMBEDDING_VERSION,
                }, ensure_ascii=False) + "\n")
                count += 1
    tmp.replace(out_path)
    return count


@dataclass
class ImportStats:
    rows: int = 0
    imported: int = 0
    already_embedded: int = 0
    rejected: list[dict[str, str]] = field(default_factory=list)

    def reject(self, chunk_id: Any, reason: str) -> None:
        self.rejected.append({"chunk_id": str(chunk_id), "reason": reason})


def _vector_problem(vector: Any) -> str | None:
    if vector is None or len(vector) != DIMENSION:
        return f"embedding must have {DIMENSION} dimensions"
    values = [float(x) for x in vector]
    if not all(math.isfinite(x) for x in values):
        return "embedding has non-finite values"
    if abs(math.sqrt(sum(x * x for x in values)) - 1.0) > NORM_TOLERANCE:
        return "embedding is not unit norm"
    return None


def iter_parquet_rows(path: Path) -> Iterator[list[dict[str, Any]]]:
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(path)
    required = {"chunk_id", "content_hash", "embedding", "model", "embedding_version"}
    missing = required - set(parquet.schema_arrow.names)
    if missing:
        raise ValueError(f"Parquet is missing columns: {sorted(missing)}")
    for batch in parquet.iter_batches(batch_size=IMPORT_BATCH, columns=sorted(required)):
        yield batch.to_pylist()


async def import_parquet(engine: AsyncEngine, path: Path) -> ImportStats:
    stats = ImportStats()
    for rows in iter_parquet_rows(path):
        stats.rows += len(rows)
        valid: dict[UUID, dict[str, Any]] = {}
        for row in rows:
            try:
                chunk_id = UUID(str(row["chunk_id"]))
            except ValueError:
                stats.reject(row["chunk_id"], "chunk_id is not a UUID")
                continue
            if row["model"] != EMBEDDING_MODEL or row["embedding_version"] != EMBEDDING_VERSION:
                stats.reject(chunk_id, "model or embedding_version differs from this deployment")
                continue
            problem = _vector_problem(row["embedding"])
            if problem:
                stats.reject(chunk_id, problem)
                continue
            if chunk_id in valid:
                stats.reject(chunk_id, "duplicate chunk_id in file")
                continue
            valid[chunk_id] = row

        async with engine.begin() as conn:
            current = {
                r.id: r for r in await conn.execute(_CURRENT, {"ids": list(valid)})
            }
            updates = []
            for chunk_id, row in valid.items():
                chunk = current.get(chunk_id)
                if chunk is None:
                    stats.reject(chunk_id, "unknown chunk_id")
                elif chunk.content_hash != row["content_hash"]:
                    stats.reject(chunk_id, "content_hash does not match the stored chunk")
                elif (chunk.embedding_model, chunk.embedding_version) != (EMBEDDING_MODEL, EMBEDDING_VERSION):
                    stats.reject(chunk_id, "stored chunk expects a different model or version")
                elif chunk.embedded:
                    stats.already_embedded += 1
                else:
                    updates.append({
                        "id": chunk_id,
                        "embedding": vector_literal([float(x) for x in row["embedding"]]),
                        "model": EMBEDDING_MODEL,
                        "version": EMBEDDING_VERSION,
                        "content_hash": row["content_hash"],
                    })
            if updates:
                # Rows are locked above, so every update applies exactly once.
                await conn.execute(_STORE, updates)
                stats.imported += len(updates)
    return stats
