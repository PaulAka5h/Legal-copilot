"""Step B: hybrid legal search and POST /api/v1/lawyer/cases/{case_id}/research/search.

Endpoint tests need legal_copilot_test to hold the first 20 bdlaws Acts, approved
and embedded (see DOCS/status.md 7.9 for the setup commands); otherwise they skip.
"""

import asyncio
import json
import secrets
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine, user_transaction
from app.main import create_app
from app.rag.search.retrieval import BN_STOPWORDS, TSQUERY_SQL, in_force
from tests.test_phase2_exit import create_case, create_invite_and_accept, register_login

ORIGIN = {"Origin": "http://localhost:3000"}
QUERIES = json.loads((Path(__file__).parent / "data" / "retrieval_queries_20_acts.json").read_text("utf-8"))["queries"]
INCIDENT = date(2024, 1, 15)


# ---------------------------------------------------------------- in-force rules
def test_in_force_rules():
    d = date(2020, 6, 1)
    assert in_force("in_force", "unknown", None, None, d) == (True, "in_force", ["effective_dates_unknown"])
    assert in_force("unknown", "unknown", None, None, d)[2] == ["amendment_status_unknown", "effective_dates_unknown"]
    assert in_force("unknown", "amended", date(2000, 1, 1), None, d) == (True, "amended", ["status_amended"])
    assert in_force("in_force", "in_force", date(2021, 1, 1), None, d)[0] is False  # not yet in force
    assert in_force("in_force", "in_force", None, date(2019, 1, 1), d)[0] is False  # ended before
    assert in_force("repealed", "unknown", None, None, d)[0] is False  # repeal date unknown
    assert in_force("unknown", "repealed", None, None, None)[0] is False  # whole Act repealed
    assert in_force("repealed", "unknown", None, date(2021, 1, 1), d) == (
        True, "repealed", ["repealed_after_incident_date"]
    )


# ---------------------------------------------------------------- endpoint fixtures
def _fixture_ready(database_url: str, user_id: UUID) -> bool:
    async def check():
        engine = create_database_engine(database_url)
        try:
            async with user_transaction(async_sessionmaker(engine), user_id) as session:
                return await session.scalar(
                    text(
                        """
                        SELECT count(DISTINCT s.external_id) FROM legal_sources s
                        JOIN legal_source_versions v ON v.legal_source_id = s.id
                        JOIN legal_chunks c ON c.legal_source_version_id = v.id
                        WHERE s.source_name = 'bdlaws.minlaw.gov.bd' AND v.review_status = 'approved'
                          AND c.embedding IS NOT NULL AND s.external_id IN
                          ('4','7','9','10','12','13','15','18','20','21','22','23','24')
                        """
                    )
                )
        finally:
            await engine.dispose()

    return asyncio.run(check()) == 13


@pytest.fixture(scope="module")
def lawyer_case():
    from tests.conftest import APP_ORIGIN  # noqa: F401  (conftest loads backend/.env)
    import os

    from app.config import Settings

    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url or not database_url.endswith("/legal_copilot_test"):
        pytest.skip("TEST_DATABASE_URL must point at legal_copilot_test")
    settings = Settings(app_env="test", database_url=database_url, app_origin="http://localhost:3000",
                        session_cookie_secure=True)
    client = TestClient(create_app(settings), base_url="https://testserver", client=("127.0.5.1", 50000))
    with client:
        user_id = UUID(register_login(client, "search-lawyer"))
        if not _fixture_ready(database_url, user_id):
            pytest.skip("legal_copilot_test lacks the 20 approved, embedded Acts (DOCS/status.md 7.9)")
        case_id = create_case(client, "SAMPLE-SEARCH")
        yield client, case_id, user_id, settings


