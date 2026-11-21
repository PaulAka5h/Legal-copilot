import asyncio
from datetime import UTC, datetime, timedelta
import secrets
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import (
    AuthenticatedSessionDep,
    AuthenticatedUserDep,
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
from app.auth.mfa import fernet_for_key, new_totp_secret
from app.auth.schemas import (
    MfaSetupResponse,
    MfaVerifyRequest,
    MfaVerifyResponse,
    InvitationAcceptRequest,
    PasswordChangeRequest,
    PasswordForgotRequest,
    PasswordResetRequest,
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
    mfa_valid = True
    if login_user is not None and login_user["mfa_enabled"]:
        mfa_valid = False
        if payload.mfa_code:
            from app.auth.mfa import verify_totp

            secret_enc = login_user["mfa_secret_enc"]
            if secret_enc:
                secret = fernet_for_key(
                    request.app.state.settings.mfa_encryption_key
                ).decrypt(bytes(secret_enc)).decode("ascii")
                mfa_valid = verify_totp(secret, payload.mfa_code)
        elif payload.mfa_recovery_code:
            async with user_transaction(
                session_factory,
                login_user["user_id"],
            ) as session:
                recovery = await session.execute(
                    text(
                        """
                        UPDATE public.mfa_recovery_codes
                        SET used_at = now()
                        WHERE user_id = :user_id
                          AND code_hash = :code_hash
                          AND used_at IS NULL
                        RETURNING id
                        """
                    ),
                    {
                        "user_id": login_user["user_id"],
                        "code_hash": hash_token(payload.mfa_recovery_code),
                    },
                )
                mfa_valid = recovery.mappings().one_or_none() is not None
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
    if not eligible or locked or not password_valid or not mfa_valid:
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
                    SELECT email::text, full_name, preferred_language,
                           must_change_password
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
        must_change_password=profile["must_change_password"],
    )


@auth_router.post(
    "/password/change",
    summary="Change the signed-in user's password",
    description=(
        "Verifies the current password and sets a new one (at least 12 characters, "
        "different from the current one). Clears the PASSWORD_CHANGE_REQUIRED state "
        "of a lawyer-set temporary password and revokes the user's other sessions. "
        "Allowed while a password change is required."
    ),
    response_model=UserResponse,
    responses=problem_responses(400, 401, 403, 422, 429, 503),
)
async def change_password(
    request: Request,
    response: Response,
    session_factory: SessionFactoryDep,
    user: AuthenticatedUserDep,
    session: AuthenticatedSessionDep,
    payload: Annotated[
        PasswordChangeRequest,
        Body(description="Current password and the new password"),
    ],
) -> UserResponse:
    if not await consume_login_attempt(session_factory, request_ip(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again later.",
        )
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The new password must differ from the current password.",
        )
    stored_hash = await session.scalar(
        text("SELECT password_hash FROM public.users WHERE id = :user_id"),
        {"user_id": user.id},
    )
    if not await asyncio.to_thread(verify_password, stored_hash, payload.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The current password is incorrect.",
        )
    password_hash = await asyncio.to_thread(hash_password, payload.new_password)
    revoked = await session.scalar(
        text("SELECT app.complete_password_change(:password_hash, :session_id)"),
        {"password_hash": password_hash, "session_id": user.session_id},
    )
    await write_audit_event(
        session,
        action="auth.password_changed",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="user",
        object_id=user.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        details={
            "was_temporary": user.must_change_password,
            "other_sessions_revoked": revoked or 0,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        preferred_language=user.preferred_language,
        must_change_password=False,
    )


@auth_router.post(
    "/password/forgot",
    summary="Request a password reset",
    description="Returns the same response whether or not the email is registered.",
    response_model=MessageResponse,
    responses=problem_responses(403, 422, 503),
)
async def password_forgot(
    request: Request,
    session_factory: SessionFactoryDep,
    payload: Annotated[
        PasswordForgotRequest,
        Body(description="Account email"),
    ],
) -> MessageResponse:
    email = str(payload.email).lower()
    login_user = await find_login_user(session_factory, email)
    if login_user is not None:
        token = new_session_token()
        expires_at = datetime.now(UTC) + timedelta(minutes=30)
        async with user_transaction(session_factory, login_user["user_id"]) as session:
            await session.execute(
                text(
                    """
                    UPDATE public.password_reset_tokens
                    SET used_at = now()
                    WHERE user_id = :user_id
                      AND used_at IS NULL
                    """
                ),
                {"user_id": login_user["user_id"]},
            )
            await session.execute(
                text(
                    """
                    INSERT INTO public.password_reset_tokens
                      (id, user_id, token_hash, expires_at)
                    VALUES (:id, :user_id, :token_hash, :expires_at)
                    """
                ),
                {
                    "id": uuid4(),
                    "user_id": login_user["user_id"],
                    "token_hash": hash_token(token),
                    "expires_at": expires_at,
                },
            )
        if request.app.state.settings.app_env == "development":
            request.app.state.last_password_reset_token = token
    return MessageResponse(message="If the account exists, a reset link was sent.")


@auth_router.post(
    "/password/reset",
    summary="Reset a password",
    description="Consumes a single-use, unexpired password reset token.",
    response_model=MessageResponse,
    responses=problem_responses(400, 403, 422, 503),
)
async def password_reset(
    request: Request,
    session_factory: SessionFactoryDep,
    payload: Annotated[
        PasswordResetRequest,
        Body(description="Reset token and new password"),
    ],
) -> MessageResponse:
    password_hash = await asyncio.to_thread(hash_password, payload.new_password)
    async with session_factory() as session:
        async with session.begin():
            reset = (
                await session.execute(
                    text("SELECT * FROM app.lookup_password_reset(:token_hash)"),
                    {"token_hash": hash_token(payload.token)},
                )
            ).mappings().one_or_none()
    if reset is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token is invalid or expired.",
        )
    user_id = reset["user_id"]
    async with user_transaction(session_factory, user_id) as session:
        consumed_user_id = await session.scalar(
                text(
                    "SELECT app.consume_password_reset(:token_hash, :password_hash)"
                ),
                {
                    "token_hash": hash_token(payload.token),
                    "password_hash": password_hash,
                },
            )
        if consumed_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token is invalid or expired.",
            )
        role = (
            await session.execute(
                text("SELECT role FROM public.users WHERE id = :user_id"),
                {"user_id": user_id},
            )
        ).scalar_one()
        await write_audit_event(
            session,
            action="auth.password_reset",
            actor_user_id=user_id,
            actor_role=role,
            object_type="user",
            object_id=user_id,
            ip_address=request_ip(request),
            user_agent=request.headers.get("user-agent", "")[:512] or None,
            request_id=getattr(request.state, "request_id", None),
        )
    return MessageResponse(message="Password reset successfully.")


