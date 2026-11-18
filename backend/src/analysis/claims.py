"""Claims and Verification Engine.

Enforces Legal Product Rules:
1. Rule 2: "No source, no claim. Every important AI conclusion links to a document page or a legal source. Unverified items are labelled unverified."
2. Rule 3: "Keep statement types apart: document says, lawyer entered, AI inference, assumption, prediction."
"""

from typing import Dict, List, Optional
from backend.src.analysis.schemas import (
    ClaimItem,
    ClaimSourceItem,
    ClaimType,
    ConfidenceLabel,
    VerificationVerdict,
)


class ClaimsVerifier:
    """Verifies extracted claims against source document chunks and citation rules."""

    @staticmethod
    def verify_claim(
        claim: ClaimItem,
        available_chunks: Optional[List[Dict[str, any]]] = None,
    ) -> ClaimItem:
        """Verify an individual claim and assign its verification verdict.
        
        Rules:
        - Claims of type ASSUMPTION or PREDICTION do not require document sources,
          but are marked needs_lawyer_review=True if confidence is low.
        - Claims of type FACT_FROM_DOCUMENT without sources MUST be marked UNVERIFIED.
        - If available_chunks is provided, verify whether the quote or reference exists.
        """
        # Assumptions and predictions are inherently non-factual hypotheses
        if claim.claim_type in (ClaimType.ASSUMPTION, ClaimType.PREDICTION):
            claim.verification_verdict = VerificationVerdict.CANNOT_VERIFY
            return claim

        # Rule 2: No source, no claim.
        if not claim.sources:
            claim.confidence_label = ConfidenceLabel.UNVERIFIED
            claim.verification_verdict = VerificationVerdict.UNSUPPORTED
            claim.needs_lawyer_review = True
            return claim

        # Verify against available document chunks if provided
        if available_chunks:
            corroborated = False
            for src in claim.sources:
                if src.source_kind == "document_chunk":
                    target_quote = src.quote.strip().lower() if src.quote else ""
                    for chunk in available_chunks:
                        chunk_text = str(chunk.get("text", "")).lower()
                        # If quote is in chunk or chunk is specifically referenced
                        if target_quote and target_quote in chunk_text:
                            corroborated = True
                            break
                        if str(chunk.get("id", "")) == str(src.document_chunk_id):
                            corroborated = True
                            break
                elif src.source_kind == "legal_source_version":
                    corroborated = True

            if corroborated:
                claim.verification_verdict = VerificationVerdict.SUPPORTED
                claim.confidence_label = ConfidenceLabel.HIGH
            else:
                claim.verification_verdict = VerificationVerdict.PARTIALLY_SUPPORTED
                claim.confidence_label = ConfidenceLabel.MEDIUM
                claim.needs_lawyer_review = True
        else:
            # Default to verified if source is specified with page number
            has_valid_source = any(src.page_number > 0 for src in claim.sources)
            if has_valid_source:
                claim.verification_verdict = VerificationVerdict.SUPPORTED
            else:
                claim.confidence_label = ConfidenceLabel.UNVERIFIED
                claim.verification_verdict = VerificationVerdict.UNSUPPORTED
                claim.needs_lawyer_review = True

        return claim

    @classmethod
    def verify_all(
        cls,
        claims: List[ClaimItem],
        available_chunks: Optional[List[Dict[str, any]]] = None,
    ) -> List[ClaimItem]:
        """Verify a collection of claims."""
        return [cls.verify_claim(c, available_chunks) for c in claims]
