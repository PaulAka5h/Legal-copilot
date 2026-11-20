"""Embed pending legal chunks with multilingual-e5-large (self-hosted).

- Text sent to the model is "passage: " + NFC(chunk text), normalized vectors.
- Resumable: each batch is its own transaction; pending = embedding IS NULL.
- Safe with several workers: rows are claimed with FOR UPDATE SKIP LOCKED.
- Idempotent via content_hash: a chunk whose hash already has an embedding for
  the same model and version reuses it instead of re-encoding.
Chunk text is never logged.
"""

import time
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.rag.ingest.chunking import EMBEDDING_MODEL, EMBEDDING_VERSION, MAX_TOKENS, PASSAGE_PREFIX
from app.rag.text import nfc

DIMENSION = 1024

_CLAIM = text(
    """
    SELECT id, text, content_hash FROM public.legal_chunks
    WHERE embedding IS NULL AND is_active
      AND embedding_model = :model AND embedding_version = :version
    ORDER BY id
    LIMIT :n
    FOR UPDATE SKIP LOCKED
    """
)
_REUSABLE = text(
    """
    SELECT DISTINCT ON (content_hash) content_hash, embedding::text
    FROM public.legal_chunks
    WHERE content_hash = ANY(:hashes) AND embedding IS NOT NULL
      AND embedding_model = :model AND embedding_version = :version
    """
)
_STORE = text(
    """
    UPDATE public.legal_chunks
    SET embedding = CAST(:embedding AS vector), embedded_at = now()
    WHERE id = :id AND embedding IS NULL
    """
)
_PENDING = text(
    """
    SELECT count(*) FROM public.legal_chunks
    WHERE embedding IS NULL AND is_active
      AND embedding_model = :model AND embedding_version = :version
    """
)


class Embedder(Protocol):
    device: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class E5Embedder:
    """sentence-transformers wrapper; fp16 on CUDA to fit small GPUs."""

    def __init__(self, device: str, batch_size: int):
        from sentence_transformers import SentenceTransformer

        self.device = device
        self.batch_size = batch_size
        self.model = SentenceTransformer(EMBEDDING_MODEL, device=device)
        self.model.max_seq_length = MAX_TOKENS
        if device == "cuda":
            self.model.half()

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            [PASSAGE_PREFIX + nfc(t) for t in texts],
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.astype("float32").tolist()


def cuda_build_supports(capability: tuple[int, int], arch_list: list[str]) -> bool:
    """True if the installed torch has kernels for this GPU (same major, build minor <= GPU minor)."""
    major, minor = capability
    for arch in arch_list:
        if arch.startswith("sm_") and arch[3:].isdigit():
            built = int(arch[3:])
            if built // 10 == major and built % 10 <= minor:
                return True
    return False


def pick_device(requested: str) -> str:
    """auto -> cuda only when a GPU exists and this torch build can run on it."""
    if requested != "auto":
        return requested
    import torch

    if not torch.cuda.is_available():
        return "cpu"
    return "cuda" if cuda_build_supports(torch.cuda.get_device_capability(0), torch.cuda.get_arch_list()) else "cpu"


def is_out_of_memory(error: BaseException) -> bool:
    return "out of memory" in str(error).lower()


def vector_literal(vector: list[float]) -> str:
    if len(vector) != DIMENSION:
        raise ValueError(f"Expected {DIMENSION} dimensions, got {len(vector)}")
    return "[" + ",".join(f"{x:.7g}" for x in vector) + "]"


@dataclass
class EmbedStats:
    embedded: int = 0
    reused_by_content_hash: int = 0
    batches: int = 0
    encode_seconds: float = 0.0
    total_seconds: float = 0.0


async def count_pending(engine: AsyncEngine) -> int:
    async with engine.connect() as conn:
        return await conn.scalar(_PENDING, {"model": EMBEDDING_MODEL, "version": EMBEDDING_VERSION})


async def embed_pending(
    engine: AsyncEngine,
    embedder: Embedder,
    batch_size: int,
    limit: int | None = None,
    stats: EmbedStats | None = None,
) -> EmbedStats:
    """Embed pending chunks; pass `stats` to keep counting across a retry."""
    stats = stats or EmbedStats()
    started = time.perf_counter()
    params = {"model": EMBEDDING_MODEL, "version": EMBEDDING_VERSION}
    while limit is None or stats.embedded + stats.reused_by_content_hash < limit:
        remaining = None if limit is None else limit - stats.embedded - stats.reused_by_content_hash
        size = batch_size if remaining is None else min(batch_size, remaining)
        async with engine.begin() as conn:
            rows = (await conn.execute(_CLAIM, {**params, "n": size})).all()
            if not rows:
                break
            reusable = dict(
                (await conn.execute(_REUSABLE, {**params, "hashes": [r.content_hash for r in rows]})).all()
            )
            fresh = [r for r in rows if r.content_hash not in reusable]
            t0 = time.perf_counter()
            vectors = embedder.embed([r.text for r in fresh]) if fresh else []
            stats.encode_seconds += time.perf_counter() - t0

            updates = [{"id": r.id, "embedding": vector_literal(v)} for r, v in zip(fresh, vectors)]
            updates += [
                {"id": r.id, "embedding": reusable[r.content_hash]}
                for r in rows if r.content_hash in reusable
            ]
            await conn.execute(_STORE, updates)
        stats.embedded += len(fresh)
        stats.reused_by_content_hash += len(rows) - len(fresh)
        stats.batches += 1
    stats.total_seconds += time.perf_counter() - started
    return stats