@auth_router.post(
    "/mfa/setup",
    summary="Set up TOTP MFA",
    description="Creates an encrypted TOTP secret and returns an otpauth URI.",
    response_model=MfaSetupResponse,
    responses=problem_responses(401, 403, 503),
)
async def mfa_setup(
    request: Request,
    user: CurrentUserDep,
    session: UserSessionDep,
) -> MfaSetupResponse:
    if (
        request.app.state.settings.app_env == "production"
        and not request.app.state.settings.mfa_encryption_key
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MFA is not configured.",
        )
    secret = new_totp_secret()
    encrypted = fernet_for_key(
        request.app.state.settings.mfa_encryption_key
    ).encrypt(secret.encode("ascii"))
    await session.execute(
        text(
            """
            UPDATE public.users
            SET mfa_secret_enc = :secret, mfa_enabled = false, updated_at = now()
            WHERE id = :user_id
            """
        ),
        {"secret": encrypted, "user_id": user.id},
    )
    await write_audit_event(
        session,
        action="auth.mfa_setup",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="user",
        object_id=user.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
    )
    issuer = "PokkhoAI"
    uri = (
        f"otpauth://totp/{issuer}:{user.email}"
        f"?secret={secret}&issuer={issuer}&digits=6&period=30"
    )
    return MfaSetupResponse(otpauth_uri=uri)


