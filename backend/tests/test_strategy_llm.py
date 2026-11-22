"""Strategy with an LLM: flat node list -> 3-ply tree, repair, verifier on every node, labelled mock.

The API test drives the real GeminiLLM code path over a mocked HTTP transport. The live test
(LIVE_LLM_TEST=1 with GEMINI_API_KEY/GEMINI_MODEL and a knowledge base with the Negotiable
Instruments Act) builds a real Gemini strategy for the SAMPLE_DATA_NOT_REAL_LAW cheque case.
"""

import json
import os
import re
import secrets
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from psycopg2 import connect

from app.main import create_app
from app.strategy_tree.schemas import FlatLegalBasis, FlatNode, StrategyFlatDraft
from app.strategy_tree.service import flatten, mock_strategy, nest_nodes
from tests.step_c_helpers import ORIGIN, lawyer_with_case
from tests.test_analysis import NEGLECT, WITHDRAW, add_fact, analyse
from tests.test_strategy_tree import walk

CHUNK = str(uuid4())


def node(node_id, parent, actor, chunk=CHUNK, **extra):
    return FlatNode(id=node_id, parent_id=parent, actor=actor, move=f"SAMPLE move {node_id}",
                    legal_basis=[FlatLegalBasis(chunk_id=chunk, quote="SAMPLE quote")], requirements=[],
                    risk="medium", cost="unknown", time="unknown", strength="moderate",
                    reasons=["SAMPLE reason"], **extra)


def test_flat_nodes_rebuild_three_plies_and_drop_what_does_not_fit():
    flat = StrategyFlatDraft(nodes=[
        node("m1", None, "us"), node("m1r1", "m1", "opponent"), node("m1r1c1", "m1r1", "us"),
        node("m1r2", "m1", "court"), node("m1r2c1", "m1r2", "us", chunk="not-a-uuid"),
        node("x1", "m1", "us"),            # ply 2 must be the opponent or the court
        node("orphan", "missing", "us"),   # no such parent
        node("m1", None, "us"),            # duplicate id
        node("o1", None, "opponent"),      # ply 1 must be ours
    ], missing_information=["SAMPLE"])
    draft, warnings = nest_nodes(flat)
    assert len(draft.moves) == 1
    responses = draft.moves[0].children
    assert [(r.actor, len(r.children)) for r in responses] == [("opponent", 1), ("court", 1)]
    assert responses[1].children[0].legal_basis == []  # an invalid chunk id is dropped, not trusted
    assert "strategy_nodes_dropped:4" in warnings and "strategy_invalid_chunk_ids:1" in warnings


def test_mock_round_trips_through_the_flat_form():
    finding = {"verification": "verified", "strength": "moderate", "offence_or_claim": "SAMPLE claim",
               "section_citation": {"chunk_id": CHUNK, "quote": "SAMPLE quote"},
               "elements": [{"element": "SAMPLE element", "status": "missing", "element_quote": "SAMPLE q"}]}
    nested = mock_strategy([finding])
    rebuilt, warnings = nest_nodes(flatten(nested))
    assert rebuilt == nested and warnings == []


def _provisions(prompt: str) -> list[tuple[str, str]]:
    return re.findall(r'<provision chunk_id="([0-9a-f-]+)">(.*?)</provision>', prompt, flags=re.S)


def _flat_tree(prompt: str) -> dict:
    chunk_id, text = _provisions(prompt)[0]
    quote = next(line.strip() for line in text.splitlines() if len(line.strip()) > 30 and "&lt;" not in line)[:120]

    def make(node_id, parent, actor):
        return {"id": node_id, "parent_id": parent, "actor": actor, "move": f"SAMPLE_DATA_NOT_REAL_LAW {node_id}",
                "legal_basis": [{"chunk_id": chunk_id, "quote": quote}], "requirements": ["SAMPLE evidence"],
                "risk": "medium", "cost": "unknown", "time": "unknown", "strength": "moderate",
                "reasons": ["SAMPLE reason grounded in the given provision"]}

    return {"nodes": [make("m1", None, "us"), make("m1r1", "m1", "opponent"), make("m1r1c1", "m1r1", "us"),
                      make("m1r2", "m1", "court"), make("m1r2c1", "m1r2", "us")],
            "missing_information": []}


