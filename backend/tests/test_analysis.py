"""Step D: case analysis. Facts are SAMPLE_DATA_NOT_REAL_LAW; statutes are the approved test-DB Acts."""

import asyncio
import json
from uuid import UUID, uuid4

import httpx
import pytest

from app.ai.structured import generate_structured
from app.case_analysis.schemas import AnalysisDraft, ElementDraft, FindingDraft
from app.case_analysis.service import _verify
from app.rag.verifier import NO_PRECEDENT_NOTE
from tests.step_c_helpers import ORIGIN, lawyer_with_case, new_client, sql_as
from tests.test_phase2_exit import create_invite_and_accept

NEGLECT = ("SAMPLE_DATA_NOT_REAL_LAW: the police officer on duty neglected his duty and refused to "
           "record the complaint at the police station.")
WITHDRAW = "SAMPLE_DATA_NOT_REAL_LAW: the police officer withdrew from the duties of his office without permission."


def add_fact(client, case_id, statement, category="act_or_omission"):
    response = client.post(f"/api/v1/lawyer/cases/{case_id}/facts", headers=ORIGIN,
                           json={"category": category, "statement": statement})
    assert response.status_code == 201, response.text
    return response.json()


def analyse(client, case_id, **body):
    response = client.post(f"/api/v1/lawyer/cases/{case_id}/analysis", headers=ORIGIN, json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def ready_case(api_client):
    user_id, case_id = lawyer_with_case(api_client, "analysis")
    add_fact(api_client, case_id, NEGLECT)
    add_fact(api_client, case_id, WITHDRAW)
    return user_id, case_id


def test_analysis_needs_confirmed_facts(api_client):
    _, case_id = lawyer_with_case(api_client, "analysis-empty")
    response = api_client.post(f"/api/v1/lawyer/cases/{case_id}/analysis", headers=ORIGIN, json={})
    assert response.status_code == 409


def test_analysis_findings_are_verified_versioned_and_tied_to_the_fact_set(api_client, ready_case):
    _, case_id = ready_case
    analysis = analyse(api_client, case_id, incident_date="2024-01-15")
    assert analysis["status"] == "succeeded", analysis["abstain_reason"]
    assert analysis["origin"] == "ai_mock" and analysis["review_status"] == "draft"
    confirmed = api_client.get(f"/api/v1/lawyer/cases/{case_id}/facts/confirmed").json()
    assert analysis["fact_set_hash"] == confirmed["fact_set_hash"]
    assert set(analysis["fact_ids"]) == {f["id"] for f in confirmed["facts"]}
    assert any("Police Act" in s["act_title"] for s in analysis["retrieved_sources"])
    assert analysis["precedent_note"] == NO_PRECEDENT_NOTE

    verified = [f for f in analysis["findings"] if f["verification"] == "verified"]
    assert verified
    for finding in verified:
        assert finding["statement_type"] == "ai_inference"
        assert finding["section_citation"]["verified"] is True and not finding["section_citation"]["failures"]
        assert finding["strength"] in {"strong", "moderate", "weak", "insufficient"} and finding["reasons"]
        for element in finding["elements"]:
            assert element["verified"]
            assert (element["status"] == "met") == (element["matched_fact_id"] is not None) or element["status"] == "disputed"
            if element["matched_fact_id"]:
                assert element["matched_fact_id"] in analysis["fact_ids"]
    assert "%" not in json.dumps(analysis) and "probabilit" not in json.dumps(analysis).lower()

    second = analyse(api_client, case_id, incident_date="2024-01-15")
    assert (second["version"], second["supersedes_id"]) == (analysis["version"] + 1, analysis["id"])
    versions = api_client.get(f"/api/v1/lawyer/cases/{case_id}/analysis/versions").json()
    assert [v["version"] for v in versions] == [2, 1]
    first_again = api_client.get(f"/api/v1/lawyer/cases/{case_id}/analysis/versions/1").json()
    assert first_again["id"] == analysis["id"] and first_again["findings"] == analysis["findings"]
    assert api_client.get(f"/api/v1/lawyer/cases/{case_id}/analysis").json()["id"] == second["id"]


def test_analysis_abstains_without_relevant_law(api_client):
    _, case_id = lawyer_with_case(api_client, "analysis-abstain")
    add_fact(api_client, case_id, "SAMPLE_DATA_NOT_REAL_LAW: the cake recipe needs vanilla frosting and chocolate.",
             category="other")
    analysis = analyse(api_client, case_id)
    assert analysis["status"] == "insufficient_information"
    assert analysis["findings"] == [] and "insufficient_information" in analysis["abstain_reason"]
    assert analysis["missing_information"]


def test_verifier_strips_and_labels():
    chunk_id, other_chunk, fact_id = uuid4(), uuid4(), uuid4()
    text = ("SAMPLE Act — Section 9: Sample\nWhoever, being a SAMPLE officer, neglects his duty shall be punished "
            "with a sample fine.")
    chunks = {chunk_id: {"text": text, "title": "SAMPLE Act", "section_number": "9", "language": "en",
                         "source_url": "https://example.invalid", "section_status": "unknown", "source_status": "unknown",
                         "effective_from": None, "effective_to": None, "review_status": "approved", "is_current": True}}
    element = ElementDraft(element="officer neglects duty", element_quote="neglects his duty",
                           matched_fact_id=uuid4(), status="met")  # fact id not in the confirmed set
    good = FindingDraft(offence_or_claim="Neglect (see 12 DLR 34)", chunk_id=chunk_id, quote="neglects his duty",
                        elements=[element], strength="strong", reasons=["About 90% likely to succeed"])
    bad_quote = FindingDraft(offence_or_claim="x", chunk_id=chunk_id, quote="words not in the provision at all",
                             elements=[ElementDraft(element="y", element_quote="not in text either",
                                                    matched_fact_id=fact_id, status="met")],
                             strength="strong", reasons=["r"])
    not_retrieved = FindingDraft(offence_or_claim="z", chunk_id=other_chunk, quote="q", elements=[element],
                                 strength="weak", reasons=["r"])
    findings, summary = _verify(AnalysisDraft(findings=[good, bad_quote, not_retrieved], missing_information=[]),
                                chunks, {fact_id}, None, {chunk_id}, precedents=False)
    assert summary["stripped_not_retrieved"] == 1 and len(findings) == 2
    first, second = findings
    assert first["verification"] == "verified" and first["elements"][0]["matched_fact_id"] is None
    assert first["elements"][0]["status"] == "missing" and summary["fact_links_removed"] == 1
    assert "DLR" not in first["offence_or_claim"] and "%" not in " ".join(first["reasons"])
    assert {"probability_language_removed", "precedent_reference_removed"} <= set(summary["scrub_flags"])
    assert second["verification"] == "unverified" and second["strength"] == "insufficient"
    assert "quote_not_in_source" in second["section_citation"]["failures"]


class FakeLLM:
    provider, model = "gemini", "fake"

    def __init__(self, outputs):
        self.outputs = list(outputs)

    def complete_json(self, system, user, name, schema):
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def test_structured_generation_retries_then_falls_back_to_labelled_mock():
    valid = json.dumps({"findings": [], "missing_information": ["SAMPLE"]})
    mock = lambda: AnalysisDraft(findings=[], missing_information=["mock"])  # noqa: E731
    ok = asyncio.run(generate_structured(FakeLLM(["not json", valid]), AnalysisDraft, "s", "u", mock, True))
    assert (ok.origin, ok.attempts, ok.value.missing_information) == ("ai", 2, ["SAMPLE"])
    request = httpx.Request("POST", "http://x")
    down = asyncio.run(generate_structured(
        FakeLLM([httpx.HTTPStatusError("503", request=request, response=httpx.Response(503, request=request))]),
        AnalysisDraft, "s", "u", mock, True))
    assert down.origin == "ai_mock" and "fallback_to_mock" in down.warnings
    with pytest.raises(Exception):
        asyncio.run(generate_structured(FakeLLM(["bad", "bad"]), AnalysisDraft, "s", "u", mock, False))


def test_analysis_isolation(api_client, ready_case):
    owner_id, case_id = ready_case
    analysis = analyse(api_client, case_id)
    database_url = api_client.app.state.settings.database_url
    other = new_client(api_client, 21)
    with other:
        other_id, _ = lawyer_with_case(other, "analysis-other")
        assert other.get(f"/api/v1/lawyer/cases/{case_id}/analysis").status_code == 404
        assert other.post(f"/api/v1/lawyer/cases/{case_id}/analysis", headers=ORIGIN, json={}).status_code == 404
        assert other.get(f"/api/v1/lawyer/cases/{case_id}/analysis/versions/1").status_code == 404
    assert sql_as(database_url, other_id, "SELECT count(*) FROM public.case_analyses WHERE case_id = :c",
                  c=case_id)[0][0] == 0
    client = new_client(api_client, 22)
    with client:
        create_invite_and_accept(api_client, client, case_id, "analysis-client")
        client_id = UUID(client.get("/api/v1/me").json()["id"])
        assert client.get(f"/api/v1/lawyer/cases/{case_id}/analysis").status_code == 403
    assert sql_as(database_url, client_id, "SELECT count(*) FROM public.case_analyses WHERE id = :i",
                  i=analysis["id"])[0][0] == 0


class _QuotaExhausted:
    """An e5-labelled embedder whose API answers 429 (like the Gemini free tier when the quota is used up)."""

    from app.rag.ingest.chunking import EMBEDDING_MODEL as model_name, EMBEDDING_VERSION as embedding_version

    def embed_query(self, query):
        from app.rag.search.errors import EmbeddingUnavailable

        raise EmbeddingUnavailable("Gemini answered HTTP 429")


def test_analysis_falls_back_to_keyword_search_and_is_labelled(api_client, monkeypatch):
    from app.case_analysis import router as analysis_router
    from app.rag.search.retrieval import KEYWORD_ONLY_WARNING

    monkeypatch.setattr(analysis_router, "get_query_embedder", lambda: _QuotaExhausted())
    _, case_id = lawyer_with_case(api_client, "analysis-keyword-only")
    add_fact(api_client, case_id, NEGLECT)
    analysis = analyse(api_client, case_id)
    assert KEYWORD_ONLY_WARNING in analysis["warnings"]
    assert analysis["retrieved_sources"], "keyword matches must still reach the analysis"
    assert any("Police" in s["act_title"] for s in analysis["retrieved_sources"])


def test_cake_still_abstains_in_keyword_only_mode(api_client, monkeypatch):
    from app.case_analysis import router as analysis_router

    monkeypatch.setattr(analysis_router, "get_query_embedder", lambda: _QuotaExhausted())
    _, case_id = lawyer_with_case(api_client, "analysis-keyword-abstain")
    add_fact(api_client, case_id, "SAMPLE_DATA_NOT_REAL_LAW: the cake recipe needs vanilla frosting and chocolate.",
             category="other")
    assert analyse(api_client, case_id)["status"] == "insufficient_information"


def test_keyword_support_counts_distinct_content_words():
    from app.case_analysis.service import keyword_support

    statute = "Every police officer who shall neglect or refuse to record a complaint at a police station ..."
    assert keyword_support(NEGLECT, statute) >= 3  # police, officer, record, complaint, station
    cake = "SAMPLE_DATA_NOT_REAL_LAW: the cake recipe needs vanilla frosting and chocolate."
    assert keyword_support(cake, "This Act is the law of the land; section 2 applies to every sample.") == 0
    bn = "পুলিশ কর্মকর্তা থানায় অভিযোগ লিপিবদ্ধ করতে অস্বীকার করেছেন।"
    assert keyword_support(bn, "যে পুলিশ কর্মকর্তা থানায় অভিযোগ লিপিবদ্ধ করিতে অস্বীকার করেন") >= 3
