"""Client portal: shared document download, approved summary PDF, lawyer contact card.

Every endpoint is client-only and reads only client-visible data (Rule 8):
documents through app.client_shared_document_file (shared, unrevoked, open case,
caller is a client member), summaries through the published-updates RLS policy,
and the lawyer card through app.client_case_lawyer_contact (lead lawyer, fields
the lawyer approved). A case or document the client cannot see is a 404.
"""

import asyncio
from zoneinfo import ZoneInfo
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import text

from app.auth.dependencies import ClientDep, SessionFactoryDep, UserSessionDep, request_ip
from app.auth.repository import write_audit_event
from app.documents.storage import StorageNotConfigured, get_store
from app.errors import problem_responses
from app.lawyer.photo import PHOTO_READ_LIMIT, WEBP_RESPONSE, check_size, read_photo
from app.rate_limit import enforce_user_quota
from app.lawyer.profile_schemas import LawyerContact
from app.pdf.render import Document, attachment_headers, render_pdf

router = APIRouter(prefix="/api/v1/client", tags=["client-portal"])

PDF_RESPONSE = {200: {"content": {"application/pdf": {}}, "description": "The PDF file (attachment)"}}
FILE_RESPONSE = {200: {"content": {"application/octet-stream": {}}, "description": "The file (attachment)"}}
EXTENSIONS = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg", "image/tiff": ".tiff"}


async def _audit(session, request: Request, user, action: str, object_type: str, object_id: UUID,
                 case_id: UUID) -> None:
    # The audit writer attributes rows to a case only for lawyer members; a client's case goes in details.
    await write_audit_event(
        session, action=action, actor_user_id=user.id, actor_role=user.role, object_type=object_type,
        object_id=object_id, details={"case_id": str(case_id)}, ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
    )


async def _lawyer_contact_row(session, case_id: UUID):
    row = (await session.execute(text("SELECT * FROM app.client_case_lawyer_contact(:c)"),
                                 {"c": case_id})).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Case was not found.")
    return row


@router.get(
    "/cases/{case_id}/lawyer",
    summary="Get the lawyer contact card",
    description=("The lead lawyer's name (always) and only the fields the lawyer chose to show clients: by default "
                 "photo, firm and phone; optionally email, Bar Council enrollment, courts, practice areas, years "
                 "of experience, office address, languages and bio. Hidden or empty fields are null. Open cases "
                 "with client membership only."),
    response_model=LawyerContact,
    responses=problem_responses(401, 403, 404, 422),
)
async def lawyer_contact(case_id: Annotated[UUID, Path(description="Case ID")], user: ClientDep,
                         session: UserSessionDep) -> LawyerContact:
    row = dict(await _lawyer_contact_row(session, case_id))
    return LawyerContact.model_validate({**row, "photo_id": row["avatar_id"]})


@router.get(
    "/cases/{case_id}/lawyer/photo",
    summary="Get the lawyer's photo",
    description=("The lead lawyer's photo (WebP, 512 or 96 pixels square), only when the lawyer shows it to "
                 "clients. Otherwise 404. Open cases with client membership only. At most 600 photo requests per "
                 "hour per user (429 with Retry-After)."),
    response_class=Response,
    responses={**WEBP_RESPONSE, **problem_responses(401, 403, 404, 422, 429, 503)},
)
async def lawyer_photo(request: Request, case_id: Annotated[UUID, Path(description="Case ID")], user: ClientDep,
                       session: UserSessionDep, session_factory: SessionFactoryDep,
                       size: Annotated[int, Query(description="Square size in pixels: 512 or 96")] = 96) -> Response:
    check_size(size)
    await enforce_user_quota(session_factory, user.id, PHOTO_READ_LIMIT)
    row = await _lawyer_contact_row(session, case_id)
    if row["avatar_id"] is None:
        raise HTTPException(status_code=404, detail="Photo was not found.")
    try:
        store = get_store(request.app.state.settings)
    except StorageNotConfigured as error:
        raise HTTPException(status_code=503, detail=f"NOT_CONFIGURED: {error}") from error
    return await read_photo(store, row["lawyer_user_id"], row["avatar_id"], size)


