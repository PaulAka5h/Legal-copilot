"""Legal Eligibility and Statutory Prerequisite Validation for Bangladesh Courts.

Validates jurisdiction, limitation periods, procedural prerequisites, and required documents.
Flags gaps as requiring verification rather than automatically discarding strategies.
"""

from typing import Any, Dict, List, Optional
from backend.src.strategy.schemas import EligibilityCheckResult


class LegalEligibilityValidator:
    """Validates legal admissibility and procedural prerequisites for Bangladesh legal actions."""

    @classmethod
    def validate(
        cls,
        strategy_name: str,
        case_facts: Dict[str, Any],
        available_documents: List[Dict[str, Any]],
    ) -> EligibilityCheckResult:
        """Validate legal eligibility for a candidate legal strategy."""
        missing_verifications: List[str] = []
        identified_remedies: List[str] = []
        is_eligible = True
        notes_parts: List[str] = []

        all_doc_names = " ".join([
            str(d.get("filename", "")).lower() + " " + str(d.get("text", "")).lower()
            for d in available_documents
        ])

        name_lower = strategy_name.lower()

        # 1. Cheque Dishonour Criminal Prosecution (NI Act Section 138)
        if "138" in name_lower or "negotiable" in name_lower or "cheque" in name_lower:
            jurisdiction = "Metropolitan Magistrate / Judicial Magistrate Court of competent territorial jurisdiction where cheque was dishonoured."
            identified_remedies = [
                "Imprisonment for a term which may extend to 1 year under Section 138",
                "Fine which may extend to twice the amount of the dishonoured cheque",
                "Direction for payment of fine to complainant as compensation under Section 138(2)",
            ]

            # Limitation check: Notice within 30 days, filing within 30 days of notice expiry
            has_notice = any(k in all_doc_names for k in ["notice", "নোটিশ", "demand"])
            has_memo = any(k in all_doc_names for k in ["dishonour", "memo", "unpaid", "মেমো"])
            has_cheque = any(k in all_doc_names for k in ["cheque", "check", "চেক"])

            if not has_cheque:
                missing_verifications.append("Original cheque or certified extract required for judicial inspection.")
                is_eligible = False

            if not has_memo:
                missing_verifications.append("Bank return memo with formal reason code required to establish cause of action.")
                is_eligible = False

            if not has_notice:
                missing_verifications.append("Proof of 30-day statutory demand notice and postal dispatch receipt required under Section 138(b).")
                limitation_status = "Unverified limitation: Date of demand notice receipt must be confirmed to ensure complaint is not time-barred."
            else:
                limitation_status = "Limitation condition: Complaint must be filed within 30 days following the 30-day notice cure period."

            procedural_met = len(missing_verifications) == 0

        # 2. Summary Civil Suit for Money Recovery (Order XXXVII CPC 1908)
        elif "civil" in name_lower or "summary" in name_lower or "xxxvii" in name_lower or "cpc" in name_lower:
            jurisdiction = "Joint District Judge / Senior Assistant Judge Court based on pecuniary claim value (Civil Courts Act 1887)."
            identified_remedies = [
                "Summary civil decree for principal cheque amount with contractual or statutory interest",
                "Attachment before judgment under Order XXXVIII CPC if defendant attempts to alienate assets",
                "Execution of money decree through sale of debtor's movable/immovable assets",
            ]
            limitation_status = "Limitation Act 1908, Article 57/64: 3 years from the date of cheque issuance/dishonour."
            procedural_met = True

            has_court_fee = any(k in all_doc_names for k in ["court fee", "ফি", "challan"])
            if not has_court_fee:
                missing_verifications.append("Ad-valorem court fee assessment required under Court-fees Act 1870.")

        # 3. Alternative Dispute Resolution (ADR / Section 89A CPC Mediation)
        elif "adr" in name_lower or "mediation" in name_lower or "settlement" in name_lower:
            jurisdiction = "Pre-litigation legal notice negotiation, or Court-annexed mediation under Section 89A CPC."
            identified_remedies = [
                "Mutual structured repayment schedule or lump-sum compromise settlement",
                "Enforceable compromise decree (Solenameh) without appellate challenge risk",
                "Immediate mitigation of legal costs and multi-year trial delays",
            ]
            limitation_status = "No strict statutory limitation period; tolling of limitation during formal mediation."
            procedural_met = True
            missing_verifications.append("Confirm willingness of adverse party to enter into bonafide compromise talks.")

        # 4. Default / General Action
        else:
            jurisdiction = "Competent Court of Civil or Criminal Jurisdiction in Bangladesh."
            identified_remedies = ["Statutory legal remedy as permitted by applicable law."]
            limitation_status = "Governed by the Limitation Act, 1908."
            procedural_met = True

        return EligibilityCheckResult(
            is_eligible=is_eligible,
            jurisdiction_status=jurisdiction,
            limitation_status=limitation_status,
            procedural_prerequisites_met=procedural_met,
            missing_verifications=missing_verifications,
            identified_remedies=identified_remedies,
            notes="; ".join(notes_parts) if notes_parts else "Eligibility check completed.",
        )
