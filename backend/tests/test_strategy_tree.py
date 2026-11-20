"""Step E: strategy game tree. Facts are SAMPLE_DATA_NOT_REAL_LAW."""

import json
from uuid import UUID, uuid4

from app.rag.verifier import NO_PRECEDENT_NOTE
from app.strategy_tree.schemas import LegalBasisDraft, Ply1Draft, Ply2Draft, Ply3Draft, StrategyDraft
from app.strategy_tree.service import build_tree, compare_trees
from tests.step_c_helpers import ORIGIN, lawyer_with_case, new_client, sql_as
from tests.test_analysis import NEGLECT, WITHDRAW, add_fact, analyse
from tests.test_phase2_exit import create_invite_and_accept


def build(client, case_id, **body):
    response = client.post(f"/api/v1/lawyer/cases/{case_id}/strategy", headers=ORIGIN, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def walk(node):
    yield node
    for child in node["children"]:
        yield from walk(child)


def test_strategy_needs_an_analysis(api_client):
    _, case_id = lawyer_with_case(api_client, "strategy-none")
    assert api_client.post(f"/api/v1/lawyer/cases/{case_id}/strategy", headers=ORIGIN, json={}).status_code == 409


def test_tree_shape_verification_and_versions(api_client):
    _, case_id = lawyer_with_case(api_client, "strategy")
    add_fact(api_client, case_id, NEGLECT)
    add_fact(api_client, case_id, WITHDRAW)
    analysis = analyse(api_client, case_id, incident_date="2024-01-15")
    tree = build(api_client, case_id)
    assert tree["status"] == "succeeded" and tree["analysis_id"] == analysis["id"]
    assert tree["fact_set_hash"] == analysis["fact_set_hash"] and tree["precedent_note"] == NO_PRECEDENT_NOTE
    root = tree["root"]
    assert root["ply"] == 0 and root["statement_type"] == "case_state"
    assert 1 <= len(root["children"]) <= 4
    allowed = {s["chunk_id"] for s in analysis["retrieved_sources"]}
    plies = set()
    for node in walk(root):
        plies.add(node["ply"])
        if node["ply"] == 0:
            continue
        assert node["actor"] == ("us" if node["ply"] in (1, 3) else node["actor"])
        assert node["ply"] != 2 or node["actor"] in ("opponent", "court")
        assert len(node["children"]) <= 3 and node["ply"] <= 3
        for key in ("risk", "cost", "time"):
            assert node[key] in {"low", "medium", "high", "unknown"}
        assert node["strength"] in {"strong", "moderate", "weak", "insufficient"} and node["reasons"]
        for citation in node["legal_basis"]:
            assert citation["chunk_id"] in allowed
        assert node["verified"] == (bool(node["legal_basis"]) and all(c["verified"] for c in node["legal_basis"]))
    assert plies == {0, 1, 2, 3}
    assert any(n["verified"] for n in root["children"])
    assert "%" not in json.dumps(tree)

    second = build(api_client, case_id)
    assert (second["version"], second["supersedes_id"]) == (tree["version"] + 1, tree["id"])
    versions = api_client.get(f"/api/v1/lawyer/cases/{case_id}/strategy/versions").json()
    assert [v["version"] for v in versions] == [2, 1]
    diff = api_client.get(f"/api/v1/lawyer/cases/{case_id}/strategy/compare", params={"base": 1, "target": 2}).json()
    assert diff["added"] == [] and diff["removed"] == [] and diff["closed_options"] == []  # same inputs, same tree
    assert api_client.get(f"/api/v1/lawyer/cases/{case_id}/strategy/versions/1").json()["id"] == tree["id"]


def test_insufficient_analysis_gives_an_insufficient_tree(api_client):
    _, case_id = lawyer_with_case(api_client, "strategy-abstain")
    add_fact(api_client, case_id, "SAMPLE_DATA_NOT_REAL_LAW: the cake recipe needs vanilla frosting and chocolate.",
             category="other")
    analyse(api_client, case_id)
    tree = build(api_client, case_id)
    assert tree["status"] == "insufficient_information" and tree["root"]["children"] == []
    assert tree["missing_information"]


def test_every_node_is_verified_and_scrubbed():
    chunk_id, foreign = uuid4(), uuid4()
    text = "SAMPLE Act — Section 9: Sample\nWhoever neglects his duty shall be punished with a sample fine."
    chunks = {chunk_id: {"text": text, "title": "SAMPLE Act", "section_number": "9", "language": "en",
                         "source_url": "https://example.invalid", "section_status": "unknown",
                         "source_status": "unknown", "effective_from": None, "effective_to": None,
                         "review_status": "approved", "is_current": True}}
    good = [LegalBasisDraft(chunk_id=chunk_id, quote="neglects his duty")]
    draft = StrategyDraft(moves=[Ply1Draft(
        actor="us", move="File on neglect; 80% chance (see 12 DLR 34)", legal_basis=good, requirements=[],
        risk="low", cost="low", time="low", strength="strong", reasons=["Rahim vs State supports this"],
        children=[Ply2Draft(actor="court", move="Court asks for proof", legal_basis=[LegalBasisDraft(
            chunk_id=foreign, quote="anything")], requirements=[], risk="medium", cost="unknown", time="unknown",
            strength="moderate", reasons=["r"], children=[Ply3Draft(
                actor="us", move="Give proof", legal_basis=[LegalBasisDraft(chunk_id=chunk_id, quote="not in text")],
                requirements=[], risk="low", cost="low", time="low", strength="strong", reasons=["r"])])])],
        missing_information=[])
    root, summary = build_tree(draft, chunks, {chunk_id}, None, False, "state")
    move = root["children"][0]
    response, counter = move["children"][0], move["children"][0]["children"][0]
    assert move["verified"] and "%" not in move["move"] and "DLR" not in move["move"]
    assert "Rahim vs State" not in move["reasons"][0]
    assert {"probability_language_removed", "precedent_reference_removed"} <= set(summary["scrub_flags"])
    assert response["legal_basis"] == [] and not response["verified"] and summary["citations_stripped"] == 1
    assert not counter["verified"] and counter["strength"] == "insufficient"
    assert "quote_not_in_source" in counter["legal_basis"][0]["failures"]


def test_compare_reports_closed_and_new_options():
    def tree(version, moves):
        return {"version": version, "root": {"ply": 0, "actor": "us", "move": "s", "children": [
            {"ply": 1, "actor": "us", "move": m, "strength": "moderate", "risk": "medium", "cost": "unknown",
             "time": "unknown", "verified": True, "children": []} for m in moves]}}

    diff = compare_trees(tree(1, ["Option A", "Option B"]), tree(2, ["Option B", "Option C"]))
    assert diff["closed_options"] == ["Option A"] and diff["new_options"] == ["Option C"]


def test_strategy_isolation(api_client):
    _, case_id = lawyer_with_case(api_client, "strategy-iso")
    add_fact(api_client, case_id, NEGLECT)
    analyse(api_client, case_id)
    tree = build(api_client, case_id)
    database_url = api_client.app.state.settings.database_url
    other = new_client(api_client, 31)
    with other:
        other_id, _ = lawyer_with_case(other, "strategy-other")
        for path in ("", "/versions", "/versions/1", "/compare?base=1&target=1"):
            assert other.get(f"/api/v1/lawyer/cases/{case_id}/strategy{path}").status_code == 404
        assert other.post(f"/api/v1/lawyer/cases/{case_id}/strategy", headers=ORIGIN, json={}).status_code == 404
    assert sql_as(database_url, other_id, "SELECT count(*) FROM public.strategy_trees WHERE case_id = :c",
                  c=case_id)[0][0] == 0
    client = new_client(api_client, 32)
    with client:
        create_invite_and_accept(api_client, client, case_id, "strategy-client")
        client_id = UUID(client.get("/api/v1/me").json()["id"])
        assert client.get(f"/api/v1/lawyer/cases/{case_id}/strategy").status_code == 403
    assert sql_as(database_url, client_id, "SELECT count(*) FROM public.strategy_trees WHERE id = :i",
                  i=tree["id"])[0][0] == 0