@router.get(
    "/documents/{document_id}/download",
    summary="Download a shared document",
    description=("Streams a document the lawyer shared with this client (attachment). Revoked, unshared, deleted "
                 "or another client's documents are 404. Audit-logged."),
    response_class=Response,
    responses={**FILE_RESPONSE, **problem_responses(401, 403, 404, 422, 503)},
)
async def download_document(request: Request, document_id: Annotated[UUID, Path(description="Document ID")],
                            user: ClientDep, session: UserSessionDep) -> Response:
    row = (await session.execute(text("SELECT * FROM app.client_shared_document_file(:d)"),
                                 {"d": document_id})).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Document was not found.")
    try:
        data = await asyncio.to_thread(get_store(request.app.state.settings).get, row["storage_key"])
    except StorageNotConfigured as error:
        raise HTTPException(status_code=503, detail=f"NOT_CONFIGURED: {error}") from error
    await _audit(session, request, user, "client.document_downloaded", "shared_document", row["shared_id"],
                 row["case_id"])
    name = row["display_name"]
    extension = EXTENSIONS.get(row["mime_type"], "")
    if extension and not name.lower().endswith(extension):
        name += extension
    return Response(content=data, media_type=row["mime_type"], headers=attachment_headers(name))


_PDF_COPY = {
    "en": {"eyebrow": "CASE UPDATE APPROVED BY YOUR LAWYER", "case": "Case", "published": "Published",
           "footer": ("Your lawyer approved this update for you. It explains what happened; it is not legal advice "
                      "and does not predict the outcome. Ask your lawyer if anything is unclear.")},
    "bn": {"eyebrow": "আপনার আইনজীবী অনুমোদিত মামলার হালনাগাদ", "case": "মামলা", "published": "প্রকাশিত",
           "footer": ("আপনার আইনজীবী এই হালনাগাদটি আপনার জন্য অনুমোদন করেছেন। এটি যা ঘটেছে তা ব্যাখ্যা করে; "
                      "এটি আইনি পরামর্শ নয় এবং ফলাফলের পূর্বাভাস দেয় না। কিছু অস্পষ্ট হলে আপনার আইনজীবীকে জিজ্ঞাসা করুন।")},
}


@router.get(
    "/updates/{update_id}/pdf",
    summary="Download an approved summary as PDF",
    description=("Server-generated PDF (embedded Noto Sans / Noto Sans Bengali) of a summary the lawyer approved "
                 "and published on an open case of this client. Drafts, withdrawn updates and other clients' "
                 "updates are 404. Audit-logged."),
    response_class=Response,
    responses={**PDF_RESPONSE, **problem_responses(401, 403, 404, 422)},
)
async def update_pdf(request: Request, update_id: Annotated[UUID, Path(description="Client update ID")],
                     user: ClientDep, session: UserSessionDep,
                     language: Annotated[Literal["en", "bn"], Query(description="Label language")] = "en") -> Response:
    # RLS: published updates of open cases where the caller is an active client member.
    row = (await session.execute(text(
        """
        SELECT u.id, u.case_id, u.title, u.body, u.published_at, c.title AS case_title
        FROM public.client_visible_updates u JOIN public.cases c ON c.id = u.case_id
        WHERE u.id = :u AND u.status = 'published'
        """), {"u": update_id})).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Summary was not found.")
    copy = _PDF_COPY[language]
    published = row["published_at"].astimezone(ZoneInfo("Asia/Dhaka")).date().isoformat() if row["published_at"] else ""
    pdf = await asyncio.to_thread(render_pdf, Document(
        eyebrow=copy["eyebrow"], title=row["title"],
        meta=[(copy["case"], row["case_title"]), (copy["published"], published)],
        sections=[], body=row["body"], footer=copy["footer"],
    ))
    await _audit(session, request, user, "client.summary_downloaded", "client_update", row["id"], row["case_id"])
    return Response(content=pdf, media_type="application/pdf",
                    headers=attachment_headers(f"case-update-{published or 'summary'}.pdf"))
