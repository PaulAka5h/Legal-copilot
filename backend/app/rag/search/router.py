from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request, status

from app.auth.dependencies import LawyerDep, UserSessionDep, request_ip
from app.auth.repository import write_audit_event
from app.cases.dependencies import CaseAccessDep
from app.errors import problem_responses
from app.rag.search.providers import ProviderNotConfigured, get_query_embedder, get_reranker
from app.rag.search.retrieval import hybrid_search
from app.rag.search.schemas import ResearchSearchHit, ResearchSearchRequest, ResearchSearchResponse

router = APIRouter(prefix="/api/v1/lawyer", tags=["legal-research"])


@router.post(
    "/cases/{case_id}/research/search",
    summary="Search approved Bangladesh statutes for a case",
    description=(
        "Hybrid search over the legal knowledge base: e5-large vector search (HNSW, cosine) "
        "and 'simple' full-text search fused with Reciprocal Rank Fusion (k=60), then a "
        "reranker (mock by default). Only approved, current statute versions are searched. "
        "With `incident_date`, sections not in force on that date are excluded; sections whose "
        "status is unknown are included and flagged. Bangla and English versions of the same "
        "section are merged and returned as alternates. Results are retrieved sources, not "
        "legal conclusions, and are marked unverified. Requires an active lawyer membership in "
        "the case. The query text is not logged; an audit event records counts only."
    ),
    response_model=ResearchSearchResponse,
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def search_case_research(
    request: Request,
    access: CaseAccessDep,
    user: LawyerDep,
    session: UserSessionDep,
    payload: Annotated[ResearchSearchRequest, Body(description="Search query and filters")],
) -> ResearchSearchResponse:
    try:
        embedder = get_query_embedder()
        reranker = get_reranker()
    except ProviderNotConfigured as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NOT_CONFIGURED: legal search models are not available on this server.",
        ) from error

    result = await hybrid_search(
        session,
        query=payload.query,
        embedder=embedder,
        reranker=reranker,
        language=payload.language,
        incident_date=payload.incident_date,
        k=payload.k,
    )
    await write_audit_event(
        session,
        action="legal_research.searched",
        actor_user_id=user.id,
        actor_role="lawyer",
        object_type="case",
        object_id=access.case_id,
        case_id=access.case_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        details={
            "results": len(result.hits),
            "k": payload.k,
            "language": payload.language,
            "incident_date": payload.incident_date.isoformat() if payload.incident_date else None,
            "reranker": result.reranker,
        },
    )
    return ResearchSearchResponse(
        case_id=access.case_id,
        results=[ResearchSearchHit(**asdict(hit)) for hit in result.hits],
        warnings=result.warnings,
        reranker=result.reranker,
        embedding_model=result.embedding_model,
        searched_versions=result.eligible_versions,
    )
