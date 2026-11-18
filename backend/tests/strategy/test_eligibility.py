"""Tests for Legal Eligibility and Statutory Prerequisite Validation."""

from backend.src.strategy.eligibility import LegalEligibilityValidator


def test_ni_act_eligibility_with_complete_docs():
    docs = [
        {"filename": "cheque.pdf", "text": "Cheque #4928192"},
        {"filename": "memo.pdf", "text": "Dishonoured unpaid insufficient funds"},
        {"filename": "notice.pdf", "text": "Demand notice under Section 138"},
    ]
    res = LegalEligibilityValidator.validate(
        strategy_name="Criminal Prosecution under Section 138 NI Act",
        case_facts={"amount": 1500000},
        available_documents=docs,
    )
    assert res.is_eligible is True
    assert "Magistrate" in res.jurisdiction_status
    assert len(res.identified_remedies) >= 2


def test_ni_act_eligibility_missing_notice_not_auto_rejected():
    # If demand notice is missing, do NOT auto-reject outright;
    # flag limitation as unverified and add to missing_verifications.
    docs = [
        {"filename": "cheque.pdf", "text": "Cheque #4928192"},
        {"filename": "memo.pdf", "text": "Dishonoured unpaid"},
    ]
    res = LegalEligibilityValidator.validate(
        strategy_name="Section 138 NI Act Prosecution",
        case_facts={},
        available_documents=docs,
    )
    assert "Unverified limitation" in res.limitation_status
    assert any("notice" in m.lower() for m in res.missing_verifications)


def test_civil_suit_eligibility_and_remedies():
    docs = [
        {"filename": "cheque.pdf", "text": "Cheque leaf #4928192"},
        {"filename": "court_fee_challan.pdf", "text": "Court fee paid"},
    ]
    res = LegalEligibilityValidator.validate(
        strategy_name="Summary Civil Suit (Order XXXVII CPC)",
        case_facts={"amount": 1500000},
        available_documents=docs,
    )
    assert res.is_eligible is True
    assert "Joint District Judge" in res.jurisdiction_status
    assert any("Attachment before judgment" in r for r in res.identified_remedies)
