from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Body, HTTPException, Path, Query, Request, status

from app.ai.llm import LLMNotConfigured, resolve_provider
from app.auth.dependencies import require_same_origin, LawyerDep, SessionFactoryDep, UserSessionDep, request_ip
from app.auth.repository import write_audit_event
from app.cases.dependencies import CaseAccessDep
from app.database import user_transaction
from app.documents import repository as docs
from app.errors import problem_responses
from app.facts import repository as repo
from app.facts import service
from app.facts.extractor import LLMFactExtractor, MockFactExtractor
from app.facts.schemas import (
    ConfirmedFactSet,
    ExtractionRequest,
    ExtractionResponse,
    FactCreateRequest,
    FactEditRequest,
    FactOut,
    FactRejectRequest,
    FactReviewRequest,
)

router = APIRouter(prefix="/api/v1/lawyer/cases/{case_id}/facts", tags=["case-facts"])
FactIdPath = Annotated[UUID, Path(description="Fact version ID")]


def _out(rows: list[dict]) -> list[FactOut]:
    return [FactOut(**r) for r in rows]


async def _open_case(session, case_id: UUID) -> UUID:
    found = await docs.case_status(session, case_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Case was not found.")
    if found[0] == "closed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Closed cases are read-only.")
    return found[1]


async def _current_fact(session, case_id: UUID, fact_id: UUID) -> dict:
    fact = await repo.get_fact(session, case_id, fact_id)
    if fact is None:
        raise HTTPException(status_code=404, detail="Fact was not found.")
    return fact


async def _audit(session, request: Request, user_id: UUID, case_id: UUID, action: str, fact_id: UUID,
                 details: dict) -> None:
    await write_audit_event(
        session, action=action, actor_user_id=user_id, actor_role="lawyer", object_type="case_fact",
        object_id=fact_id, case_id=case_id, ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None), details=details,
    )


