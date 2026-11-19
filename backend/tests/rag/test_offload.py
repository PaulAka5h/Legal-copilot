"""Embedding export/import for external GPUs. Runs against legal_copilot_test. SAMPLE_DATA_NOT_REAL_LAW."""

import asyncio
import json
import secrets
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from app.rag.embed.offload import export_pending, import_parquet
from app.rag.embed.worker import DIMENSION
from app.rag.ingest.chunking import EMBEDDING_MODEL, EMBEDDING_VERSION
from app.rag.ingest.repository import create_ingest_engine
from tests.rag.test_embed_and_approve import CHUNKS_FOR_ACT, _fetch, _ingest
from tests.rag.test_ingest import SAMPLE, record, write_jsonl

UNIT = [1.0] + [0.0] * (DIMENSION - 1)


def _with_engine(url, fn):
    async def run():
        engine = create_ingest_engine(url)
        try:
            return await fn(engine)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _write_parquet(path, rows):
    pq.write_table(
        pa.table({
            "chunk_id": [r["chunk_id"] for r in rows],
            "content_hash": [r["content_hash"] for r in rows],
            "embedding": [r["embedding"] for r in rows],
            "model": [r.get("model", EMBEDDING_MODEL) for r in rows],
            "embedding_version": [r.get("embedding_version", EMBEDDING_VERSION) for r in rows],
        }),
        path,
    )


def test_export_then_import_validates_and_is_idempotent(counter, ingest_url, tmp_path):
    act = f"sample-{secrets.token_hex(6)}"
    bodies = [f"{SAMPLE} {secrets.token_hex(8)} ধারা {i}" for i in range(4)]
    write_jsonl(tmp_path / "s.jsonl", [record(act_id=act, n=str(i + 1), body=b) for i, b in enumerate(bodies)])
    _ingest(ingest_url, tmp_path / "s.jsonl", counter)

    out = tmp_path / "chunks.jsonl"
    exported = _with_engine(ingest_url, lambda e: export_pending(e, out))
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert exported == len(rows)
    ours = [r for r in rows if any(b in r["text"] for b in bodies)]
    assert len(ours) == 4
    assert all(r["model"] == EMBEDDING_MODEL and not r["text"].startswith("passage: ") for r in ours)
    assert all(SAMPLE in r["text"].split("\n", 1)[0] for r in ours)  # header included

    good, bad_hash, bad_dim, bad_norm = ours
    parquet = tmp_path / "e.parquet"
    _write_parquet(parquet, [
        {**good, "embedding": UNIT},
        {**bad_hash, "content_hash": "0" * 64, "embedding": UNIT},
        {**bad_dim, "embedding": [1.0] * 10},
        {**bad_norm, "embedding": [0.5] * DIMENSION},
        {"chunk_id": str(uuid4()), "content_hash": "x", "embedding": UNIT},
        {"chunk_id": "not-a-uuid", "content_hash": "x", "embedding": UNIT},
        {**good, "model": "other-model", "embedding": UNIT},
    ])
    stats = _with_engine(ingest_url, lambda e: import_parquet(e, parquet))
    reasons = {r["chunk_id"]: r["reason"] for r in stats.rejected}
    assert stats.imported == 1
    assert "content_hash" in reasons[bad_hash["chunk_id"]]
    assert "dimensions" in reasons[bad_dim["chunk_id"]]
    assert "unit norm" in reasons[bad_norm["chunk_id"]]
    assert "not-a-uuid" in reasons
    assert len(stats.rejected) == 6  # incl. unknown chunk and model mismatch

    embedded = {r.content_hash: r.embedded for r in _fetch(ingest_url, CHUNKS_FOR_ACT, name=SAMPLE, act=act)}
    assert embedded[good["content_hash"]] and not embedded[bad_hash["content_hash"]]

    _write_parquet(parquet, [{**good, "embedding": UNIT}])
    again = _with_engine(ingest_url, lambda e: import_parquet(e, parquet))
    assert (again.imported, again.already_embedded, again.rejected) == (0, 1, [])
