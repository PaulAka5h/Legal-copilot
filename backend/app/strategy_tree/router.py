from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request, status

from app.ai.llm import LLMNotConfigured, mock_allowed, resolve_provider
from app.auth.dependencies import LawyerDep, SessionFactoryDep, UserSessionDep, require_same_origin
from app.cases.dependencies import CaseAccessDep, CaseAccessShortDep, require_case_permission
from app.database import user_transaction
from app.documents.repository import case_status
from app.errors import problem_responses
from app.strategy_tree import service
from app.strategy_tree.schemas import StrategyComparison, StrategyOut, StrategyRequest, StrategyVersionSummary

router = APIRouter(prefix="/api/v1/lawyer/cases/{case_id}/strategy", tags=["strategy-tree"])


@router.post(
    "",
    summary="Build a strategy game tree (new version)",
    description=(
        "Builds a bounded game tree from the latest (or a given) analysis version: our moves (ply 1, at most 4), "
        "opponent or court responses (ply 2, at most 3 per move), our counters (ply 3, at most 3 per response). "
        "Every node carries legal_basis citations, requirements, risk/cost/time (low/medium/high/unknown), a "
        "strength label and reasons. Each citation must be a provision the analysis retrieved and passes the "
        "deterministic verifier; nodes without a verified basis are marked unverified. No percentages. No "
        "precedent is cited unless judgments are in the knowledge base (otherwise the precedent_note says so). "
        "Each run is a new immutable version. Requires can_run_ai."
    ),
    response_model=StrategyOut,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def create_strategy(
    request: Request, access: CaseAccessShortDep, user: LawyerDep, session_factory: SessionFactoryDep,
    payload: Annotated[StrategyRequest, Body(description="Which analysis version to build from")] = StrategyRequest(),
) -> StrategyOut:
    require_case_permission(access, "can_run_ai")
    async with user_transaction(session_factory, user.id) as session:
        found = await case_status(session, access.case_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Case was not found.")
    if found[0] == "closed":
        raise HTTPException(status_code=409, detail="Closed cases are read-only.")
    settings = request.app.state.settings
    try:
        llm = resolve_provider(settings, getattr(request.app.state, "llm_transport", None))
    except LLMNotConfigured as error:
        raise HTTPException(status_code=503, detail=f"NOT_CONFIGURED: {error}") from error
    try:
        tree_id = await service.run_strategy(session_factory, case_id=access.case_id, user_id=user.id,
                                             analysis_version=payload.analysis_version, llm=llm,
                                             allow_mock=mock_allowed(settings))
    except service.StrategyError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    async with user_transaction(session_factory, user.id) as session:
        return StrategyOut(**service.to_out(await service.get_tree(session, access.case_id, tree_id=tree_id)))


@router.get("", summary="Latest strategy tree", description="Returns the newest strategy tree version.",
            response_model=StrategyOut, responses=problem_responses(401, 403, 404))
async def latest_strategy(access: CaseAccessDep, session: UserSessionDep) -> StrategyOut:
    row = await service.get_tree(session, access.case_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No strategy tree yet.")
    return StrategyOut(**service.to_out(row))


@router.get("/versions", summary="List strategy tree versions", description="All versions, newest first.",
            response_model=list[StrategyVersionSummary], responses=problem_responses(401, 403, 404))
async def strategy_versions(access: CaseAccessDep, session: UserSessionDep) -> list[StrategyVersionSummary]:
    return [StrategyVersionSummary(**r) for r in await service.list_trees(session, access.case_id)]


@router.get(
    "/compare",
    summary="Compare two strategy tree versions",
    description=(
        "Deterministic diff between two versions: nodes added, removed, or changed (strength, risk, cost, time, "
        "verified), plus closed_options and new_options for our first moves."
    ),
    response_model=StrategyComparison,
    responses=problem_responses(401, 403, 404, 422),
)
async def compare_strategy(
    access: CaseAccessDep, session: UserSessionDep,
    base: Annotated[int, Query(ge=1, description="Earlier version")],
    target: Annotated[int, Query(ge=1, description="Later version")],
) -> StrategyComparison:
    before = await service.get_tree(session, access.case_id, version=base)
    after = await service.get_tree(session, access.case_id, version=target)
    if before is None or after is None:
        raise HTTPException(status_code=404, detail="Strategy version not found.")
    return StrategyComparison(**service.compare_trees(service.to_out(before), service.to_out(after)))


@router.get("/versions/{version}", summary="Get one strategy tree version", description="A specific version.",
            response_model=StrategyOut, responses=problem_responses(401, 403, 404))
async def strategy_version(access: CaseAccessDep, session: UserSessionDep,
                           version: Annotated[int, Path(ge=1, description="Version number")]) -> StrategyOut:
    row = await service.get_tree(session, access.case_id, version=version)
    if row is None:
        raise HTTPException(status_code=404, detail="Strategy version not found.")
    return StrategyOut(**service.to_out(row))
