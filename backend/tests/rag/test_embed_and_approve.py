"""Embedding worker and version approval. Runs against legal_copilot_test only.

All legal-looking rows use source_name SAMPLE_DATA_NOT_REAL_LAW (database.md 16).
"""

import argparse
import asyncio
import os
import secrets
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine, user_transaction
from app.rag import approve
from app.rag.embed.worker import (
    DIMENSION,
    EmbedStats,
    cuda_build_supports,
    embed_pending,
    pick_device,
    vector_literal,
)
from app.rag.ingest.pipeline import ingest_batches
from app.rag.ingest.records import Rejects, iter_act_batches
from app.rag.ingest.repository import create_ingest_engine
from tests.rag.test_ingest import SAMPLE, record, write_jsonl

ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "correct horse battery staple"


class FakeEmbedder:
    """Deterministic unit vectors; records every text it is asked to encode."""

    device = "cpu"

    def __init__(self):
        self.seen: list[str] = []

    def embed(self, texts):
        self.seen.extend(texts)
        return [[1.0] + [0.0] * (DIMENSION - 1) for _ in texts]


def test_vector_literal_checks_dimension_and_device_choice():
    assert vector_literal([0.5] * DIMENSION).startswith("[0.5,")
    with pytest.raises(ValueError):
        vector_literal([0.1, 0.2])
    assert pick_device("cpu") == "cpu"


def test_cuda_is_used_only_when_the_torch_build_supports_the_gpu():
    build = ["sm_75", "sm_80", "sm_86", "sm_90", "sm_100", "sm_120"]
    assert not cuda_build_supports((6, 1), build)  # e.g. MX350 with a cu132 build
    assert cuda_build_supports((7, 5), build)
    assert cuda_build_supports((8, 9), build)  # sm_86 kernels run on 8.9
    assert not cuda_build_supports((7, 0), build)


def _ingest(url, path, counter):
    async def run():
        engine = create_ingest_engine(url)
        try:
            return await ingest_batches(iter_act_batches(path, Rejects()), counter, engine, source_name=SAMPLE)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _fetch(url, sql, **params):
    async def run():
        engine = create_ingest_engine(url)
        try:
            async with engine.connect() as conn:
                return (await conn.execute(text(sql), params)).all()
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _embed(url, embedder):
    async def run():
        engine = create_ingest_engine(url)
        try:
            return await embed_pending(engine, embedder, batch_size=64, stats=EmbedStats())
        finally:
            await engine.dispose()

    return asyncio.run(run())


CHUNKS_FOR_ACT = """
    SELECT c.content_hash, c.embedding IS NOT NULL AS embedded, c.embedded_at IS NOT NULL AS stamped
    FROM legal_chunks c
    JOIN legal_source_versions v ON v.id = c.legal_source_version_id
    JOIN legal_sources s ON s.id = v.legal_source_id
    WHERE s.source_name = :name AND s.external_id = :act
"""


def test_embed_is_resumable_and_reuses_embeddings_by_content_hash(counter, ingest_url, tmp_path):
    act_a, act_b = f"sample-{secrets.token_hex(6)}", f"sample-{secrets.token_hex(6)}"
    path = tmp_path / "sections.jsonl"
    marker = f"{SAMPLE} {secrets.token_hex(8)}"  # unique text so hashes are new in this DB

    write_jsonl(path, [record(act_id=act_a, body=marker)])
    _ingest(ingest_url, path, counter)
    first = FakeEmbedder()
    _embed(ingest_url, first)
    rows_a = _fetch(ingest_url, CHUNKS_FOR_ACT, name=SAMPLE, act=act_a)
    assert rows_a and all(r.embedded and r.stamped for r in rows_a)
    assert any(marker in t for t in first.seen)

    # Same act title and section text under a new act id -> identical chunk text and hash.
    write_jsonl(path, [record(act_id=act_b, body=marker)])
    _ingest(ingest_url, path, counter)
    second = FakeEmbedder()
    stats = _embed(ingest_url, second)
    rows_b = _fetch(ingest_url, CHUNKS_FOR_ACT, name=SAMPLE, act=act_b)
    assert {r.content_hash for r in rows_b} == {r.content_hash for r in rows_a}
    assert all(r.embedded for r in rows_b)
    assert not any(marker in t for t in second.seen)  # reused, not re-encoded
    assert stats.reused_by_content_hash >= len(rows_b)

    assert _embed(ingest_url, FakeEmbedder()).embedded == 0  # nothing pending: idempotent


def _register(api_client) -> tuple[str, UUID]:
    email = f"reviewer-{secrets.token_hex(6)}@example.com"
    assert api_client.post(
        "/api/v1/auth/register", headers=ORIGIN,
        json={"email": email, "password": PASSWORD, "full_name": f"{SAMPLE} Reviewer"},
    ).status_code == 201
    assert api_client.post(
        "/api/v1/auth/login", headers=ORIGIN, json={"email": email, "password": PASSWORD}
    ).status_code == 200
    return email, UUID(api_client.get("/api/v1/me").json()["id"])


def test_approval_records_reviewer_time_and_audit_event(api_client, counter, ingest_url, tmp_path, monkeypatch):
    email, reviewer_id = _register(api_client)
    act = f"sample-{secrets.token_hex(6)}"
    path = tmp_path / "sections.jsonl"
    write_jsonl(path, [record(act_id=act)])
    _ingest(ingest_url, path, counter)
    (version_id,) = [
        r.id for r in _fetch(
            ingest_url,
            "SELECT v.id FROM legal_source_versions v JOIN legal_sources s ON s.id = v.legal_source_id "
            "WHERE s.source_name = :name AND s.external_id = :act",
            name=SAMPLE, act=act,
        )
    ]
    monkeypatch.setenv("LEGAL_INGEST_DATABASE_URL", ingest_url)

    def args(**overrides):
        base = dict(version_id=[version_id], all_pending=False, reviewer_email=email, note=SAMPLE, dry_run=False)
        return argparse.Namespace(**{**base, **overrides})

    def status():
        return _fetch(
            ingest_url,
            "SELECT review_status, reviewed_by, reviewed_at FROM legal_source_versions WHERE id = :id",
            id=version_id,
        )[0]

    dry = asyncio.run(approve.run(args(dry_run=True)))
    assert dry["to_approve"] == 1 and dry["reviewer_eligible"] and status().review_status == "pending"

    with pytest.raises(SystemExit):
        asyncio.run(approve.run(args(reviewer_email="nobody@example.com")))
    assert status().review_status == "pending"

    assert asyncio.run(approve.run(args()))["approved"] == 1
    approved = status()
    assert (approved.review_status, approved.reviewed_by) == ("approved", reviewer_id)
    assert approved.reviewed_at is not None

    with pytest.raises(SystemExit):  # already approved: not pending
        asyncio.run(approve.run(args()))

    async def audit_events():
        engine = create_database_engine(api_client.app.state.settings.database_url)
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with user_transaction(factory, reviewer_id) as session:
                rows = await session.execute(
                    text(
                        "SELECT action, actor_role, details->>'note' FROM audit_logs "
                        "WHERE object_id = :id AND actor_user_id = :actor"
                    ),
                    {"id": version_id, "actor": reviewer_id},
                )
                return [tuple(r) for r in rows]
        finally:
            await engine.dispose()

    assert asyncio.run(audit_events()) == [("legal_source_version.approved", "lawyer", SAMPLE)]
