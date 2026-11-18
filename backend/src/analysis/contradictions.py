"""Contradiction & Evidence Gap Detection Engine.

Detects conflicts between opposing documents and evaluates statutory checklists
for Bangladesh legal practice.
"""

from typing import Dict, List, Optional
from backend.src.analysis.schemas import ContradictionItem, EvidenceGapItem

# Statutory procedural prerequisites for Bangladesh legal actions
STATUTORY_CHECKLISTS: Dict[str, List[Dict[str, str]]] = {
    "ni_act_138": [
        {
            "item": "Original Cheque or Certified Copy",
            "statutory_requirement": "Negotiable Instruments Act 1881, Section 138 - Primary negotiable instrument",
            "keywords": ["cheque", "check", "চেক"],
            "impact": "Inadmissible without original instrument or formal leave for secondary evidence under Evidence Act Sec 65.",
        },
        {
            "item": "Bank Return Memo / Dishonour Slip",
            "statutory_requirement": "Negotiable Instruments Act 1881, Section 138 - Proof of bank dishonour",
            "keywords": ["dishonour", "return memo", "insufficient funds", "ব্যাংক মেমো", "প্রত্যাখ্যাত"],
            "impact": "Failure to prove presentation and dishonour within cheque validity period bars cause of action.",
        },
        {
            "item": "Statutory Legal Demand Notice",
            "statutory_requirement": "Negotiable Instruments Act 1881, Section 138(b) - Notice within 30 days of dishonour",
            "keywords": ["legal notice", "demand notice", "আইনি নোটিশ", "দাবি নোটিশ"],
            "impact": "Mandatory condition precedent. Omission or late service is fatal to prosecution.",
        },
        {
            "item": "Postal Dispatch Receipt / Acknowledgment Due (A.D.) Card",
            "statutory_requirement": "General Clauses Act 1897, Section 27 - Presumption of service by registered post",
            "keywords": ["postal receipt", "acknowledgment", "registry", "ad card", "ডাক রশিদ", "এডি কার্ড"],
            "impact": "Without dispatch receipt or AD card, drawer can rebut presumption of notice receipt.",
        },
    ],
    "penal_code_murder": [
        {
            "item": "First Information Report (FIR / Ejahar)",
            "statutory_requirement": "Code of Criminal Procedure 1898, Section 154 - Initiation of investigation",
            "keywords": ["fir", "ejahar", "এজাহার"],
            "impact": "Foundational prosecution document; unexplained delay weakens credibility.",
        },
        {
            "item": "Post-Mortem / Autopsy Report",
            "statutory_requirement": "Code of Criminal Procedure 1898, Section 174 - Inquest and cause of death",
            "keywords": ["post-mortem", "autopsy", "ময়নাতদন্ত", "সুরতহাল"],
            "impact": "Medical corroboration essential to establish ante-mortem nature of fatal injuries.",
        },
    ],
    "land_title_suit": [
        {
            "item": "Registered Title Deed (Dalil)",
            "statutory_requirement": "Registration Act 1908, Section 17 & 49 - Compulsory registration of title",
            "keywords": ["deed", "dalil", "দলিল", "কবলা"],
            "impact": "Unregistered documents cannot confer or extinguish right, title, or interest in immovable property.",
        },
        {
            "item": "Record of Rights (Khatian / Porcha)",
            "statutory_requirement": "State Acquisition and Tenancy Act 1950 - Presumption of possession",
            "keywords": ["khatian", "porcha", "খতিয়ান", "পর্চা", "cs", "sa", "rs", "bs"],
            "impact": "Khatian entries raise rebuttable presumption of possession and tenancy.",
        },
    ],
}


class ContradictionEngine:
    """Analyzes cross-document contradictions and scans for missing evidence."""

    @classmethod
    def evaluate_statutory_gaps(
        cls,
        case_type: str,
        available_documents: List[Dict[str, any]],
    ) -> List[EvidenceGapItem]:
        """Check whether required statutory evidentiary documents are present in the case record."""
        checklist_key = "ni_act_138"  # Default to NI Act 138 for commercial cheque disputes
        if "murder" in case_type.lower() or "302" in case_type.lower():
            checklist_key = "penal_code_murder"
        elif "land" in case_type.lower() or "title" in case_type.lower() or "partition" in case_type.lower():
            checklist_key = "land_title_suit"

        checklist = STATUTORY_CHECKLISTS.get(checklist_key, [])
        gaps: List[EvidenceGapItem] = []

        all_doc_names = " ".join([
            str(d.get("filename", "")).lower() + " " + str(d.get("text", "")).lower()
            for d in available_documents
        ])

        for entry in checklist:
            matched = any(kw.lower() in all_doc_names for kw in entry["keywords"])
            if not matched:
                gaps.append(
                    EvidenceGapItem(
                        missing_item=entry["item"],
                        statutory_requirement=entry["statutory_requirement"],
                        impact=entry["impact"],
                    )
                )

        return gaps

    @classmethod
    def find_contradictions(
        cls,
        items: List[ContradictionItem],
    ) -> List[ContradictionItem]:
        """Validate and filter extracted contradictions."""
        valid_items = []
        for c in items:
            if c.statement_a.strip() and c.statement_b.strip():
                valid_items.append(c)
        return valid_items
