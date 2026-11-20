"""Spot-check sampling is read-only and reproducible with a seed."""

import asyncio

from app.rag.spot_check import sample_pending


def test_sample_is_reproducible_and_bounded(ingest_url):
    total, first = asyncio.run(sample_pending(ingest_url, 5, seed=42))
    _, again = asyncio.run(sample_pending(ingest_url, 5, seed=42))
    assert [r["id"] for r in first] == [r["id"] for r in again]
    assert len(first) == min(5, total)
    assert all(r["source_url"] and r["sections"] >= 0 for r in first)
