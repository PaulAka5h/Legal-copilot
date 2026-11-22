"""Fact quotes: sentence splitting, shared quote normalization, exact spans, confirm errors.

All case content is SAMPLE_DATA_NOT_REAL_LAW (tests/data/case1_cheque_dishonour.pdf is a
synthetic brief labelled as such on its first line).
"""

from pathlib import Path
from uuid import uuid4

from app.facts.extractor import PageInput
from app.facts.sentences import sentence_spans
from app.facts.service import check_quote
from app.rag.quote_locator import locate_normalized
from tests.step_c_helpers import ORIGIN, lawyer_with_case, sql_as, upload
from tests.test_facts import extract, facts_url

PDF = Path(__file__).parent / "data" / "case1_cheque_dishonour.pdf"


def sentences(text: str) -> list[str]:
    return [" ".join(text[s:e].split()) for s, e in sentence_spans(text)]


def test_sentences_are_not_cut_at_abbreviations_or_numbers() -> None:
    text = ("Mr. Rahim of Rahim Traders Ltd. was paid by Dr. Karim. The cheque, No. 0045871, was for "
            "Tk 5,00,000 on 5 April 2026 (s. 138 applies in Rahim v. Karim). Next sentence here.")
    assert sentences(text) == [
        "Mr. Rahim of Rahim Traders Ltd. was paid by Dr. Karim.",
        "The cheque, No. 0045871, was for Tk 5,00,000 on 5 April 2026 (s. 138 applies in Rahim v. Karim).",
        "Next sentence here.",
    ]
    assert sentences("চেক নং. ০০৪৫৮৭১ তারিখ ১০ এপ্রিল ২০২৬। পরের বাক্য।") == [
        "চেক নং. ০০৪৫৮৭১ তারিখ ১০ এপ্রিল ২০২৬।", "পরের বাক্য।"]
    assert sentences("Amount 5.5 lakh and M. A. Karim signed. Done.") == [
        "Amount 5.5 lakh and M. A. Karim signed.", "Done."]


def test_wrapped_lines_join_and_headings_split() -> None:
    text = "3. Timeline\n10 Apr 2026\nCheque date.\nThe cheque is\nreturned unpaid."
    assert sentences(text) == ["3. Timeline", "10 Apr 2026 Cheque date.", "The cheque is returned unpaid."]
    for start, end in sentence_spans(text):  # spans are verbatim page text
        assert text[start:end] == text[start:end].strip()


def test_shared_normalization_dehyphenates_and_unifies_marks() -> None:
    page = "The cheque was dis-\nhonoured on 22 Apr 2026. উপ-\nধারা (১) অনুযায়ী নোটিশ দেওয়া হয়।"
    found = locate_normalized("The cheque was dishonoured on 22 Apr 2026.", page)
    assert found and found.method == "normalized" and page[found.start:found.end] == found.text
    assert found.text.startswith("The cheque was dis-\nhonoured")
    assert locate_normalized("উপ-ধারা (১) অনুযায়ী নোটিশ দেওয়া হয়।", page)
    assert locate_normalized("“The cheque was dis-honoured on 22 Apr 2026.”"[1:-1], page)
    assert locate_normalized("The cheque was honoured on 22 Apr 2026.", page) is None


def test_check_quote_stores_exact_span_or_marks_unverified() -> None:
    page = PageInput(uuid4(), uuid4(), 1, 1, "SAMPLE_DATA_NOT_REAL_LAW the buyer   paid\nthe seller on 12 March 2024.")
    ok = check_quote("the buyer paid the seller on 12 March 2024.", page)
    assert ok["quote_check"] == "passed" and ok["quote_match"] == "normalized"
    assert ok["quote"] == page.text[ok["quote_start"]:ok["quote_end"]] == "the buyer   paid\nthe seller on 12 March 2024."
    missing = check_quote("the seller paid the buyer on 12 March 2024.", page)
    assert missing["quote_check"] == "failed" and missing["quote_start"] is None
    assert check_quote("12 March 2024.", page)["quote_check"] == "failed"  # too short to support a fact


def test_every_fact_from_cheque_brief_is_confirmable_or_flagged(api_client, local_app_user_database_url) -> None:
    user_id, case_id = lawyer_with_case(api_client, "cheque-brief")
    uploaded = upload(api_client, case_id, PDF.read_bytes(), "case1_cheque_dishonour.pdf")
    assert uploaded.status_code == 201, uploaded.text
    run = extract(api_client, case_id)
    assert run["status"] == "succeeded" and len(run["facts"]) >= 10
    page_text = sql_as(local_app_user_database_url, user_id,
                       "SELECT text FROM public.extracted_pages WHERE case_id = :c AND page_no = 1 "
                       "ORDER BY version DESC LIMIT 1", c=case_id)[0][0]
    for fact in run["facts"]:
        source = fact["sources"][0]
        response = api_client.post(facts_url(case_id, f"/{fact['id']}/confirm"), headers=ORIGIN, json={})
        if fact["source_check"] == "passed":
            assert response.status_code == 200, (fact["statement"], response.text)
            assert page_text[source["quote_start"]:source["quote_end"]] == source["quote"]
        else:  # clearly flagged: unverified quote and a machine-readable confirm error
            assert source["quote_start"] is None
            assert response.status_code == 409 and response.json()["detail"].startswith("QUOTE_NOT_FOUND")
    statements = [f["statement"] for f in run["facts"]]
    assert all(f["source_check"] == "passed" for f in run["facts"]), statements
    assert any("No. 0045871, dated 10 April 2026, for Tk 5,00,000" in s for s in statements)
    assert not any(s.endswith(" No.") or s.endswith(" for Tk") for s in statements)


def test_unfound_quote_blocks_confirm_with_quote_not_found(api_client) -> None:
    _, case_id = lawyer_with_case(api_client, "quote-missing")
    assert upload(api_client, case_id, PDF.read_bytes(), "case1_cheque_dishonour.pdf").status_code == 201
    document_id = api_client.get(f"/api/v1/lawyer/cases/{case_id}/documents").json()[0]["id"]
    fact = api_client.post(facts_url(case_id), headers=ORIGIN, json={
        "category": "date", "statement": "SAMPLE cheque dated 11 April 2026.", "statement_type": "lawyer_entered",
        "sources": [{"document_id": document_id, "page_no": 1,
                     "quote": "a cheque dated 11 April 2026 for Tk 9,00,000 was given"}],
    })
    assert fact.status_code == 201, fact.text
    assert fact.json()["sources"][0]["quote_check"] == "failed"
    assert fact.json()["sources"][0]["quote_match"] is None
