"""Offload embedding to another machine (e.g. a Kaggle notebook) and import the result.

The model is the configured EMBEDDING_PROVIDER's (an EmbeddingTarget): e5_small_onnx with
scripts/kaggle_embed_e5small.py, local (e5-large) with scripts/kaggle_embed.py.
export: pending legal_chunks -> JSONL {chunk_id, text, content_hash, model, embedding_version
        [, model_sha256 for e5_small_onnx]}. Only public legal KB text (legal_chunks) is
        exported, never case data. `text` is the stored chunk text: NFC, header included,
        no "passage: " prefix.
import: parquet {chunk_id, content_hash, embedding, model, embedding_version
        [, model_sha256]} -> legal_chunks. Each row must match the chunk's current
        content_hash, model, and version, (e5-small) come from the pinned ONNX build, and be
        a finite unit vector of the target's dimension. Already-embedded chunks are left
        alone (idempotent). Anything else is rejected into a report by chunk_id and reason.
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
from app.rag.search.e5_small_onnx import E5_SMALL_MODEL, E5_SMALL_MODEL_SHA256

# Default target for callers that do not pass one: e5-large (EMBEDDING_PROVIDER=local).
_E5_LARGE = (EMBEDDING_MODEL, EMBEDDING_VERSION, DIMENSION)


def _target(target: Any) -> tuple[str, int, int]:
    return _E5_LARGE if target is None else (target.model, target.version, target.dimension)

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


async def export_pending(engine: AsyncEngine, out_path: Path, target: Any = None, limit: int | None = None) -> int:
    """Write pending chunks to JSONL atomically; returns the number of rows."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    count = 0
    model, version, _ = _target(target)
    extra = {"model_sha256": E5_SMALL_MODEL_SHA256} if model == E5_SMALL_MODEL else {}
    async with engine.connect() as conn:
        rows = await conn.execute(_PENDING_ROWS, {"model": model, "version": version, "limit": limit if limit else None})
        with open(tmp, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps({
                    "chunk_id": str(row.id),
                    "text": row.text,
                    "content_hash": row.content_hash,
                    "model": model,
                    "embedding_version": version,
                    **extra,
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


def _vector_problem(vector: Any, dimension: int = DIMENSION) -> str | None:
    if vector is None or len(vector) != dimension:
        return f"embedding must have {dimension} dimensions"
    values = [float(x) for x in vector]
    if not all(math.isfinite(x) for x in values):
        return "embedding has non-finite values"
    if abs(math.sqrt(sum(x * x for x in values)) - 1.0) > NORM_TOLERANCE:
        return "embedding is not unit norm"
    return None


def iter_parquet_rows(path: Path, extra: frozenset[str] = frozenset()) -> Iterator[list[dict[str, Any]]]:
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(path)
    required = {"chunk_id", "content_hash", "embedding", "model", "embedding_version", *extra}
    missing = required - set(parquet.schema_arrow.names)
    if missing:
        raise ValueError(f"Parquet is missing columns: {sorted(missing)}")
    for batch in parquet.iter_batches(batch_size=IMPORT_BATCH, columns=sorted(required)):
        yield batch.to_pylist()


async def import_parquet(engine: AsyncEngine, path: Path, target: Any = None) -> ImportStats:
    stats = ImportStats()
    model, version, dimension = _target(target)
    pinned = model == E5_SMALL_MODEL
    for rows in iter_parquet_rows(path, frozenset({"model_sha256"}) if pinned else frozenset()):
        stats.rows += len(rows)
        valid: dict[UUID, dict[str, Any]] = {}
        for row in rows:
            try:
                chunk_id = UUID(str(row["chunk_id"]))
            except ValueError:
                stats.reject(row["chunk_id"], "chunk_id is not a UUID")
                continue
            if row["model"] != model or row["embedding_version"] != version:
                stats.reject(chunk_id, "model or embedding_version differs from this deployment")
                continue
            if pinned and row["model_sha256"] != E5_SMALL_MODEL_SHA256:
                stats.reject(chunk_id, "made with another ONNX build (model_sha256 differs)")
                continue
            problem = _vector_problem(row["embedding"], dimension)
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
                elif (chunk.embedding_model, chunk.embedding_version) != (model, version):
                    stats.reject(chunk_id, "stored chunk expects a different model or version")
                elif chunk.embedded:
                    stats.already_embedded += 1
                else:
                    updates.append({
                        "id": chunk_id,
                        "embedding": vector_literal([float(x) for x in row["embedding"]]),
                        "model": model,
                        "version": version,
                        "content_hash": row["content_hash"],
                    })
            if updates:
                # Rows are locked above, so every update applies exactly once.
                await conn.execute(_STORE, updates)
                stats.imported += len(updates)
    return stats
