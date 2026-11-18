"""Tests for Claims Verification and Statement Classification."""

from backend.src.analysis.claims import ClaimsVerifier
from backend.src.analysis.schemas import (
    ClaimItem,
    ClaimSourceItem,
    ClaimType,
    ConfidenceLabel,
    VerificationVerdict,
)


def test_unsourced_fact_flagged_unverified():
    # Legal Product Rule 2: "No source, no claim. Unverified items are labelled unverified."
    claim = ClaimItem(
        text="Accused admitted guilt in police station.",
        claim_type=ClaimType.FACT_FROM_DOCUMENT,
        confidence_label=ConfidenceLabel.HIGH,
        sources=[],
    )
    verified = ClaimsVerifier.verify_claim(claim)
    assert verified.confidence_label == ConfidenceLabel.UNVERIFIED
    assert verified.verification_verdict == VerificationVerdict.UNSUPPORTED
    assert verified.needs_lawyer_review is True


def test_corroborated_claim_verified():
    chunks = [
        {
            "id": "chunk-101",
            "text": "The cheque no. 4928192 was returned unpaid on 25 January 2023 with remark Insufficient Funds.",
        }
    ]
    claim = ClaimItem(
        text="Cheque was dishonoured due to insufficient funds.",
        claim_type=ClaimType.FACT_FROM_DOCUMENT,
        sources=[
            ClaimSourceItem(
                source_kind="document_chunk",
                document_chunk_id="chunk-101",
                page_number=1,
                quote="returned unpaid on 25 January 2023 with remark Insufficient Funds",
            )
        ],
    )
    verified = ClaimsVerifier.verify_claim(claim, available_chunks=chunks)
    assert verified.confidence_label == ConfidenceLabel.HIGH
    assert verified.verification_verdict == VerificationVerdict.SUPPORTED


def test_assumptions_handled_as_hypotheses():
    claim = ClaimItem(
        text="The defense will likely argue the cheque was given for collateral security.",
        claim_type=ClaimType.ASSUMPTION,
        sources=[],
    )
    verified = ClaimsVerifier.verify_claim(claim)
    assert verified.verification_verdict == VerificationVerdict.CANNOT_VERIFY
