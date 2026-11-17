from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cases.schemas import CaseAccess, CaseCreate, CasePatch, CaseResponse
from app.tenancy import resolve_actor_organization

_CASE_FIELDS = """
    c.id, c.organization_id, c.reference_no, c.title, c.case_type,
    c.workflow_template_id, c.court, c.court_case_no, c.jurisdiction,
    c.opposing_party, c.description, c.internal_notes, c.client_objectives,
    c.status, c.current_stage, c.key_dates, c.closed_at, c.closed_by,
    c.retention_until, c.created_by, c.created_at, c.updated_at
"""
DEFAULT_CASE_STAGES = (
    ("Case intake", "Case intake"),
    ("Document review", "Document review"),
    ("Legal research", "Legal research"),
    ("Strategy preparation", "Strategy preparation"),
    ("Hearings", "Hearings"),
    ("Resolution", "Resolution"),
)


async def list_cases(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
) -> list[CaseResponse]:
    result = await session.execute(
        text(
            f"""
            SELECT {_CASE_FIELDS}
            FROM public.cases AS c
            WHERE EXISTS (
              SELECT 1 FROM public.case_members AS cm
              WHERE cm.case_id = c.id
                AND cm.user_id = :acting_user_id
                AND cm.status = 'active')
            ORDER BY c.updated_at DESC, c.id
            """
        ),
        {"acting_user_id": acting_user_id},
    )
    return [
        CaseResponse.model_validate(dict(row))
        for row in result.mappings().all()
    ]


async def get_case_membership(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
    case_id: UUID,
) -> CaseAccess | None:
    result = await session.execute(
        text(
            """
            SELECT role, permissions
            FROM public.case_members
            WHERE case_id = :case_id
              AND user_id = :acting_user_id
              AND status = 'active'
            """
        ),
        {"acting_user_id": acting_user_id, "case_id": case_id},
    )
    row = result.mappings().one_or_none()
    if row is None:
        return None
    return CaseAccess(
        case_id=case_id,
        role=row["role"],
        permissions=row["permissions"],
    )


async def get_case(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
    case_id: UUID,
) -> CaseResponse | None:
    result = await session.execute(
        text(
            f"""
            SELECT {_CASE_FIELDS}
            FROM public.cases AS c
            WHERE c.id = :case_id
              AND EXISTS (
                SELECT 1 FROM public.case_members AS cm
                WHERE cm.case_id = :case_id
                  AND cm.user_id = :acting_user_id
                  AND cm.status = 'active')
            """
        ),
        {"acting_user_id": acting_user_id, "case_id": case_id},
    )
    row = result.mappings().one_or_none()
    return CaseResponse.model_validate(dict(row)) if row is not None else None


async def create_case(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
    payload: CaseCreate,
) -> CaseResponse:
    organization_id = await resolve_actor_organization(session, acting_user_id)
    case_id = uuid4()
    await session.execute(
        text(
            """
            INSERT INTO public.cases
              (id, organization_id, reference_no, title, case_type, court,
               court_case_no, jurisdiction, opposing_party, description,
               internal_notes, client_objectives, current_stage, created_by)
            VALUES
              (:id, :organization_id, :reference_no, :title, :case_type, :court,
               :court_case_no, :jurisdiction, :opposing_party, :description,
               :internal_notes, :client_objectives, :current_stage, :acting_user_id)
            """
        ),
        {
            "id": case_id,
            "organization_id": organization_id,
            "acting_user_id": acting_user_id,
            "current_stage": DEFAULT_CASE_STAGES[0][0],
            **payload.model_dump(),
        },
    )
    await session.execute(
        text(
            """
            INSERT INTO public.case_members
              (case_id, organization_id, user_id, role, permissions, granted_by)
            VALUES
              (:case_id, :organization_id, :acting_user_id, 'lead_lawyer',
               CAST(:permissions AS jsonb), :acting_user_id)
            """
        ),
        {
            "case_id": case_id,
            "organization_id": organization_id,
            "acting_user_id": acting_user_id,
            "permissions": '{"can_edit_case":true,"can_close_case":true}',
        },
    )
    await insert_default_stages(
        session,
        case_id=case_id,
        organization_id=organization_id,
    )
    case = await get_case(
        session,
        acting_user_id=acting_user_id,
        case_id=case_id,
    )
    if case is None:
        raise RuntimeError("Newly created case is not visible to its lead lawyer.")
    return case


async def insert_default_stages(
    session: AsyncSession,
    *,
    case_id: UUID,
    organization_id: UUID,
) -> None:
    for position, (name, client_label) in enumerate(DEFAULT_CASE_STAGES, start=1):
        await session.execute(
            text(
                """
                INSERT INTO public.case_stages
                  (case_id, organization_id, position, name, client_label, status)
                VALUES
                  (:case_id, :organization_id, :position, :name, :client_label,
                   :status)
                """
            ),
            {
                "case_id": case_id,
                "organization_id": organization_id,
                "position": position,
                "name": name,
                "client_label": client_label,
                "status": "current" if position == 1 else "pending",
            },
        )


async def patch_case(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
    case_id: UUID,
    payload: CasePatch,
) -> CaseResponse | None:
    updates = payload.model_dump(exclude_unset=True)
    columns = {
        "reference_no": "reference_no",
        "title": "title",
        "case_type": "case_type",
        "court": "court",
        "court_case_no": "court_case_no",
        "jurisdiction": "jurisdiction",
        "opposing_party": "opposing_party",
        "description": "description",
        "internal_notes": "internal_notes",
        "client_objectives": "client_objectives",
    }
    assignments = ", ".join(f"{columns[field]} = :{field}" for field in updates)
    result = await session.execute(
        text(
            f"""
            UPDATE public.cases AS c
            SET {assignments}, updated_at = now()
            WHERE c.id = :case_id
              AND EXISTS (
                SELECT 1 FROM public.case_members AS cm
                WHERE cm.case_id = :case_id
                  AND cm.user_id = :acting_user_id
                  AND cm.status = 'active')
            RETURNING {_CASE_FIELDS}
            """
        ),
        {
            **updates,
            "acting_user_id": acting_user_id,
            "case_id": case_id,
        },
    )
    row = result.mappings().one_or_none()
    return CaseResponse.model_validate(dict(row)) if row is not None else None