def _search(client, case_id, **body):
    response = client.post(f"/api/v1/lawyer/cases/{case_id}/research/search", headers=ORIGIN, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _rank(results, act_id, section):
    for i, hit in enumerate(results, start=1):
        if hit["act_id"] == act_id and hit["section_number"] == section:
            return i
        if any(a["section_number"] == section for a in hit["alternates"]) and hit["act_id"] == act_id:
            return i
    return None


# ---------------------------------------------------------------- recall and behaviour
def test_recall_at_10_on_20_act_queries(lawyer_case):
    client, case_id, _, _ = lawyer_case
    ranks = []
    for q in QUERIES:
        body = _search(client, case_id, query=q["query"], incident_date=INCIDENT.isoformat(), k=10)
        ranks.append(_rank(body["results"], q["act_id"], q["section"]))
    hits = [r for r in ranks if r is not None]
    recall = len(hits) / len(QUERIES)
    mrr = sum(1 / r for r in hits) / len(QUERIES)
    misses = [q["query"][:60] for q, r in zip(QUERIES, ranks) if r is None]
    print(f"\nRecall@10 = {recall:.3f} ({len(hits)}/{len(QUERIES)}), MRR@10 = {mrr:.3f}, misses = {misses}")
    # Regression floor for the default (mock) reranker. Measured 2026-11-20: mock 29/30
    # (Divorce Act s.12 at rank 14); bge-reranker-v2-m3 30/30 but ~43 s/query on CPU.
    assert recall >= 0.95, misses


def test_nfc_variants_return_identical_results(lawyer_case):
    client, case_id, _, _ = lawyer_case
    precomposed = "ইসলামী বিশ্ববিদ্যালয়"  # য় as U+09DF
    decomposed = "ইসলামী বিশ্ববিদ্যালয়"  # য + nukta
    a = _search(client, case_id, query=precomposed, language="bn")
    b = _search(client, case_id, query=decomposed, language="bn")
    assert [h["chunk_id"] for h in a["results"]] == [h["chunk_id"] for h in b["results"]]
    assert a["results"] and a["results"][0]["language"] == "bn"
    assert a["results"][0]["sparse_rank"] is not None  # full-text matched despite the encoding difference


def test_repealed_act_excluded_and_results_are_flagged_unverified(lawyer_case):
    client, case_id, _, _ = lawyer_case
    body = _search(client, case_id, query="public gambling common gaming house", k=20)
    assert all(h["act_id"] != "16" for h in body["results"])  # Act 16 title carries [Repealed]
    assert "no_incident_date: in-force status not checked against a date" in body["warnings"]
    assert body["source_scope"] == "approved_statutes_only"
    for hit in body["results"]:
        assert hit["verification"] == "unverified" and hit["statement_type"] == "retrieved_source"
        assert "amendment_status_unknown" in hit["warnings"]  # scraper gives no status


def test_language_filter_and_canonical_dedupe(lawyer_case):
    client, case_id, _, _ = lawyer_case
    body = _search(client, case_id, query="police officer neglect of duty penalty", language="en")
    assert body["results"] and all(h["language"] == "en" for h in body["results"])
    canon = [h["canonical_section_id"] for h in body["results"]]
    assert len(canon) == len(set(canon))  # one result per section


def test_access_control_and_audit(lawyer_case):
    client, case_id, user_id, settings = lawyer_case
    path = f"/api/v1/lawyer/cases/{case_id}/research/search"
    query = f"SAMPLE secret query {secrets.token_hex(4)}"

    anonymous = TestClient(create_app(settings), base_url="https://testserver", client=("127.0.5.2", 50000))
    with anonymous:
        assert anonymous.post(path, headers=ORIGIN, json={"query": query}).status_code == 401

    other = TestClient(create_app(settings), base_url="https://testserver", client=("127.0.5.3", 50000))
    with other:
        register_login(other, "search-other-lawyer")
        assert other.post(path, headers=ORIGIN, json={"query": query}).status_code == 404  # not a member

    member_client = TestClient(create_app(settings), base_url="https://testserver", client=("127.0.5.4", 50000))
    with member_client:
        create_invite_and_accept(client, member_client, case_id, "search-client")
        assert member_client.post(path, headers=ORIGIN, json={"query": query}).status_code == 403

    assert client.post(path, headers=ORIGIN, json={"query": query, "k": 99}).status_code == 422
    _search(client, case_id, query=query)

    async def audit():
        engine = create_database_engine(settings.database_url)
        try:
            async with user_transaction(async_sessionmaker(engine), user_id) as session:
                rows = await session.execute(
                    text("SELECT details::text FROM audit_logs WHERE action = 'legal_research.searched' "
                         "AND case_id = :c"),
                    {"c": UUID(case_id)},
                )
                return [r[0] for r in rows]
        finally:
            await engine.dispose()

    details = asyncio.run(audit())
    assert details and all(query not in d for d in details)  # counts only, never the query


def test_bangla_stopwords_are_dropped_from_full_text(lawyer_case):
    client, case_id, user_id, settings = lawyer_case

    async def lexemes():
        engine = create_database_engine(settings.database_url)
        try:
            async with user_transaction(async_sessionmaker(engine), user_id) as session:
                return await session.scalar(
                    text("SELECT tsvector_to_array(to_tsvector('simple', :q))"), {"q": "এবং ধারা জন্য"}
                )
        finally:
            await engine.dispose()

    assert set(asyncio.run(lexemes())) == {"এবং", "ধারা", "জন্য"}  # whole-word lexemes, so filtering applies

    async def tsquery(q):
        engine = create_database_engine(settings.database_url)
        try:
            async with user_transaction(async_sessionmaker(engine), user_id) as session:
                value = await session.scalar(text(TSQUERY_SQL), {"qtext": q, "bn_stopwords": BN_STOPWORDS})
                return None if value is None else str(value)
        finally:
            await engine.dispose()

    assert asyncio.run(tsquery("এবং যে বা জন্য")) is None  # nothing left to match
    assert asyncio.run(tsquery("ইসলামী বিশ্ববিদ্যালয় এবং")) == asyncio.run(tsquery("ইসলামী বিশ্ববিদ্যালয়"))
    assert asyncio.run(tsquery("the punishment of the offence")) == asyncio.run(tsquery("punishment offence"))

    only_stopwords = _search(client, case_id, query="এবং যে বা জন্য", language="bn")
    assert all(h["sparse_rank"] is None for h in only_stopwords["results"])


BN_EVAL = Path(__file__).resolve().parents[1] / "data" / "retrieval_eval_bn.jsonl"
BN_RECALL_FLOOR = 0.90


def load_bn_eval() -> list[dict]:
    rows = [json.loads(line) for line in BN_EVAL.read_text("utf-8").splitlines() if line.strip()]
    return [r for r in rows if r.get("label") != "SAMPLE_DATA_NOT_REAL_LAW"]


def test_bn_eval_template_is_valid():
    rows = [json.loads(line) for line in BN_EVAL.read_text("utf-8").splitlines() if line.strip()]
    for row in rows:
        assert {"query", "act_id", "section"} <= set(row), row
        assert row.get("language") in (None, "bn", "en")
        if row.get("incident_date"):
            date.fromisoformat(row["incident_date"])


def test_recall_at_10_on_bangla_eval(lawyer_case):
    rows = load_bn_eval()
    if not rows:
        pytest.skip(f"No real queries yet in {BN_EVAL.name} (only SAMPLE_DATA_NOT_REAL_LAW rows)")
    client, case_id, user_id, settings = lawyer_case

    async def approved_sections():
        engine = create_database_engine(settings.database_url)
        try:
            async with user_transaction(async_sessionmaker(engine), user_id) as session:
                result = await session.execute(text(
                    "SELECT s.external_id, sec.section_number FROM legal_sections sec "
                    "JOIN legal_source_versions v ON v.id = sec.legal_source_version_id "
                    "JOIN legal_sources s ON s.id = v.legal_source_id "
                    "WHERE v.review_status = 'approved' AND v.is_current"
                ))
                return {(a, n) for a, n in result}
        finally:
            await engine.dispose()

    known = asyncio.run(approved_sections())
    unknown = [(r["act_id"], r["section"]) for r in rows if (r["act_id"], r["section"]) not in known]
    assert not unknown, f"Expected sections not approved in the test database: {unknown}"

    ranks = []
    for row in rows:
        body = {"query": row["query"], "k": 10}
        body.update({key: row[key] for key in ("language", "incident_date") if row.get(key)})
        ranks.append(_rank(_search(client, case_id, **body)["results"], row["act_id"], row["section"]))
    hits = [r for r in ranks if r is not None]
    recall, mrr = len(hits) / len(rows), sum(1 / r for r in hits) / len(rows)
    misses = [row["query"][:60] for row, r in zip(rows, ranks) if r is None]
    print(f"\nBangla Recall@10 = {recall:.3f} ({len(hits)}/{len(rows)}), MRR@10 = {mrr:.3f}, misses = {misses}")
    assert recall >= BN_RECALL_FLOOR, misses
