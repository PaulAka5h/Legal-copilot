"""Quote repair: model quotes are located in the stored chunk and replaced by the EXACT span.

Rule 1 (no invented law): whatever is stored must be an exact substring of the chunk.
Statute-like text below is SAMPLE_DATA_NOT_REAL_LAW unless noted.
"""

import unicodedata
from uuid import uuid4

import pytest

from app.case_analysis.analyzer import ProvisionInput, build_user_prompt, numbered_sentences, sentence_numbers
from app.case_analysis.schemas import AnalysisDraft, ElementDraft, FindingDraft, QuoteRef
from app.case_analysis.service import _verify
from app.rag.quote_locator import FUZZY_MIN_RATIO, locate_quote, segment_hint, segments
from app.rag.verifier import verify_citation

EN = ("SAMPLE_DATA_NOT_REAL_LAW Act, 1881 — Section 138: Dishonour of cheque\n"
      "Where any cheque drawn by a person on an account maintained by him with a banker for payment of any "
      "amount of money to another person from out of that account for the discharge, in whole or in part, "
      "of any debt or other liability, is returned by the bank unpaid, because of the amount of money "
      "standing to the credit of that account is insufficient to honour the cheque, such person shall be "
      "deemed to have committed an offence.")
BN = ("SAMPLE_DATA_NOT_REAL_LAW আইন — ধারা ৫: নমুনা\n"
      "যদি কোন ব্যক্তি চেক প্রদান করেন । তবে তিনি উক্ত অর্থ পরিশোধে দায়ী হইবেন।\n"
      "এই ধারার অধীন নোটিশ ত্রিশ দিনের মধ্যে দিতে হইবে।")


def _chunk(text):
    return {"text": text, "title": "SAMPLE Act", "section_number": "138", "language": "en",
            "source_url": "https://example.invalid", "section_status": "unknown", "source_status": "unknown",
            "effective_from": None, "effective_to": None, "review_status": "approved", "is_current": True}


def _is_exact_span(located, text):
    return located is not None and text[located.start:located.end] == located.text and located.text in text


# ---------------------------------------------------------------- repair into the exact span
@pytest.mark.parametrize(("quote", "method"), [
    ("is returned by the bank unpaid", "exact"),
    ("IS RETURNED  by the\nbank unpaid", "normalized"),  # case + whitespace
    ("SAMPLE_DATA_NOT_REAL_LAW Act, 1881 - Section 138: Dishonour of cheque", "normalized"),  # dash variant
    ("Where any cheque drawn by a person on an account maintained by him with the banker for the payment of any "
     "amount", "fuzzy"),  # two small slips ("the banker", "the payment")
])
def test_inexact_quote_is_repaired_into_the_exact_source_span(quote, method):
    located = locate_quote(quote, EN)
    assert located is not None and located.method == method
    assert _is_exact_span(located, EN)
    if method == "fuzzy":
        assert located.ratio >= FUZZY_MIN_RATIO
        assert "with a banker for payment of any amount" in located.text  # the source wording, not the model's


@pytest.mark.parametrize("quote", [
    "shall be punished with imprisonment for a term which may extend to one year",  # fabricated provision text
    "the drawer must pay twice the cheque amount as compensation to the payee",  # invented obligation
    "cheque returned unpaid",  # paraphrase, too short for the fuzzy step
    "",
])
def test_fabricated_or_paraphrased_quote_is_rejected(quote):
    assert locate_quote(quote, EN) is None


def test_fuzzy_needs_four_words_and_twenty_characters():
    assert locate_quote("dishonour of cheques", EN) is None  # 20 chars, 3 words, not an exact match
    assert locate_quote("returned by the bnk unpaid because", EN) is not None  # 5 words, one slip


# ---------------------------------------------------------------- Bangla
@pytest.mark.parametrize("quote", [
    "যদি কোন ব্যক্তি চেক প্রদান করেন।",  # no space before the danda (source has " ।")
    "যদি  কোন ব্যক্তি\nচেক প্রদান করেন ।",  # extra whitespace / line break
    "যদি কোন ব্যক্তি চেক প্রদান করেন |",  # ASCII pipe typed for the danda
    "তবে তিনি উক্ত অর্থ পরিশোধে দায়ী হইবেন॥",  # double danda
    unicodedata.normalize("NFD", "এই ধারার অধীন নোটিশ ত্রিশ দিনের মধ্যে দিতে হইবে।"),  # decomposed input
    "এই ধারার অধীন নো‌টিশ ত্রিশ দিনের মধ্যে দিতে হইবে।",  # stray ZWNJ
])
def test_bangla_danda_and_whitespace_variants_pass(quote):
    located = locate_quote(quote, BN)
    assert _is_exact_span(located, BN), quote


def test_bangla_fabricated_quote_is_rejected():
    assert locate_quote("তিনি দুই বছর কারাদণ্ডে দণ্ডিত হইবেন এবং জরিমানা দিবেন।", BN) is None


