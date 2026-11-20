from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, status

from app.ai.llm import LLMNotConfigured, mock_allowed, resolve_provider
from app.auth.dependencies import LawyerDep, SessionFactoryDep, UserSessionDep, require_same_origin
from app.case_analysis import service
from app.case_analysis.schemas import AnalysisOut, AnalysisRequest, AnalysisVersionSummary
from app.cases.dependencies import CaseAccessDep, CaseAccessShortDep, require_case_permission
from app.database import user_transaction
from app.documents.repository import case_status
from app.errors import problem_responses
from app.rag.search.providers import ProviderNotConfigured, get_query_embedder, get_reranker

router = APIRouter(prefix="/api/v1/lawyer/cases/{case_id}/analysis", tags=["case-analysis"])


def model_settings(request: Request):
    settings = request.app.state.settings
    try:
        llm = resolve_provider(settings, getattr(request.app.state, "llm_transport", None))
        return llm, mock_allowed(settings), get_query_embedder(), get_reranker()
    except (LLMNotConfigured, ProviderNotConfigured) as error:
        raise HTTPException(status_code=503, detail=f"NOT_CONFIGURED: {error}") from error


@router.post(
    "",
    summary="Run a case analysis (new version)",
    description=(
        "Reads only the confirmed fact set (view case_facts_for_analysis) and records its hash. For each fact it "
        "generates search queries and retrieves approved statute text (Step B search, filtered by incident_date). "
        "If no provision reaches the relevance threshold it abstains with insufficient_information and lists what "
        "is missing. Otherwise it builds element-by-element findings (legal ingredients quoted from the retrieved "
        "provision, each mapped to a confirmed fact or marked missing/disputed, strength strong/moderate/weak/"
        "insufficient with reasons, statement_type ai_inference). Every citation passes a deterministic verifier "
        "(chunk exists, approved, in force or flagged, quote is an NFC substring); failures are stripped or "
        "labelled unverified. No precedents are cited unless judgments exist in the knowledge base. Each run is a "
        "new immutable version. Requires can_run_ai."
    ),
    response_model=AnalysisOut,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def create_analysis(
    request: Request,
    access: CaseAccessShortDep,
    user: LawyerDep,
    session_factory: SessionFactoryDep,
    payload: Annotated[AnalysisRequest, Body(description="Incident date and language filter")] = AnalysisRequest(),
) -> AnalysisOut:
    require_case_permission(access, "can_run_ai")
    async with user_transaction(session_factory, user.id) as session:
        found = await case_status(session, access.case_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Case was not found.")
    if found[0] == "closed":
        raise HTTPException(status_code=409, detail="Closed cases are read-only.")
    llm, allow_mock, embedder, reranker = model_settings(request)
    settings = request.app.state.settings
    try:
        analysis_id = await service.run_analysis(
            session_factory, case_id=access.case_id, user_id=user.id, incident_date=payload.incident_date,
            language=payload.language, embedder=embedder, reranker=reranker, llm=llm, allow_mock=allow_mock,
            thresholds=service.Thresholds(settings.analysis_min_similarity, settings.analysis_min_rerank_score),
        )
    except service.AnalysisError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    async with user_transaction(session_factory, user.id) as session:
        row = await service.get_analysis_by_id(session, access.case_id, analysis_id)
    return AnalysisOut(**service.to_out(row))


@router.get(
    "",
    summary="Latest case analysis",
    description="Returns the newest analysis version for the case.",
    response_model=AnalysisOut,
    responses=problem_responses(401, 403, 404),
)
async def latest_analysis(access: CaseAccessDep, session: UserSessionDep) -> AnalysisOut:
    row = await service.get_analysis(session, access.case_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No analysis yet.")
    return AnalysisOut(**service.to_out(row))


@router.get(
    "/versions",
    summary="List analysis versions",
    description="All analysis versions, newest first. Versions are never overwritten.",
    response_model=list[AnalysisVersionSummary],
    responses=problem_responses(401, 403, 404),
)
async def analysis_versions(access: CaseAccessDep, session: UserSessionDep) -> list[AnalysisVersionSummary]:
    return [AnalysisVersionSummary(**r) for r in await service.list_versions(session, access.case_id)]


@router.get(
    "/versions/{version}",
    summary="Get one analysis version",
    description="Returns a specific analysis version.",
    response_model=AnalysisOut,
    responses=problem_responses(401, 403, 404),
)
async def analysis_version(
    access: CaseAccessDep, session: UserSessionDep,
    version: Annotated[int, Path(ge=1, description="Version number")],
) -> AnalysisOut:
    row = await service.get_analysis(session, access.case_id, version)
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis version not found.")
    return AnalysisOut(**service.to_out(row))