@auth_router.post(
    "/mfa/verify",
    summary="Verify and enable TOTP MFA",
    description="Verifies the current TOTP code and creates hashed recovery codes.",
    response_model=MfaVerifyResponse,
    responses=problem_responses(400, 401, 403, 422, 503),
)
async def mfa_verify(
    request: Request,
    user: CurrentUserDep,
    session: UserSessionDep,
    payload: Annotated[
        MfaVerifyRequest,
        Body(description="Six-digit TOTP code"),
    ],
) -> MfaVerifyResponse:
    from app.auth.mfa import verify_totp

    row = (
        await session.execute(
            text(
                "SELECT mfa_secret_enc FROM public.users WHERE id = :user_id"
            ),
            {"user_id": user.id},
        )
    ).mappings().one_or_none()
    if row is None or row["mfa_secret_enc"] is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup is required before verification.",
        )
    secret = fernet_for_key(
        request.app.state.settings.mfa_encryption_key
    ).decrypt(bytes(row["mfa_secret_enc"])).decode("ascii")
    if not verify_totp(secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The MFA code is invalid.",
        )
    await session.execute(
        text(
            """
            UPDATE public.users
            SET mfa_enabled = true, updated_at = now()
            WHERE id = :user_id
            """
        ),
        {"user_id": user.id},
    )
    recovery_codes = [
        secrets.token_urlsafe(12)[:16] for _ in range(10)
    ]
    for code in recovery_codes:
        await session.execute(
            text(
                """
                INSERT INTO public.mfa_recovery_codes (user_id, code_hash)
                VALUES (:user_id, :code_hash)
                """
            ),
            {"user_id": user.id, "code_hash": hash_token(code)},
        )
    await write_audit_event(
        session,
        action="auth.mfa_enabled",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="user",
        object_id=user.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
    )
    return MfaVerifyResponse(enabled=True, recovery_codes=recovery_codes)


@auth_router.post(
    "/invitations/accept",
    summary="Accept a client invitation",
    description="Uses a single-use invitation token to activate a client account and session.",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    responses=problem_responses(400, 403, 429, 422, 503),
)
async def accept_invitation(
    request: Request,
    response: Response,
    session_factory: SessionFactoryDep,
    payload: Annotated[
        InvitationAcceptRequest,
        Body(description="Invitation token and new password"),
    ],
) -> UserResponse:
    ip_address = request_ip(request)
    if not await consume_login_attempt(session_factory, ip_address):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many invitation attempts. Try again later.",
        )
    password_hash = await asyncio.to_thread(hash_password, payload.password)
    session_token = new_session_token()
    expires_at = datetime.now(UTC) + timedelta(
        hours=request.app.state.settings.session_absolute_hours
    )
    async with session_factory() as session:
        async with session.begin():
            accepted = (
                await session.execute(
                    text(
                        """
                        SELECT * FROM app.accept_case_invitation(
                          :token_hash, :password_hash, :session_hash, :expires_at,
                          CAST(:ip AS inet), :user_agent, :request_id
                        )
                        """
                    ),
                    {
                        "token_hash": hash_token(payload.token),
                        "password_hash": password_hash,
                        "session_hash": hash_token(session_token),
                        "expires_at": expires_at,
                        "ip": str(ip_address),
                        "user_agent": request.headers.get("user-agent", "")[:512] or None,
                        "request_id": getattr(request.state, "request_id", None),
                    },
                )
            ).mappings().one_or_none()
    if accepted is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation is invalid, expired, revoked, or already used.",
        )
    user_id = accepted["result_user_id"]
    async with user_transaction(session_factory, user_id) as session:
        await write_audit_event(
            session,
            action="case.invitation_accepted",
            actor_user_id=user_id,
            actor_role="client",
            object_type="user",
            object_id=user_id,
            ip_address=ip_address,
            user_agent=request.headers.get("user-agent", "")[:512] or None,
            request_id=getattr(request.state, "request_id", None),
        )
    settings = request.app.state.settings
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=settings.session_absolute_hours * 3600,
        httponly=True,
        secure=settings.secure_session_cookie,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return UserResponse(
        id=user_id,
        email=accepted["result_email"],
        role="client",
        full_name=accepted["result_full_name"],
        preferred_language="en",
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
    user: AuthenticatedUserDep,
    session: AuthenticatedSessionDep,
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
    user: AuthenticatedUserDep,
    session: AuthenticatedSessionDep,
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