# ---------------------------------------------------------------- numbered sentences and hints
def test_numbered_sentences_are_exact_text_and_refs_map_back():
    spans = segments(EN)
    rendered = numbered_sentences(EN).splitlines()
    assert len(rendered) == len(spans) and rendered[0].startswith("[S1] ")
    assert all(line.split(" ", 1)[1] in EN for line in rendered)
    assert sentence_numbers(EN, "is returned by the bank unpaid") == [2]
    assert segment_hint(EN, [2]) == spans[1] and segment_hint(EN, [99, -1]) is None
    prompt = build_user_prompt([], [ProvisionInput(uuid4(), "SAMPLE Act", "138", BN)])
    assert "[S2] যদি কোন ব্যক্তি চেক প্রদান করেন ।" in prompt


def test_sentence_labels_copied_into_a_quote_are_ignored():
    chunk_id = uuid4()
    citation = verify_citation(chunk_id, "[S2] is returned by the bank unpaid", {chunk_id: _chunk(EN)}, None)
    assert citation.verified and citation.quote == "is returned by the bank unpaid"


# ---------------------------------------------------------------- verifier and analysis rules
def test_verifier_stores_the_exact_span_and_records_the_repair():
    chunk_id = uuid4()
    citation = verify_citation(chunk_id, "IS RETURNED by the bank   unpaid", {chunk_id: _chunk(EN)}, None)
    assert citation.verified and citation.quote == "is returned by the bank unpaid"
    assert "quote_repaired:normalized" in citation.warnings


def test_verifier_drops_a_fabricated_quote():
    chunk_id = uuid4()
    citation = verify_citation(chunk_id, "shall be punished with imprisonment for one year",
                               {chunk_id: _chunk(EN)}, None)
    assert not citation.verified and citation.quote is None and "quote_not_in_source" in citation.failures


def _finding(chunk_id, quote, element_quotes, fact_id):
    return FindingDraft(
        offence_or_claim="SAMPLE dishonour", chunk_id=chunk_id, quote=quote,
        quote_ref=QuoteRef(chunk_id=chunk_id, sentences=[2]),
        elements=[ElementDraft(element=f"e{i}", element_quote=q, matched_fact_id=fact_id, status="met",
                               element_quote_sentences=[2]) for i, q in enumerate(element_quotes)],
        strength="strong", reasons=["SAMPLE reason"])


def test_one_bad_element_quote_is_dropped_and_the_finding_kept_unverified():
    chunk_id, fact_id = uuid4(), uuid4()
    draft = AnalysisDraft(missing_information=[], findings=[_finding(
        chunk_id, "IS RETURNED by the bank unpaid",
        ["is returned by the bank  unpaid", "the drawer is liable to pay double the amount as a penalty"], fact_id)])
    (finding,), summary = _verify(draft, {chunk_id: _chunk(EN)}, {fact_id}, None, {chunk_id}, False)
    assert finding["section_citation"]["verified"] and finding["section_citation"]["quote"] in EN
    good, bad = finding["elements"]
    assert good["verified"] and good["element_quote"] == "is returned by the bank unpaid"
    assert not bad["verified"] and bad["element_quote"] is None  # dropped, never the model's text
    assert finding["verification"] == "unverified" and finding["strength"] == "insufficient"
    assert summary["quotes_dropped"] == 1 and summary["quotes_repaired"] == 2
    assert any("removed" in r for r in finding["reasons"])


def test_repaired_quotes_verify_the_finding():
    chunk_id, fact_id = uuid4(), uuid4()
    draft = AnalysisDraft(missing_information=[], findings=[_finding(
        chunk_id, "Where any cheque drawn by a person on an account maintained by him with the banker",
        ["IS RETURNED by the bank unpaid", "insufficient to honour the cheque"], fact_id)])
    (finding,), _ = _verify(draft, {chunk_id: _chunk(EN)}, {fact_id}, None, {chunk_id}, False)
    assert finding["verification"] == "verified" and finding["strength"] == "strong"
    stored = [finding["section_citation"]["quote"], *(e["element_quote"] for e in finding["elements"])]
    assert all(q in EN for q in stored)  # Rule 1: every stored quote is an exact substring


def test_long_quotes_are_located_quickly():
    """A whole-provision quote (Gemini does this) must not stall the request."""
    import time

    body = " ".join(f"SAMPLE clause {i} says the holder of the cheque shall give notice in writing." for i in range(40))
    chunk = "Preamble about banks. " * 30 + body + " Explanation follows. " * 30
    quote = body.replace("holder", "holders", 3).replace("notice in", "notice  in")
    started = time.perf_counter()
    located = locate_quote(quote, chunk)
    assert located is not None and located.method == "fuzzy" and located.text in chunk
    assert time.perf_counter() - started < 2.0