@router.post(
    "/extractions",
    summary="Extract draft facts from case documents",
    description=(
        "Reads the current text of the case's processed pages (optionally only `document_ids`) and asks "
        "the configured extractor for structured facts: parties, dates, places, acts or omissions, "
        "documents, relief sought. Page text is sent as untrusted, delimited data. Output must match a "
        "JSON schema (validated with Pydantic); an invalid batch is retried once, then the run is "
        "marked extraction_failed and nothing is stored. Every quote is checked in code against the "
        "exact page version; failed checks are flagged and cannot be confirmed as document_says. All "
        "facts are drafts until a lawyer confirms them. Providers: the mock extractor (development "
        "and test only) or a local Ollama server; otherwise 503 NOT_CONFIGURED."
    ),
    response_model=ExtractionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def extract_facts(
    request: Request,
    access: CaseAccessDep,
    user: LawyerDep,
    session_factory: SessionFactoryDep,
    payload: Annotated[ExtractionRequest, Body(description="Which documents to read")],
) -> ExtractionResponse:
    try:
        llm = resolve_provider(request.app.state.settings, getattr(request.app.state, "llm_transport", None))
    except LLMNotConfigured as error:
        raise HTTPException(status_code=503, detail=f"NOT_CONFIGURED: {error}") from error
    extractor = getattr(request.app.state, "fact_extractor", None) or (
        MockFactExtractor() if llm is None else LLMFactExtractor(llm)
    )
    async with user_transaction(session_factory, user.id) as session:
        organization_id = await _open_case(session, access.case_id)
    try:
        result = await service.run_extraction(
            session_factory, case_id=access.case_id, organization_id=organization_id, user_id=user.id,
            document_ids=payload.document_ids, extractor=extractor,
        )
    except service.FactError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    async with user_transaction(session_factory, user.id) as session:
        facts = await repo.facts_for_run(session, result.run_id)
    return ExtractionResponse(
        run_id=result.run_id, status=result.status, provider=extractor.provider, model=extractor.model,
        attempts=result.attempts, pages_read=result.pages_read, facts_created=len(result.fact_ids),
        source_check_failed=result.source_check_failed, facts=_out(facts),
    )


@router.get(
    "",
    summary="List current facts",
    description="Lists the current version of each fact with its sources. Rejected facts are hidden by default.",
    response_model=list[FactOut],
    responses=problem_responses(401, 403, 404),
)
async def list_facts(
    access: CaseAccessDep,
    session: UserSessionDep,
    review_status: Annotated[Literal["draft", "lawyer_reviewed", "lawyer_rejected"] | None,
                             Query(description="Filter by review status")] = None,
    statement_type: Annotated[Literal["document_says", "lawyer_entered", "ai_inference", "assumption"] | None,
                              Query(description="Filter by statement type")] = None,
    include_rejected: Annotated[bool, Query(description="Include rejected facts")] = False,
) -> list[FactOut]:
    return _out(await repo.list_facts(session, access.case_id, review_status, statement_type,
                                      include_rejected or review_status == "lawyer_rejected"))


@router.get(
    "/confirmed",
    summary="Facts usable in analysis",
    description=(
        "The confirmed fact set: current facts that are lawyer_entered or lawyer-confirmed and not rejected "
        "(view case_facts_for_analysis). fact_set_hash identifies the exact set; analysis records it."
    ),
    response_model=ConfirmedFactSet,
    responses=problem_responses(401, 403, 404),
)
async def confirmed_facts(access: CaseAccessDep, session: UserSessionDep) -> ConfirmedFactSet:
    facts = await repo.facts_for_analysis(session, access.case_id)
    return ConfirmedFactSet(case_id=access.case_id, fact_set_hash=service.fact_set_hash(facts), facts=_out(facts))


@router.post(
    "",
    summary="Enter a fact as a lawyer",
    description=(
        "Creates a lawyer_entered (or assumption) fact. Optional sources must cite processed pages of this "
        "case; each quote is checked against the current page text."
    ),
    response_model=FactOut,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(401, 403, 404, 409, 422),
    dependencies=[Depends(require_same_origin)],
)
async def create_fact(
    request: Request, access: CaseAccessDep, user: LawyerDep, session: UserSessionDep,
    payload: Annotated[FactCreateRequest, Body(description="The fact")],
) -> FactOut:
    organization_id = await _open_case(session, access.case_id)
    try:
        fact_id = await service.create_lawyer_fact(session, case_id=access.case_id, organization_id=organization_id,
                                                   user_id=user.id, payload=payload)
    except service.FactError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    await _audit(session, request, user.id, access.case_id, "fact.created", fact_id,
                 {"statement_type": payload.statement_type, "sources": len(payload.sources)})
    return FactOut(**await repo.get_fact(session, access.case_id, fact_id))


@router.patch(
    "/{fact_id}",
    summary="Edit a fact (creates a new version)",
    description=(
        "Never overwrites: inserts version n+1 and marks the old version not current. Changing the statement, "
        "statement type, or sources makes it a lawyer_entered fact with re-checked quotes; changing only "
        "category, attributes, or standing keeps its provenance. The new version is a draft."
    ),
    response_model=FactOut,
    responses=problem_responses(401, 403, 404, 409, 422),
    dependencies=[Depends(require_same_origin)],
)
async def edit_fact(
    request: Request, access: CaseAccessDep, user: LawyerDep, session: UserSessionDep, fact_id: FactIdPath,
    payload: Annotated[FactEditRequest, Body(description="Fields to change")],
) -> FactOut:
    organization_id = await _open_case(session, access.case_id)
    current = await _current_fact(session, access.case_id, fact_id)
    try:
        new_id = await service.edit_fact(session, case_id=access.case_id, organization_id=organization_id,
                                         user_id=user.id, current=current, payload=payload)
    except service.FactError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    await _audit(session, request, user.id, access.case_id, "fact.edited", new_id,
                 {"supersedes_id": str(fact_id), "fields": sorted(payload.model_fields_set)})
    return FactOut(**await repo.get_fact(session, access.case_id, new_id))


async def _review(request, access, user, session, fact_id, status_value, note, action) -> FactOut:
    await _open_case(session, access.case_id)
    current = await _current_fact(session, access.case_id, fact_id)
    try:
        await service.review(session, current=current, status=status_value, user_id=user.id, note=note)
    except service.FactError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    await _audit(session, request, user.id, access.case_id, action, fact_id,
                 {"statement_type": current["statement_type"], "origin": current["origin"]})
    return FactOut(**await repo.get_fact(session, access.case_id, fact_id))


@router.post(
    "/{fact_id}/confirm",
    summary="Confirm a draft fact",
    description=(
        "Marks the current draft version lawyer_reviewed, recording who and when. A document_says fact can be "
        "confirmed only if its quote check passed."
    ),
    response_model=FactOut,
    responses=problem_responses(401, 403, 404, 409, 422),
    dependencies=[Depends(require_same_origin)],
)
async def confirm_fact(
    request: Request, access: CaseAccessDep, user: LawyerDep, session: UserSessionDep, fact_id: FactIdPath,
    payload: Annotated[FactReviewRequest, Body(description="Optional note")] = FactReviewRequest(),
) -> FactOut:
    return await _review(request, access, user, session, fact_id, "lawyer_reviewed", payload.note, "fact.confirmed")


@router.post(
    "/{fact_id}/reject",
    summary="Reject a draft fact",
    description="Marks the current draft version lawyer_rejected with a reason. Rejected facts are never used.",
    response_model=FactOut,
    responses=problem_responses(401, 403, 404, 409, 422),
    dependencies=[Depends(require_same_origin)],
)
async def reject_fact(
    request: Request, access: CaseAccessDep, user: LawyerDep, session: UserSessionDep, fact_id: FactIdPath,
    payload: Annotated[FactRejectRequest, Body(description="Reason")],
) -> FactOut:
    return await _review(request, access, user, session, fact_id, "lawyer_rejected", payload.note, "fact.rejected")


@router.get(
    "/{fact_id}/history",
    summary="Version history of a fact",
    description="All versions of the fact's lineage, newest first, each with its sources.",
    response_model=list[FactOut],
    responses=problem_responses(401, 403, 404),
)
async def fact_history(access: CaseAccessDep, session: UserSessionDep, fact_id: FactIdPath) -> list[FactOut]:
    history = await repo.lineage_history(session, access.case_id, fact_id)
    if not history:
        raise HTTPException(status_code=404, detail="Fact was not found.")
    return _out(history)
