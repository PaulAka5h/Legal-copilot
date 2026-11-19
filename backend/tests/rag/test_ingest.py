"""Step A ingestion tests. All legal-looking text is SAMPLE_DATA_NOT_REAL_LAW."""

import asyncio
import json
import os
import secrets

import pytest
from sqlalchemy import text

from app.rag.ingest.chunking import MAX_TOKENS, PASSAGE_PREFIX, chunk_section, section_header
from app.rag.ingest.pipeline import canonical_section_id, ingest_batches, section_row
from app.rag.ingest.records import Rejects, iter_act_batches
from app.rag.ingest.repository import create_ingest_engine

SAMPLE = "SAMPLE_DATA_NOT_REAL_LAW"
BANGLA_BODY = "১। এই ধারাটি SAMPLE_DATA_NOT_REAL_LAW নমুনা পাঠ, কোন আইন নয়। (ক) প্রথম উপধারা।"


def record(act_id="9001", n="১", lang="bn", body=BANGLA_BODY, title=None):
    return {
        "document_id": f"bd-act-{act_id}-sec-{n}-{lang}",
        "act_id": act_id,
        "act_name": f"{SAMPLE} Act",
        "act_number": "I",
        "act_year": "2099",
        "language": lang,
        "section_number": n,
        "section_title": title or f"{SAMPLE} heading",
        "section_content": body,
        "source_url": f"https://example.invalid/act-{act_id}/section-1.html",
        "content_hash": "h",
    }


def write_jsonl(path, records):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")


def test_bangla_round_trip_and_header(counter, tmp_path):
    path = tmp_path / "sections.jsonl"
    write_jsonl(path, [record()])
    (batch,) = list(iter_act_batches(path, Rejects()))
    stored = section_row(batch.records[0], 0)
    assert stored["text"] == BANGLA_BODY

    header = section_header(f"{SAMPLE} Act", "2099", "১", f"{SAMPLE} heading")
    assert header == f"{SAMPLE} Act (2099) — Section ১: {SAMPLE} heading\n"
    (chunk,) = chunk_section(header, BANGLA_BODY, counter)
    assert chunk.text == header + BANGLA_BODY


def test_prefix_is_counted(counter):
    tokenizer = counter.tokenizer
    assert counter.count("x") == len(tokenizer(PASSAGE_PREFIX + "x")["input_ids"])
    assert counter.count("x") > len(tokenizer("x")["input_ids"])


def test_long_section_sub_chunks_under_512_tokens_with_overlap(counter):
    body = " ".join(
        f"({i}) {SAMPLE} নমুনা বাক্য সংখ্যা {i}, sample clause number {i}." for i in range(400)
    )
    header = section_header(f"{SAMPLE} Act", "2099", "7", "Long sample section")
    chunks = chunk_section(header, body, counter)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.text.startswith(header)
        assert counter.count(chunk.text) == chunk.token_count <= MAX_TOKENS
        assert chunk.text[len(header):] in body  # exact substring, quotable
    first, second = (c.text[len(header):] for c in chunks[:2])
    assert second.split()[0] in first.split()  # ~15% overlap
    assert chunks[-1].text.endswith(body.split()[-1])  # nothing dropped at the end


def test_validator_rejects_and_grouping(tmp_path):
    path = tmp_path / "sections.jsonl"
    bad = record(n="2", body="")
    write_jsonl(path, [record(), bad, record(act_id="9002", lang="en", n="1", body="SAMPLE text")])
    rejects = Rejects()
    batches = list(iter_act_batches(path, rejects))
    assert [(b.act_id, b.language, len(b.records)) for b in batches] == [("9001", "bn", 1), ("9002", "en", 1)]
    assert rejects.items == [{"line": 2, "document_id": bad["document_id"], "issues": ["Empty section_content"]}]

    write_jsonl(path, [record(), record(act_id="9002", lang="en", body="x"), record(n="3")])
    with pytest.raises(ValueError, match="not grouped"):
        list(iter_act_batches(path, Rejects()))


def test_canonical_id_links_bn_and_en_and_repealed_marker():
    bn = record(n="১২", lang="bn")
    en = record(n="12", lang="en")
    en["document_id"] = "bd-act-9001-sec-12-en"
    bn["document_id"] = "bd-act-9001-sec-১২-bn"
    assert canonical_section_id(bn) == canonical_section_id(en)
    assert canonical_section_id(bn) != canonical_section_id(record(n="13"))

    repealed = section_row(record(title="[Repealed]"), 0)
    assert (repealed["status"], repealed["status_basis"]) == ("repealed", "section_title_marker")
    assert section_row(record(), 0)["status"] == "unknown"


def test_dry_run_counts_without_database(counter, tmp_path):
    path = tmp_path / "sections.jsonl"
    write_jsonl(path, [record(), record(n="২"), record(act_id="9002")])
    summary = asyncio.run(ingest_batches(iter_act_batches(path, Rejects()), counter, None, limit=1))
    assert (summary.acts_seen, summary.sections, summary.acts_new_version) == (1, 2, 0)


def test_rerun_is_idempotent_and_change_adds_version(counter, tmp_path):
    """Opt-in: writes SAMPLE_DATA_NOT_REAL_LAW rows that cannot be deleted (no DELETE grant)."""
    url = os.getenv("LEGAL_INGEST_TEST_DATABASE_URL")
    if not url:
        pytest.skip("LEGAL_INGEST_TEST_DATABASE_URL is not set")
    act_id = f"sample-{secrets.token_hex(6)}"
    path = tmp_path / "sections.jsonl"

    async def ingest():
        engine = create_ingest_engine(url)
        try:
            return await ingest_batches(
                iter_act_batches(path, Rejects()), counter, engine, source_name=SAMPLE
            )
        finally:
            await engine.dispose()

    async def versions():
        engine = create_ingest_engine(url)
        try:
            async with engine.connect() as conn:
                rows = await conn.execute(
                    text(
                        """
                        SELECT v.version_no, v.is_current, v.review_status, count(c.id)
                        FROM legal_sources s
                        JOIN legal_source_versions v ON v.legal_source_id = s.id
                        LEFT JOIN legal_chunks c ON c.legal_source_version_id = v.id
                        WHERE s.source_name = :name AND s.external_id = :act
                        GROUP BY v.version_no, v.is_current, v.review_status ORDER BY v.version_no
                        """
                    ),
                    {"name": SAMPLE, "act": act_id},
                )
                return [tuple(r) for r in rows]
        finally:
            await engine.dispose()

    write_jsonl(path, [record(act_id=act_id), record(act_id=act_id, n="২")])
    assert asyncio.run(ingest()).acts_new_version == 1
    assert asyncio.run(ingest()).acts_unchanged == 1
    assert asyncio.run(versions()) == [(1, True, "pending", 2)]

    write_jsonl(path, [record(act_id=act_id, body=BANGLA_BODY + " পরিবর্তিত।")])
    assert asyncio.run(ingest()).acts_new_version == 1
    assert asyncio.run(versions()) == [(1, False, "pending", 2), (2, True, "pending", 1)]