def test_strategy_uses_gemini_with_repair_and_verifies_every_node(api_client, caplog):
    _, case_id = lawyer_with_case(api_client, "strategy-llm")
    add_fact(api_client, case_id, NEGLECT)
    add_fact(api_client, case_id, WITHDRAW)
    analyse(api_client, case_id, incident_date="2024-01-15")  # mock analysis with verified findings
    calls = []

    def gemini(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        prompt = body["contents"][0]["parts"][0]["text"]
        schema = body["generationConfig"]["responseJsonSchema"]
        calls.append(prompt)
        assert "nodes" in schema["properties"] and "children" not in json.dumps(schema)  # flat schema
        tree = _flat_tree(prompt)
        if len(calls) == 1:
            del tree["nodes"][0]["reasons"]  # an invalid first answer: repaired once
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(tree)}]}}]})

    settings = api_client.app.state.settings.model_copy(update={
        "llm_provider": "gemini", "llm_approved_providers": "gemini,mock", "llm_fallback_chain": "gemini,mock",
        "gemini_api_key": SecretStr("test-key"), "gemini_model": "gemini-sample"})
    app = create_app(settings)
    app.state.llm_transport = httpx.MockTransport(gemini)
    with TestClient(app, base_url="https://testserver") as client, caplog.at_level("INFO", logger="pokkhoai"):
        client.cookies = api_client.cookies
        response = client.post(f"/api/v1/lawyer/cases/{case_id}/strategy", headers=ORIGIN, json={})
    assert response.status_code == 201, response.text
    tree = response.json()
    assert (tree["origin"], tree["provider"], tree["status"]) == ("ai", "gemini", "succeeded")
    assert len(calls) == 2 and "<validation_errors>" in calls[1] and "nodes.0.reasons" in calls[1]
    plies = {n["ply"] for n in walk(tree["root"])}
    assert plies == {0, 1, 2, 3}  # our move -> opponent/court -> our counter
    first = tree["root"]["children"][0]
    assert first["children"][0]["actor"] == "opponent" and first["children"][0]["children"][0]["actor"] == "us"
    for item in walk(tree["root"]):
        if item["ply"]:
            assert item["verified"] and item["legal_basis"][0]["verified"]  # the verifier ran on every node
    assert any(getattr(r, "event", "") == "llm.answered" and r.provider == "gemini" for r in caplog.records)
    assert calls[0] not in caplog.text


def _unverify_elements(case_id: str) -> None:
    """Make the stored analysis look like the live one: citations verified, element quotes not found."""
    with connect(host="localhost", port=5433, user="postgres", password="local-development-placeholder",
                 dbname="legal_copilot_test") as conn, conn.cursor() as cur:
        cur.execute("SELECT id, result FROM public.case_analyses WHERE case_id = %s ORDER BY version DESC LIMIT 1",
                    (case_id,))
        analysis_id, result = cur.fetchone()
        for finding in result["findings"]:
            finding["verification"], finding["strength"] = "unverified", "insufficient"
            for element in finding["elements"]:
                element["verified"], element["element_quote"] = False, None
        assert all(f["section_citation"]["verified"] for f in result["findings"])
        cur.execute("UPDATE public.case_analyses SET result = %s WHERE id = %s", (json.dumps(result), analysis_id))


def test_root_cause_unverified_elements_no_longer_skip_the_llm(api_client, caplog):
    """Live bug: a real-model analysis had verified citations but unlocatable element quotes, so every
    finding was 'unverified'; strategy then never called the LLM and stored a one-node ai_mock tree."""
    _, case_id = lawyer_with_case(api_client, "strategy-root-cause")
    add_fact(api_client, case_id, NEGLECT)
    add_fact(api_client, case_id, WITHDRAW)
    analyse(api_client, case_id, incident_date="2024-01-15")
    _unverify_elements(case_id)
    calls = []

    def gemini(request: httpx.Request) -> httpx.Response:
        prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        calls.append(prompt)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [
            {"text": json.dumps(_flat_tree(prompt))}]}}]})

    settings = api_client.app.state.settings.model_copy(update={
        "llm_approved_providers": "gemini,mock", "llm_fallback_chain": "gemini,mock",
        "gemini_api_key": SecretStr("test-key"), "gemini_model": "gemini-sample"})
    app = create_app(settings)
    app.state.llm_transport = httpx.MockTransport(gemini)
    with TestClient(app, base_url="https://testserver") as client:
        client.cookies = api_client.cookies
        tree = client.post(f"/api/v1/lawyer/cases/{case_id}/strategy", headers=ORIGIN, json={}).json()
    assert len(calls) == 1 and '"verification": "unverified"' in calls[0]  # the model sees what is unproven
    assert tree["origin"] == "ai" and {n["ply"] for n in walk(tree["root"])} == {0, 1, 2, 3}


