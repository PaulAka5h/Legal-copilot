"""Tests for Contradiction Detection and Statutory Checklist Gap Analysis."""

from backend.src.analysis.contradictions import ContradictionEngine
from backend.src.analysis.schemas import ContradictionItem


def test_find_contradictions_filtering():
    items = [
        ContradictionItem(
            issue="Transaction Consideration",
            statement_a="Complainant claims debt of BDT 1,500,000 for supply of fabrics.",
            statement_b="Accused claims no commercial relationship exists.",
        ),
        ContradictionItem(
            issue="Empty issue",
            statement_a="",
            statement_b="Something",
        ),
    ]
    valid = ContradictionEngine.find_contradictions(items)
    assert len(valid) == 1
    assert valid[0].issue == "Transaction Consideration"


def test_statutory_gaps_ni_act_missing_postal_receipt():
    # Only cheque and return memo are present; legal notice and postal receipt are missing
    documents = [
        {"filename": "cheque_copy.pdf", "text": "Pay to Mr. Rahman BDT 1,500,000"},
        {"filename": "bank_dishonour_memo.pdf", "text": "Dishonoured unpaid insufficient funds"},
    ]
    gaps = ContradictionEngine.evaluate_statutory_gaps(
        case_type="Cheque Dishonour NI Act 138",
        available_documents=documents,
    )

    missing_names = [g.missing_item for g in gaps]
    assert any("Notice" in name for name in missing_names)
    assert any("Postal" in name for name in missing_names)


def test_statutory_gaps_complete_record():
    # All statutory elements present
    documents = [
        {"filename": "cheque.pdf", "text": "cheque leaf 4928192"},
        {"filename": "return_memo.pdf", "text": "dishonour return memo insufficient funds"},
        {"filename": "legal_demand_notice.pdf", "text": "statutory demand notice under Section 138"},
        {"filename": "postal_ad_card.pdf", "text": "registered postal receipt and ad card signed"},
    ]
    gaps = ContradictionEngine.evaluate_statutory_gaps(
        case_type="ni_act_138",
        available_documents=documents,
    )
    assert len(gaps) == 0
