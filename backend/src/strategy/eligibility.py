"""Legal Eligibility Validation (NOT_CONFIGURED).

The earlier validator returned hard-coded courts, remedies, and limitation
periods by keyword-matching the strategy name. Limitation periods and procedural
deadlines must come from deterministic code over a curated, cited rules table
(master prompt idea #10). No such table exists yet, so every check is reported
as NOT_CONFIGURED and left to the lawyer.
"""

from typing import Any, Dict, List

from backend.src.strategy.schemas import NOT_CONFIGURED, EligibilityCheckResult


class LegalEligibilityValidator:
    """Eligibility checks for a candidate strategy. Currently NOT_CONFIGURED."""

    @classmethod
    def validate(
        cls,
        strategy_name: str,
        case_facts: Dict[str, Any],
        available_documents: List[Dict[str, Any]],
    ) -> EligibilityCheckResult:
        """Report that jurisdiction, limitation and prerequisites are unchecked."""
        return EligibilityCheckResult(
            is_eligible=False,
            jurisdiction_status=NOT_CONFIGURED,
            limitation_status=NOT_CONFIGURED,
            procedural_prerequisites_met=False,
            missing_verifications=[
                "Lawyer must verify jurisdiction, limitation, and procedural prerequisites; "
                "no curated, cited rules table is configured."
            ],
            identified_remedies=[],
            notes=NOT_CONFIGURED,
        )