def test_strategy_without_verified_citation_logs_why_the_llm_was_not_called(api_client, caplog):
    _, case_id = lawyer_with_case(api_client, "strategy-skip-log")
    add_fact(api_client, case_id, NEGLECT)
    analyse(api_client, case_id, incident_date="2024-01-15")
    with connect(host="localhost", port=5433, user="postgres", password="local-development-placeholder",
                 dbname="legal_copilot_test") as conn, conn.cursor() as cur:
        cur.execute("UPDATE public.case_analyses SET result = jsonb_set(result, '{findings}', '[]') "
                    "WHERE case_id = %s", (case_id,))
    with caplog.at_level("INFO", logger="pokkhoai"):
        tree = api_client.post(f"/api/v1/lawyer/cases/{case_id}/strategy", headers=ORIGIN, json={}).json()
    assert tree["origin"] == "ai_mock" and "llm_not_called:no_finding_with_verified_citation" in tree["warnings"]
    assert any(getattr(r, "reason", "") == "strategy:no_finding_with_verified_citation" for r in caplog.records)


CHEQUE_FACTS = [
    ("party", "SAMPLE_DATA_NOT_REAL_LAW: Abdur Rahim, proprietor of Rahim Traders, is the payee and holder of the "
              "cheque."),
    ("act_or_omission", "SAMPLE_DATA_NOT_REAL_LAW: On 5 April 2026 Karim Uddin drew cheque No. 0045871 dated 10 April "
                        "2026 for Tk 5,00,000 on his account at Sonali Bank to pay a debt to Rahim Traders."),
    ("act_or_omission", "SAMPLE_DATA_NOT_REAL_LAW: On 22 April 2026 the bank returned the cheque unpaid for "
                        "insufficient funds."),
    ("act_or_omission", "SAMPLE_DATA_NOT_REAL_LAW: On 5 May 2026 Abdur Rahim sent Karim Uddin a written notice "
                        "demanding payment of Tk 5,00,000, which Karim Uddin received on 8 May 2026."),
    ("act_or_omission", "SAMPLE_DATA_NOT_REAL_LAW: Karim Uddin did not pay within thirty days of receiving the "
                        "notice."),
]


@pytest.mark.skipif(os.environ.get("LIVE_LLM_TEST") != "1", reason="live Gemini test: set LIVE_LLM_TEST=1")
def test_live_gemini_strategy_for_the_cheque_case(api_client):
    key, model = os.environ.get("GEMINI_API_KEY"), os.environ.get("GEMINI_MODEL")
    if not key or not model:
        pytest.skip("GEMINI_API_KEY and GEMINI_MODEL are required")
    settings = api_client.app.state.settings.model_copy(update={
        "llm_provider": "gemini", "llm_approved_providers": "gemini,mock", "llm_fallback_chain": "gemini,mock",
        "gemini_api_key": SecretStr(key), "gemini_model": model,
        "gemini_fallback_model": os.environ.get("GEMINI_FALLBACK_MODEL")})
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        _, case_id = lawyer_with_case(client, f"cheque-{secrets.token_hex(2)}")
        for category, statement in CHEQUE_FACTS:
            add_fact(client, case_id, statement, category)
        analysis = analyse(client, case_id, incident_date="2026-04-22")
        if not any(f["verification"] == "verified" for f in analysis["findings"]):
            pytest.skip("this knowledge base has no verified finding for the cheque case")
        response = client.post(f"/api/v1/lawyer/cases/{case_id}/strategy", headers=ORIGIN, json={})
        assert response.status_code == 201, response.text
        tree = response.json()
    assert tree["origin"] == "ai", tree["warnings"]
    plies = {n["ply"] for n in walk(tree["root"])}
    assert {1, 2, 3} <= plies, tree["warnings"]  # our move -> opponent -> our counter
