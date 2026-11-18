"""Deterministic Mock LLM Provider.

Generates realistic Bangladesh legal responses for tests and local development
without internet access or API credentials.
Complies with AGENTS.md Rule 1: Test data labelled SAMPLE_DATA_NOT_REAL_LAW.
"""

from typing import Any, Optional, Type, TypeVar
import json
from pydantic import BaseModel
from backend.src.ai.gateway import BaseLLMProvider, LLMResponse, LLMTokenUsage

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(BaseLLMProvider):
    """Deterministic mock provider producing structured legal models."""

    def __init__(self, model_name: str = "mock-legal-v1"):
        self._model_name = model_name

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: Optional[Type[T]] = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Generate deterministic mock legal outputs based on requested schema or prompt keywords."""
        content = ""
        parsed = None

        if response_schema is not None:
            schema_name = response_schema.__name__
            mock_data = self._generate_mock_data_for_schema(schema_name, prompt)
            content = json.dumps(mock_data, ensure_ascii=False)
            try:
                parsed = response_schema.model_validate(mock_data)
            except Exception:
                parsed = response_schema.model_validate_json(content)
        else:
            content = (
                "[SAMPLE_DATA_NOT_REAL_LAW] Mock legal reasoning generated for offline development. "
                "Document evidence reviewed against Bangladesh legal standards."
            )

        return LLMResponse(
            content=content,
            parsed=parsed,
            provider="mock",
            model=self._model_name,
            usage=LLMTokenUsage(
                prompt_tokens=len(prompt) // 4,
                completion_tokens=len(content) // 4,
                total_tokens=(len(prompt) + len(content)) // 4,
            ),
        )

    def _generate_mock_data_for_schema(self, schema_name: str, prompt: str) -> dict:
        """Generate context-aware mock payload matching the requested Pydantic schema."""
        # Timeline extraction schema
        if "Timeline" in schema_name:
            return {
                "events": [
                    {
                        "event_date": "2023-01-10",
                        "raw_date_text": "10 January 2023",
                        "title": "Cheque Issuance",
                        "description": "Accused issued Cheque No. 4928192 drawn on Agrani Bank for BDT 1,500,000.",
                        "actor": "Accused (Managing Director)",
                        "source_document_id": "doc-cheque-01",
                        "source_page": 1,
                        "confidence": "high",
                    },
                    {
                        "event_date": "2023-01-25",
                        "raw_date_text": "25 January 2023",
                        "title": "Bank Presentation & Dishonour",
                        "description": "Cheque presented for encashment; returned dishonoured with remark 'Insufficient Funds'.",
                        "actor": "Complainant & Agrani Bank",
                        "source_document_id": "doc-return-memo-01",
                        "source_page": 1,
                        "confidence": "high",
                    },
                    {
                        "event_date": "2023-02-05",
                        "raw_date_text": "05 February 2023",
                        "title": "Statutory Demand Notice Sent",
                        "description": "Legal notice dispatched via registered post demanding payment within 30 days under NI Act Sec 138.",
                        "actor": "Complainant Advocate",
                        "source_document_id": "doc-notice-01",
                        "source_page": 1,
                        "confidence": "high",
                    },
                    {
                        "event_date": "2023-02-08",
                        "raw_date_text": "০৮ই ফেব্রুয়ারি ২০২৩",
                        "title": "Notice Delivered",
                        "description": "Postal acknowledgment card signed by recipient at registered business address.",
                        "actor": "Postal Service & Accused",
                        "source_document_id": "doc-postal-ad-01",
                        "source_page": 1,
                        "confidence": "high",
                    },
                    {
                        "event_date": "2023-03-20",
                        "raw_date_text": "20 March 2023",
                        "title": "Complaint Petition Filed in C.R. Case",
                        "description": "Complainant filed formal petition of complaint before Metropolitan Magistrate Court.",
                        "actor": "Complainant Advocate",
                        "source_document_id": "doc-complaint-01",
                        "source_page": 2,
                        "confidence": "high",
                    },
                ]
            }

        # Contradictions and missing gaps schema
        if "Contradiction" in schema_name:
            return {
                "contradictions": [
                    {
                        "issue": "Disputed Cheque Consideration Amount",
                        "statement_a": "Complainant states cheque was issued in discharge of business debt of BDT 1,500,000.",
                        "source_a_document": "Complaint Petition",
                        "source_a_page": 2,
                        "statement_b": "Accused Written Statement claims cheque was stolen blank security leaf with no debt.",
                        "source_b_document": "Accused Deposition",
                        "source_b_page": 1,
                        "severity": "high",
                        "analysis": "Creates genuine triable issue under Section 139 presumption; burden of rebuttal on accused.",
                    }
                ],
                "gaps": [
                    {
                        "missing_item": "Bank Account Opening Signature Specimen Card",
                        "statutory_requirement": "Evidence to corroborate authenticity of drawer signature under Section 138",
                        "impact": "Crucial if accused denies signature under Section 73 Evidence Act.",
                    },
                    {
                        "missing_item": "Postal Registry Dispatch Memo",
                        "statutory_requirement": "Strict proof of dispatch within 30 days of dishonour memo receipt",
                        "impact": "Procedural condition precedent; limitation bar if dispatch exceeds 30-day window.",
                    },
                ],
            }

        # Case Analysis schema
        return {
            "client_position": "Complainant seeking recovery of BDT 1,500,000 dishonoured cheque under Section 138 Negotiable Instruments Act 1881.",
            "factual_summary": "On 10 Jan 2023, the accused issued a cheque for BDT 1,500,000 against goods supplied. The cheque was dishonoured for insufficient funds on 25 Jan 2023. Statutory demand notice was served within the 30-day limitation window on 08 Feb 2023. Accused failed to repay within 30 days.",
            "legal_issues": [
                "Whether statutory demand notice was lawfully served within 30 days of dishonour under NI Act 138(b)?",
                "Whether the statutory presumption under Section 139 applies in favour of the holder of the cheque?",
            ],
            "key_claims": [
                {
                    "text": "Cheque was issued by accused for lawful discharge of preexisting commercial debt.",
                    "claim_type": "fact_from_document",
                    "confidence_label": "high",
                    "source_name": "Complaint Petition",
                    "source_page": 1,
                    "quote": "The accused issued cheque no. 4928192 against supply invoice 104.",
                    "needs_lawyer_review": False,
                },
                {
                    "text": "Dishonour memo explicitly notes 'funds insufficient' on 25 January 2023.",
                    "claim_type": "fact_from_document",
                    "confidence_label": "high",
                    "source_name": "Bank Return Memo",
                    "source_page": 1,
                    "quote": "Returned unpaid. Reason code 01: Insufficient Funds.",
                    "needs_lawyer_review": False,
                },
                {
                    "text": "Accused may plead lost or security cheque defense during examination under Section 342 CrPC.",
                    "claim_type": "inference",
                    "confidence_label": "medium",
                    "source_name": "Legal Inference",
                    "source_page": 1,
                    "quote": "",
                    "needs_lawyer_review": True,
                },
            ],
            "supporting_evidence": [
                {
                    "item": "Original Cheque No. 4928192 and Bank Dishonour Slip",
                    "source": "Document Ex. 1",
                    "page": 1,
                    "relevance": "Primary documentary evidence establishing dishonour under Section 138.",
                },
                {
                    "item": "Postal Acknowledgment Card signed by Accused",
                    "source": "Document Ex. 2",
                    "page": 1,
                    "relevance": "Proves service of legal demand notice satisfying Section 138(c).",
                },
            ],
            "weakening_evidence": [
                {
                    "item": "Absence of written commercial contract or delivery challan in case record",
                    "source": "Document Inventory",
                    "page": 1,
                    "relevance": "Accused may challenge consideration behind the cheque under Section 118.",
                }
            ],
            "suggested_next_steps": [
                "Summon Bank Branch Manager to produce original bank ledger and signature specimen.",
                "Procure delivery challans and purchase orders to substantiate consideration before formal cross-examination.",
                "Prepare targeted cross-examination questions regarding the accused's admission of cheque issuance.",
            ],
        }
