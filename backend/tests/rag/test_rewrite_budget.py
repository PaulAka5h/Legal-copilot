"""Gemini budget for query rewriting: batching, caching, no retries, cooldown.

Fake LLM, no network. The cache-table tests use the local Compose database
(TEST_DATABASE_URL) and check organization isolation. SAMPLE_DATA_NOT_REAL_LAW.
"""

import asyncio
import json
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.case_analysis import service as analysis
from app.case_analysis.analyzer import FactInput
from app.database import create_database_engine, user_transaction
from app.rag.search import retrieval
from app.rag.search.query_rewrite import BATCH_SYSTEM, SYSTEM, QueryRewriter, resolve_rewrites
from app.rag.search.retrieval import REWRITE_FAILED_WARNING, SearchResult

SAMPLE = "SAMPLE_DATA_NOT_REAL_LAW"


def _variants(i):
    return {"bangla": f"বাংলা {i}", "english": f"english {i}", "keywords": [f"kw{i}", "term"]}


class FakeLLM:
    model = "fake-model"

    def __init__(self, error=None, items=None):
        self.calls, self.error, self.items = [], error, items

    def complete_json(self, system, user, schema_name, schema):
        self.calls.append((system, user, schema_name))
        if self.error:
            raise self.error
        if system == BATCH_SYSTEM:
            statements = json.loads(user)
            count = len(statements) if self.items is None else self.items
            return json.dumps({"items": [_variants(i) for i in range(count)]})
        return json.dumps(_variants("s"))


def _status(code):
    return httpx.HTTPStatusError(str(code), request=httpx.Request("POST", "https://x"),
                                 response=httpx.Response(code))


def facts(n):
    return [f"{SAMPLE} fact number {i} about a dishonoured cheque" for i in range(n)]


def test_ten_facts_are_rewritten_in_one_call_and_then_cost_nothing():
    llm = FakeLLM()
    rewriter = QueryRewriter(llm)
    rewrites, calls = rewriter.rewrite_many(facts(10))
    assert calls == 1 and len(llm.calls) == 1 and llm.calls[0][0] == BATCH_SYSTEM
    assert json.loads(llm.calls[0][1]) == facts(10)  # statements go as a JSON list: data, not instructions
    assert [r.queries[1] for r in rewrites] == [f"বাংলা {i}" for i in range(10)]  # input order kept
    again, calls = rewriter.rewrite_many(facts(10))
    assert calls == 0 and len(llm.calls) == 1 and [r.queries for r in again] == [r.queries for r in rewrites]


def test_only_new_facts_go_to_the_llm_and_a_single_one_uses_the_search_prompt():
    llm = FakeLLM()
    rewriter = QueryRewriter(llm)
    rewriter.rewrite_many(facts(3))
    _, calls = rewriter.rewrite_many([*facts(3), f"{SAMPLE} a new fact"])
    assert calls == 1 and llm.calls[-1][0] == SYSTEM and llm.calls[-1][1] == f"{SAMPLE} a new fact"


def test_a_batch_with_the_wrong_item_count_falls_back_for_every_fact():
    llm = FakeLLM(items=2)
    rewrites, calls = QueryRewriter(llm).rewrite_many(facts(4))
    assert calls == 1 and all(r.failed and len(r.queries) == 1 for r in rewrites)


@pytest.mark.parametrize("error", [_status(429), _status(503), httpx.ReadTimeout("slow")])
def test_rate_limit_is_not_retried_and_pauses_rewriting(error):
    now = [0.0]
    llm = FakeLLM(error=error)
    rewriter = QueryRewriter(llm, cooldown=60, clock=lambda: now[0])
    first = rewriter.rewrite(f"{SAMPLE} query")
    assert first.failed and first.queries == [f"{SAMPLE} query"] and len(llm.calls) == 1  # no retry
    skipped, calls = rewriter.rewrite_many(facts(5))
    assert calls == 0 and len(llm.calls) == 1 and all(r.failed for r in skipped)  # no wait, no call
    now[0] = 61.0
    llm.error = None
    assert not rewriter.rewrite(f"{SAMPLE} query").failed and len(llm.calls) == 2


