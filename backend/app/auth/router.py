import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import (
    CurrentUserDep,
    SESSION_COOKIE_NAME,
    SessionFactoryDep,
    UserSessionDep,
    request_ip,
    require_same_origin,
)
from app.auth.repository import (
    consume_login_attempt,
    create_lawyer,
    create_session,
    find_login_user,
    find_session,
    record_login_result,
    write_audit_event,
)
from app.auth.schemas import (
    CurrentUser,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    UserResponse,
)
from app.auth.security import (
    hash_password,
    hash_token,
    new_session_token,
    verify_password,
)
from app.database import user_transaction
from app.errors import problem_responses

auth_router = APIRouter(
    prefix="/api/v1/auth",
    tags=["authentication"],
    dependencies=[Depends(require_same_origin)],
)
identity_router = APIRouter(prefix="/api/v1", tags=["identity"])


@auth_router.post(
    "/register",
    summary="Register a lawyer account",
    description=(
        "Creates a lawyer, individual organization, owner membership, and lawyer "
        "profile atomically. Passwords require at least 12 characters."
    ),
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(400, 403, 409, 422, 503),
)
async def register(
    request: Request,
    session_factory: SessionFactoryDep,
    payload: Annotated[RegisterRequest, Body(description="Lawyer account details")],
) -> UserResponse:
    email = str(payload.email).lower()
    password_hash = await asyncio.to_thread(hash_password, payload.password)
    try:
        return await create_lawyer(
            session_factory,
            email=email,
            password_hash=password_hash,
            full_name=payload.full_name,
            preferred_language=payload.preferred_language,
            ip_address=request_ip(request),
            user_agent=request.headers.get("user-agent", "")[:512] or None,
            request_id=getattr(request.state, "request_id", None),
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc


@auth_router.post(
    "/login",
    summary="Create a session",
    description=(
        "Verifies account status and Argon2id password, enforces account lockout "
        "and per-IP throttling, then sets a hashed server-side session cookie."
    ),
    response_model=UserResponse,
    responses=problem_responses(400, 401, 403, 422, 429, 503),
)
async def login(
    request: Request,
    response: Response,
    session_factory: SessionFactoryDep,
    payload: Annotated[
        LoginRequest,
        Body(description="Email and password credentials"),
    ],
) -> UserResponse:
    ip_address = request_ip(request)
    if not await consume_login_attempt(session_factory, ip_address):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )

    email = str(payload.email).lower()
    login_user = await find_login_user(session_factory, email)
    stored_hash = login_user["password_hash"] if login_user else None
    password_valid = await asyncio.to_thread(
        verify_password,
        stored_hash,
        payload.password,
    )
    now = datetime.now(UTC)
    eligible = (
        login_user is not None
        and login_user["user_status"] == "active"
        and login_user["user_role"] in {"lawyer", "client"}
    )
    locked = (
        login_user is not None
        and login_user["locked_until"] is not None
        and login_user["locked_until"] > now
    )
    if not eligible or locked or not password_valid:
        if eligible and not locked:
            async with user_transaction(
                session_factory,
                login_user["user_id"],
            ) as session:
                await record_login_result(
                    session,
                    login_user["user_id"],
                    succeeded=False,
                )
                await write_audit_event(
                    session,
                    action="auth.login_failed",
                    actor_user_id=login_user["user_id"],
                    actor_role=login_user["user_role"],
                    object_type="user",
                    object_id=login_user["user_id"],
                    ip_address=ip_address,
                    user_agent=request.headers.get("user-agent", "")[:512] or None,
                    request_id=getattr(request.state, "request_id", None),
                )
        else:
            await _audit_anonymous_login_failure(
                session_factory,
                ip_address=ip_address,
                user_agent=request.headers.get("user-agent", "")[:512] or None,
                request_id=getattr(request.state, "request_id", None),
            )
        raise _invalid_credentials()

    user_id = login_user["user_id"]
    token = new_session_token()
    expires_at = now + timedelta(
        hours=request.app.state.settings.session_absolute_hours
    )
    user_agent = request.headers.get("user-agent", "")[:512] or None
    async with user_transaction(session_factory, user_id) as session:
        await record_login_result(session, user_id, succeeded=True)
        profile = (
            await session.execute(
                text(
                    """
                    SELECT email::text, full_name, preferred_language
                    FROM public.users
                    WHERE id = :user_id
                    """
                ),
                {"user_id": user_id},
            )
        ).mappings().one()
        previous_token = request.cookies.get(SESSION_COOKIE_NAME)
        if previous_token:
            previous_session = await find_session(
                session_factory,
                hash_token(previous_token),
            )
            if (
                previous_session is not None
                and previous_session["user_id"] == user_id
            ):
                await session.execute(
                    text("SELECT app.revoke_sessions(:session_id)"),
                    {"session_id": previous_session["session_id"]},
                )
        session_id = await create_session(
            session,
            user_id=user_id,
            token=token,
            user_role=login_user["user_role"],
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=getattr(request.state, "request_id", None),
        )

    settings = request.app.state.settings
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=request.app.state.settings.session_absolute_hours * 3600,
        httponly=True,
        secure=settings.secure_session_cookie,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return UserResponse(
        id=user_id,
        email=profile["email"],
        role=login_user["user_role"],
        full_name=profile["full_name"],
        preferred_language=profile["preferred_language"],
    )


@auth_router.post(
    "/logout",
    summary="Revoke the current session",
    description="Revokes the authenticated session and clears its browser cookie.",
    response_model=MessageResponse,
    responses=problem_responses(401, 403, 422, 503),
)
async def logout(
    request: Request,
    response: Response,
    user: CurrentUserDep,
    session: UserSessionDep,
) -> MessageResponse:
    await session.execute(
        text("SELECT app.revoke_sessions(:session_id)"),
        {"session_id": user.session_id},
    )
    await write_audit_event(
        session,
        action="auth.logout",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="session",
        object_id=user.session_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
    )
    _clear_session_cookie(response, request)
    response.headers["Cache-Control"] = "no-store"
    return MessageResponse(message="Logged out.")


@auth_router.post(
    "/logout-all",
    summary="Revoke all account sessions",
    description="Revokes every session for the authenticated account.",
    response_model=MessageResponse,
    responses=problem_responses(401, 403, 422, 503),
)
async def logout_all(
    request: Request,
    response: Response,
    user: CurrentUserDep,
    session: UserSessionDep,
) -> MessageResponse:
    await session.execute(
        text("SELECT app.revoke_sessions(NULL)"),
    )
    await write_audit_event(
        session,
        action="auth.logout_all",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="user",
        object_id=user.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
    )
    _clear_session_cookie(response, request)
    response.headers["Cache-Control"] = "no-store"
    return MessageResponse(message="All sessions logged out.")


@identity_router.get(
    "/me",
    summary="Get the authenticated user",
    description="Returns the server-validated identity and role for this session.",
    response_model=UserResponse,
    responses=problem_responses(401, 503),
)
async def me(
    user: CurrentUserDep,
    response: Response,
) -> UserResponse:
    response.headers["Cache-Control"] = "no-store"
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        preferred_language=user.preferred_language,
    )


async def _audit_anonymous_login_failure(
    session_factory,
    *,
    ip_address,
    user_agent: str | None,
    request_id: str | None,
) -> None:
    async with session_factory() as session:
        async with session.begin():
            await write_audit_event(
                session,
                action="auth.login_failed",
                actor_user_id=None,
                actor_role=None,
                object_type=None,
                object_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
            )


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email or password is incorrect.",
    )


def _clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=request.app.state.settings.secure_session_cookie,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
