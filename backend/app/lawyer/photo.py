"""Lawyer profile photo: upload/replace, remove, and serve the lawyer's own photo.

Photos are processed by app.lawyer.avatar (type sniffed from bytes, metadata
stripped, WebP 512 and 96) and stored at users/{user_id}/avatar/. They are only
ever served through authorized endpoints: here for the lawyer themself, and
/api/v1/client/cases/{case_id}/lawyer/photo for their clients when the lawyer
shows the photo. There is no endpoint that takes another lawyer's user ID.
"""

import asyncio
import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import LawyerDep, SessionFactoryDep, UserSessionDep, request_ip, require_same_origin
from app.auth.repository import write_audit_event
from app.documents.storage import ObjectStore, StorageNotConfigured, get_store
from app.errors import problem_responses
from app.lawyer.avatar import MAX_PHOTO_BYTES, SIZES, PhotoRejected, avatar_key, process_photo
from app.rate_limit import RateLimit, enforce_user_quota
from app.tenancy import resolve_actor_organization

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/lawyer/profile/photo", tags=["lawyer-profile"])

WEBP_RESPONSE = {200: {"content": {"image/webp": {}}, "description": "The photo (WebP)"}}
NOT_CONFIGURED = 503
# Per signed-in user. Uploads decode an image; removals share the bucket. Serving allows normal browsing
# (pages show the 96 px photo; browsers cache it privately for a day).
PHOTO_WRITE_LIMIT = RateLimit("profile_photo_write", limit=10, window_seconds=3600)
PHOTO_READ_LIMIT = RateLimit("profile_photo_read", limit=600, window_seconds=3600)


class PhotoResponse(BaseModel):
    photo_id: UUID | None = Field(description="The current photo version; null after removal")


def check_size(size: int) -> None:
    if size not in SIZES:
        raise HTTPException(status_code=422, detail="size must be 512 or 96.")


def photo_headers() -> dict[str, str]:
    # URLs carry the photo version (?v=), so a private cache cannot show a stale photo.
    return {"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"}


def _store(request: Request) -> ObjectStore:
    try:
        return get_store(request.app.state.settings)
    except StorageNotConfigured as error:
        raise HTTPException(status_code=NOT_CONFIGURED, detail=f"NOT_CONFIGURED: {error}") from error


async def read_photo(store: ObjectStore, user_id: UUID, avatar_id: UUID, size: int) -> Response:
    try:
        data = await asyncio.to_thread(store.get, avatar_key(user_id, avatar_id, size))
    except StorageNotConfigured as error:
        raise HTTPException(status_code=NOT_CONFIGURED, detail=f"NOT_CONFIGURED: {error}") from error
    except Exception as error:  # missing object or storage outage; never leak the key
        raise HTTPException(status_code=404, detail="Photo was not found.") from error
    return Response(content=data, media_type="image/webp", headers=photo_headers())


def _delete_objects(store: ObjectStore, user_id: UUID, avatar_id: UUID) -> None:
    for size in SIZES:
        try:
            store.delete(avatar_key(user_id, avatar_id, size))
        except Exception:  # best effort; an orphan is unreachable through the API
            logger.warning("profile photo object cleanup failed", extra={"user_id": str(user_id)})


async def _current_avatar(session: AsyncSession, user_id: UUID) -> UUID | None:
    return (await session.execute(
        text("SELECT avatar_id FROM public.lawyer_profiles WHERE user_id = :u"), {"u": user_id},
    )).scalar_one_or_none()


async def _audit(session: AsyncSession, request: Request, user, action: str, details: dict) -> None:
    await write_audit_event(
        session, action=action, actor_user_id=user.id, actor_role=user.role, object_type="user",
        object_id=user.id, organization_id=await resolve_actor_organization(session, user.id),
        ip_address=request_ip(request), user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None), details=details,
    )