def test_invalid_output_does_not_pause_rewriting():
    llm = FakeLLM(items=1)
    rewriter = QueryRewriter(llm, cooldown=60, clock=lambda: 0.0)
    rewriter.rewrite_many(facts(2))
    rewriter.rewrite_many(facts(2))
    assert len(llm.calls) == 2


def test_an_analysis_with_ten_facts_makes_one_rewrite_call(monkeypatch):
    async def fake_search(session, *, query, **kwargs):
        return SearchResult([], [], "mock", "m", 1)

    monkeypatch.setattr(retrieval, "hybrid_search", fake_search)
    monkeypatch.setattr(analysis, "hybrid_search", fake_search)
    llm = FakeLLM()
    calls = [0]
    rows = [FactInput(uuid4(), s, "event", "lawyer_entered", "undisputed") for s in facts(10)]
    asyncio.run(analysis._retrieve(None, rows, None, None, None, None, rewriter=QueryRewriter(llm), llm_calls=calls))
    assert calls[0] == 1 and len(llm.calls) == 1


def test_a_failed_batch_marks_the_analysis_search_as_plain(monkeypatch):
    async def fake_search(session, *, query, **kwargs):
        return SearchResult([], [], "mock", "m", 1)

    monkeypatch.setattr(retrieval, "hybrid_search", fake_search)
    monkeypatch.setattr(analysis, "hybrid_search", fake_search)
    rows = [FactInput(uuid4(), s, "event", "lawyer_entered", "undisputed") for s in facts(3)]
    _, warnings = asyncio.run(analysis._retrieve(None, rows, None, None, None, None,
                                                 rewriter=QueryRewriter(FakeLLM(error=_status(429)))))
    assert REWRITE_FAILED_WARNING in warnings


def test_cache_key_is_nfc_and_whitespace_insensitive():
    rewriter = QueryRewriter(FakeLLM())
    decomposed, composed = "চেকো", "চেকো"  # e + aa composes to o-kar
    assert rewriter.cache_key(f"  {decomposed} ") == rewriter.cache_key(composed)
    assert len(rewriter.cache_key("x")) == 64


# ---------------------------------------------------------------- per-organization store (database)
def _run(database_url, user_id, coro_fn):
    async def go():
        engine = create_database_engine(database_url)
        try:
            async with user_transaction(async_sessionmaker(engine), user_id) as session:
                return await coro_fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(go())


def test_stored_rewrites_are_reused_and_isolated_by_organization(api_client, local_app_user_database_url):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.step_c_helpers import lawyer_with_case

    owner, case = lawyer_with_case(api_client, "rewrite-a")
    other_client = TestClient(create_app(api_client.app.state.settings), base_url="https://testserver")
    with other_client:
        stranger, other_case = lawyer_with_case(other_client, "rewrite-b")
    statements = facts(4)
    first = QueryRewriter(FakeLLM())
    _, calls = _run(local_app_user_database_url, owner,
                    lambda s: resolve_rewrites(s, first, statements, UUID(case)))
    assert calls == 1

    # A new process (empty memory cache) in the same organization: no LLM call at all.
    fresh_llm = FakeLLM()
    rewrites, calls = _run(local_app_user_database_url, owner,
                           lambda s: resolve_rewrites(s, QueryRewriter(fresh_llm), statements, UUID(case)))
    assert calls == 0 and fresh_llm.calls == [] and rewrites[0].queries[1] == "বাংলা 0"

    # Another organization cannot read those rows: it pays for its own call.
    other_llm = FakeLLM()
    _, calls = _run(local_app_user_database_url, stranger,
                    lambda s: resolve_rewrites(s, QueryRewriter(other_llm), statements, UUID(other_case)))
    assert calls == 1

    # And the owner's lookup through someone else's case id finds nothing (RLS on cases + rewrites).
    probe_llm = FakeLLM()
    _, calls = _run(local_app_user_database_url, stranger,
                    lambda s: resolve_rewrites(s, QueryRewriter(probe_llm), statements, UUID(case)))
    assert calls == 1
