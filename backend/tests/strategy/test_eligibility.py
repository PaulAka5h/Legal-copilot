"""Eligibility is NOT_CONFIGURED until a curated, cited rules table exists."""

from backend.src.strategy.eligibility import LegalEligibilityValidator
from backend.src.strategy.schemas import NOT_CONFIGURED


def test_eligibility_reports_not_configured_without_legal_claims():
    res = LegalEligibilityValidator.validate(
        strategy_name="SAMPLE_DATA_NOT_REAL_LAW strategy",
        case_facts={},
        available_documents=[{"filename": "doc.pdf", "text": "SAMPLE_DATA_NOT_REAL_LAW"}],
    )
    assert res.is_eligible is False
    assert res.jurisdiction_status == NOT_CONFIGURED
    assert res.limitation_status == NOT_CONFIGURED
    assert res.identified_remedies == []
    assert res.missing_verifications
