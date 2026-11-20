from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, status
from sqlalchemy import text

from app.ai.llm import LLMNotConfigured, mock_allowed, resolve_provider
from app.auth.dependencies import LawyerDep, SessionFactoryDep, UserSessionDep, request_ip, require_same_origin
from app.auth.repository import write_audit_event
from app.case_analysis.service import Thresholds
from app.cases.dependencies import CaseAccessDep, CaseAccessShortDep, require_case_permission
from app.database import user_transaction
from app.documents.repository import case_status
from app.errors import problem_responses
from app.hearing_updates import service
from app.hearing_updates.schemas import HearingCreate, HearingOut, HearingReassessment, HearingUpdateCreate, TimelineEntry
from app.rag.search.providers import ProviderNotConfigured, get_query_embedder, get_reranker

router = APIRouter(prefix="/api/v1/lawyer/cases/{case_id}", tags=["hearings"])
HEARING_FIELDS = ("id, case_id, scheduled_at, purpose, court_room, date_status, date_confirmed_by, "
                  "date_confirmed_at, created_at")


async def _open_case(session, case_id: UUID) -> UUID:
    found = await case_status(session, case_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Case was not found.")
    if found[0] == "closed":
        raise HTTPException(status_code=409, detail="Closed cases are read-only.")
    return found[1]


@router.post(
    "/hearings",
    summary="Add a hearing",
    description="Lawyer-entered hearing. The date is confirmed only when the lawyer says so (Rule 5).",
    response_model=HearingOut,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(401, 403, 404, 409, 422),
    dependencies=[Depends(require_same_origin)],
)
async def create_hearing(request: Request, access: CaseAccessDep, user: LawyerDep, session: UserSessionDep,
                         payload: Annotated[HearingCreate, Body(description="Hearing details")]) -> HearingOut:
    organization_id = await _open_case(session, access.case_id)
    confirmed = payload.date_confirmed and payload.scheduled_at is not None
    row = (await session.execute(text(
        f"""
        INSERT INTO public.hearings (case_id, organization_id, scheduled_at, purpose, court_room, date_status,
          date_confirmed_by, date_confirmed_at)
        VALUES (:c, :o, :d, :p, :r, :s, :by, CASE WHEN :confirmed THEN now() END)
        RETURNING {HEARING_FIELDS}
        """), {"c": access.case_id, "o": organization_id, "d": payload.scheduled_at, "p": payload.purpose,
               "r": payload.court_room, "s": "confirmed" if confirmed else "tentative",
               "by": user.id if confirmed else None, "confirmed": confirmed})).mappings().one()
    await write_audit_event(session, action="hearing.created", actor_user_id=user.id, actor_role="lawyer",
                            object_type="hearing", object_id=row["id"], case_id=access.case_id,
                            ip_address=request_ip(request), user_agent=None,
                            request_id=getattr(request.state, "request_id", None),
                            details={"date_status": row["date_status"]})
    return HearingOut(**row)


@router.get("/hearings", summary="List hearings", description="All hearings of the case, by date.",
            response_model=list[HearingOut], responses=problem_responses(401, 403, 404))
async def list_hearings(access: CaseAccessDep, session: UserSessionDep) -> list[HearingOut]:
    rows = await session.execute(text(f"SELECT {HEARING_FIELDS} FROM public.hearings WHERE case_id = :c "
                                      "ORDER BY scheduled_at NULLS LAST, created_at"), {"c": access.case_id})
    return [HearingOut(**r) for r in rows.mappings()]


@router.get("/hearings/timeline", summary="Hearing timeline",
            description="Every hearing update (append-only versions), oldest first.",
            response_model=list[TimelineEntry], responses=problem_responses(401, 403, 404))
async def hearing_timeline(access: CaseAccessDep, session: UserSessionDep) -> list[TimelineEntry]:
    rows = await session.execute(text(
        """
        SELECT id AS hearing_update_id, hearing_id, version, orders_directions AS order_text, happened AS notes,
               next_hearing_date, next_hearing_confirmed, source_label, created_at
        FROM public.hearing_updates WHERE case_id = :c ORDER BY created_at, id
        """), {"c": access.case_id})
    return [TimelineEntry(**r) for r in rows.mappings()]


@router.post(
    "/hearings/{hearing_id}/updates",
    summary="Record a hearing update and reassess",
    description=(
        "Appends the update to the timeline (order text, notes, next date), adds the order text as a "
        "lawyer_entered fact, re-runs the case analysis and the strategy tree on the updated confirmed facts, and "
        "returns the reassessment diff: changed findings, closed and new options, tree version, and tasks. A next "
        "date creates a confirmed hearing only when the lawyer confirms it; a date found in the order text is a "
        "draft suggestion. A plain-language client summary is saved as a draft client update; the client sees it "
        "only after the lawyer publishes it. Requires can_run_ai."
    ),
    response_model=HearingReassessment,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def submit_hearing_update(
    request: Request, access: CaseAccessShortDep, user: LawyerDep, session_factory: SessionFactoryDep,
    hearing_id: Annotated[UUID, Path(description="Hearing ID")],
    payload: Annotated[HearingUpdateCreate, Body(description="Order, notes, next date")],
) -> HearingReassessment:
    require_case_permission(access, "can_run_ai")
    async with user_transaction(session_factory, user.id) as session:
        await _open_case(session, access.case_id)
    settings = request.app.state.settings
    try:
        llm = resolve_provider(settings, getattr(request.app.state, "llm_transport", None))
        embedder, reranker = get_query_embedder(), get_reranker()
    except (LLMNotConfigured, ProviderNotConfigured) as error:
        raise HTTPException(status_code=503, detail=f"NOT_CONFIGURED: {error}") from error
    try:
        reassessment_id = await service.submit_update(
            session_factory, case_id=access.case_id, hearing_id=hearing_id, user_id=user.id, payload=payload,
            embedder=embedder, reranker=reranker, llm=llm, allow_mock=mock_allowed(settings),
            thresholds=Thresholds(settings.analysis_min_similarity, settings.analysis_min_rerank_score))
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Hearing was not found.") from error
    except Exception as error:  # analysis needs confirmed facts etc.
        detail = getattr(error, "detail", None)
        if detail:
            raise HTTPException(status_code=getattr(error, "status_code", 409), detail=detail) from error
        raise
    async with user_transaction(session_factory, user.id) as session:
        row = (await session.execute(text(service.REASSESSMENT_QUERY + " AND r.id = :i"),
                                     {"c": access.case_id, "i": reassessment_id})).mappings().one()
    return HearingReassessment(**service.reassessment_out(dict(row)))


@router.get("/reassessments", summary="List hearing reassessments",
            description="All reassessments of the case, newest first.",
            response_model=list[HearingReassessment], responses=problem_responses(401, 403, 404))
async def list_reassessments(access: CaseAccessDep, session: UserSessionDep) -> list[HearingReassessment]:
    rows = await session.execute(text(service.REASSESSMENT_QUERY + " ORDER BY r.created_at DESC"),
                                 {"c": access.case_id})
    return [HearingReassessment(**service.reassessment_out(dict(r))) for r in rows.mappings()]
