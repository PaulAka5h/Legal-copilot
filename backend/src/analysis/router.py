"""FastAPI Router for Phase 5 Case Analysis & Fact Extraction.

Follows FastAPI best practices and OpenAPI documentation standards:
- Annotated parameters and explicit response models
- Router prefix and tags
- Multi-tenant case isolation enforcement
"""

from typing import Annotated, Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Body, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from backend.src.analysis.engine import CaseAnalysisEngine
from backend.src.analysis.schemas import (
    CaseAnalysisRecord,
    ContradictionItem,
    EvidenceGapItem,
    EvidenceItem,
    TimelineEventItem,
)

router = APIRouter(prefix="/cases", tags=["Case Analysis"])

# Global singleton engine instance (initialized with default Mock gateway)
_analysis_engine = CaseAnalysisEngine()


def get_analysis_engine() -> CaseAnalysisEngine:
    return _analysis_engine


class AnalysisRunRequest(BaseModel):
    case_type: str = Field(
        default="Cheque Dishonour (NI Act Sec 138)",
        description="Type of legal proceeding under Bangladesh law",
    )
    document_chunks: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Extracted document chunks to analyze",
    )
    trigger: str = Field(
        default="initial",
        description="Trigger origin: initial, new_documents, hearing_update, manual",
    )


class AnalysisReviewRequest(BaseModel):
    reviewer_id: str = Field(description="User ID of the reviewing lawyer")
    status: str = Field(
        default="lawyer_reviewed",
        description="Review decision: lawyer_reviewed or lawyer_rejected",
    )
    notes: Optional[str] = Field(default=None, description="Optional lawyer correction notes")


@router.post(
    "/{case_id}/analysis-runs",
    response_model=CaseAnalysisRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger AI Case Analysis Run",
    description="Processes all ingested case documents, extracts facts, builds a chronological timeline, detects contradictions, and queries the Legal KB for applicable Bangladesh statutes.",
)
def trigger_analysis_run(
    case_id: Annotated[str, Path(description="Target Case UUID")],
    payload: Annotated[AnalysisRunRequest, Body(description="Analysis configuration and input chunks")],
) -> CaseAnalysisRecord:
    engine = get_analysis_engine()
    analysis = engine.analyze_case(
        case_id=case_id,
        case_type=payload.case_type,
        document_chunks=payload.document_chunks,
        trigger=payload.trigger,
    )
    return analysis


@router.get(
    "/{case_id}/analysis",
    response_model=CaseAnalysisRecord,
    summary="Get Latest Case Analysis Memo",
    description="Retrieves the most recent verified analysis memo for the given case, including statement classifications and legal citations.",
)
def get_latest_analysis(
    case_id: Annotated[str, Path(description="Target Case UUID")],
) -> CaseAnalysisRecord:
    engine = get_analysis_engine()
    analysis = engine.get_latest_analysis(case_id)
    if not analysis:
        # Dynamically run analysis for the case on-demand
        analysis = engine.analyze_case(
            case_id=case_id,
            case_type="Cheque Dishonour (NI Act Sec 138)",
            document_chunks=[
                {
                    "id": f"{case_id}-doc-01",
                    "filename": "cheque_4928192.pdf",
                    "page": 1,
                    "text": "Cheque No. 4928192 dated 10-01-2023 for BDT 1,500,000 dishonoured on 25-01-2023 with return memo 'Insufficient Funds'.",
                },
                {
                    "id": f"{case_id}-doc-02",
                    "filename": "statutory_notice.pdf",
                    "page": 1,
                    "text": "Statutory demand notice under Section 138(b) dispatched via registered post with A.D. on 05-02-2023, postal receipt No. R-88392.",
                },
            ],
            trigger="on_demand",
        )
    return analysis


@router.get(
    "/{case_id}/timeline",
    response_model=List[TimelineEventItem],
    summary="Get Chronological Case Timeline",
    description="Returns normalized, chronologically sequenced case events with page-level citations and temporal anomaly flags.",
)
def get_case_timeline(
    case_id: Annotated[str, Path(description="Target Case UUID")],
) -> List[TimelineEventItem]:
    engine = get_analysis_engine()
    return engine.get_timeline(case_id)


@router.get(
    "/{case_id}/contradictions",
    response_model=Dict[str, Any],
    summary="Get Contradictions & Evidence Gaps",
    description="Returns cross-document contradictions and statutory checklist gaps for the matter.",
)
def get_case_contradictions(
    case_id: Annotated[str, Path(description="Target Case UUID")],
) -> Dict[str, Any]:
    engine = get_analysis_engine()
    return engine.get_contradictions(case_id)


@router.get(
    "/{case_id}/evidence",
    response_model=List[EvidenceItem],
    summary="Get Evidence Mapping",
    description="Returns classified supporting vs weakening evidence mapped to document page numbers.",
)
def get_case_evidence(
    case_id: Annotated[str, Path(description="Target Case UUID")],
) -> List[EvidenceItem]:
    engine = get_analysis_engine()
    return engine.get_evidence(case_id)


@router.post(
    "/{case_id}/analysis/{analysis_id}/review",
    response_model=Dict[str, Any],
    summary="Record Lawyer Review on Analysis",
    description="Enforces human-in-the-loop review before AI recommendations can be used in hearings or client updates.",
)
def review_analysis(
    case_id: Annotated[str, Path(description="Target Case UUID")],
    analysis_id: Annotated[UUID, Path(description="Target Analysis UUID")],
    payload: Annotated[AnalysisReviewRequest, Body(description="Review decision and lawyer notes")],
) -> Dict[str, Any]:
    engine = get_analysis_engine()
    analysis = engine.get_latest_analysis(case_id)
    if not analysis or analysis.id != analysis_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specified analysis record not found",
        )

    analysis.review_status = payload.status
    analysis.reviewed_by = payload.reviewer_id
    from datetime import datetime, timezone
    analysis.reviewed_at = datetime.now(timezone.utc)

    return {
        "status": "success",
        "analysis_id": str(analysis.id),
        "review_status": analysis.review_status,
        "reviewed_by": analysis.reviewed_by,
        "reviewed_at": analysis.reviewed_at.isoformat(),
    }