@router.put(
    "",
    summary="Upload or replace the profile photo",
    description=(
        "JPEG, PNG or WebP up to 5 MB, detected from the file content (the extension and declared type are "
        "ignored). Images over 16 megapixels are refused before decoding. The server strips all metadata "
        "(EXIF, GPS, ICC), center-crops to 512x512 plus a 96x96 thumbnail, and stores WebP only. The previous "
        "photo is deleted. At most 10 uploads or removals per hour per user (429 with Retry-After). "
        "Audit-logged without image content."
    ),
    response_model=PhotoResponse,
    responses=problem_responses(401, 403, 413, 415, 422, 429, 503),
    dependencies=[Depends(require_same_origin)],
)
async def upload_photo(
    request: Request,
    background: BackgroundTasks,
    user: LawyerDep,
    session: UserSessionDep,
    session_factory: SessionFactoryDep,
    file: Annotated[UploadFile, File(description="The photo (JPEG, PNG or WebP, at most 5 MB)")],
) -> PhotoResponse:
    await enforce_user_quota(session_factory, user.id, PHOTO_WRITE_LIMIT)
    data = await file.read(MAX_PHOTO_BYTES + 1)
    try:
        photo = await asyncio.to_thread(process_photo, data)
    except PhotoRejected as error:
        raise HTTPException(status_code=error.status_code, detail=f"{error.code}: {error}") from error
    store = _store(request)
    avatar_id = uuid4()
    try:
        for size, body in zip(SIZES, (photo.large, photo.thumb), strict=True):
            await asyncio.to_thread(store.put, avatar_key(user.id, avatar_id, size), body, "image/webp")
    except StorageNotConfigured as error:
        raise HTTPException(status_code=NOT_CONFIGURED, detail=f"NOT_CONFIGURED: {error}") from error
    except Exception as error:
        background.add_task(_delete_objects, store, user.id, avatar_id)
        raise HTTPException(status_code=NOT_CONFIGURED, detail="Photo storage is unavailable.") from error

    previous = await _current_avatar(session, user.id)
    await session.execute(
        text(
            """
            INSERT INTO public.lawyer_profiles (user_id, avatar_id, avatar_updated_at)
            VALUES (:u, :a, now())
            ON CONFLICT (user_id) DO UPDATE SET avatar_id = EXCLUDED.avatar_id,
                                                avatar_updated_at = EXCLUDED.avatar_updated_at
            """
        ),
        {"u": user.id, "a": avatar_id},
    )
    await _audit(session, request, user, "lawyer.photo_updated",
                 {"size_bytes": len(data), "replaced": previous is not None})
    if previous is not None:
        # Runs after the response, i.e. after this request's transaction committed.
        background.add_task(_delete_objects, store, user.id, previous)
    return PhotoResponse(photo_id=avatar_id)


@router.delete(
    "",
    summary="Remove the profile photo",
    description=("Removes the photo (clients then see initials). Deletes the stored files. Shares the upload "
                 "limit (10 per hour per user). Audit-logged."),
    response_model=PhotoResponse,
    responses=problem_responses(401, 403, 429, 503),
    dependencies=[Depends(require_same_origin)],
)
async def delete_photo(request: Request, background: BackgroundTasks, user: LawyerDep,
                       session: UserSessionDep, session_factory: SessionFactoryDep) -> PhotoResponse:
    await enforce_user_quota(session_factory, user.id, PHOTO_WRITE_LIMIT)
    previous = await _current_avatar(session, user.id)
    if previous is None:
        return PhotoResponse(photo_id=None)
    store = _store(request)
    await session.execute(
        text("UPDATE public.lawyer_profiles SET avatar_id = NULL, avatar_updated_at = now() WHERE user_id = :u"),
        {"u": user.id},
    )
    await _audit(session, request, user, "lawyer.photo_removed", {})
    background.add_task(_delete_objects, store, user.id, previous)
    return PhotoResponse(photo_id=None)


@router.get(
    "",
    summary="Get my profile photo",
    description=("The signed-in lawyer's own photo as WebP (512 or 96 pixels square). 404 when there is none. "
                 "At most 600 photo requests per hour per user (429 with Retry-After)."),
    response_class=Response,
    responses={**WEBP_RESPONSE, **problem_responses(401, 403, 404, 422, 429, 503)},
)
async def get_my_photo(
    request: Request, user: LawyerDep, session: UserSessionDep, session_factory: SessionFactoryDep,
    size: Annotated[int, Query(description="Square size in pixels: 512 or 96")] = 96,
) -> Response:
    check_size(size)
    await enforce_user_quota(session_factory, user.id, PHOTO_READ_LIMIT)
    avatar_id = await _current_avatar(session, user.id)
    if avatar_id is None:
        raise HTTPException(status_code=404, detail="Photo was not found.")
    return await read_photo(_store(request), user.id, avatar_id, size)
