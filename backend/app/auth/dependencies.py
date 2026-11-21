from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import find_session
from app.auth.schemas import CurrentUser
from app.auth.security import hash_token
from app.database import user_transaction

SessionFactory = async_sessionmaker[AsyncSession]
SESSION_COOKIE_NAME = "lc_session"
IpAddress = IPv4Address | IPv6Address


def get_session_factory(request: Request) -> SessionFactory:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        )
    return session_factory


SessionFactoryDep = Annotated[SessionFactory, Depends(get_session_factory)]


def _origin_parts(value: str) -> tuple[str, str, int] | None:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return None
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None
    return parsed.scheme.lower(), parsed.hostname.lower(), port


async def require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    expected_origin = str(request.app.state.settings.app_origin)
    if (
        origin is None
        or _origin_parts(origin) is None
        or _origin_parts(origin) != _origin_parts(expected_origin)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request origin is not allowed.",
        )


def request_ip(request: Request) -> IpAddress:
    if request.client is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A client IP address is required.",
        )
    try:
        return ip_address(request.client.host)
    except ValueError:
        # Test clients (e.g. Starlette TestClient) may report a non-IP host
        # such as "testclient". In production the peer address is always a
        # valid IP, so this fallback only affects test/dev tooling.
        return ip_address("127.0.0.1")


async def get_authenticated_user(
    request: Request,
    session_factory: SessionFactoryDep,
) -> CurrentUser:
    """The session's user, even when a password change is still required."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise _unauthenticated()

    token_hash = hash_token(token)
    record = await find_session(session_factory, token_hash)
    if record is None:
        raise _unauthenticated()

    now = datetime.now(UTC)
    if (
        record["revoked_at"] is not None
        or record["user_status"] != "active"
        or record["expires_at"] <= now
        or record["last_seen_at"]
        <= now
        - timedelta(minutes=request.app.state.settings.session_idle_minutes)
    ):
        raise _unauthenticated()

    user = CurrentUser(
        id=record["user_id"],
        email=record["email"],
        role=record["user_role"],
        full_name=record["full_name"],
        preferred_language=record["preferred_language"],
        session_id=record["session_id"],
        must_change_password=record["must_change_password"],
    )
    async with user_transaction(session_factory, user.id) as session:
        result = await session.execute(
            text(
                """
                UPDATE public.sessions
                SET last_seen_at = now()
                WHERE id = :session_id
                  AND user_id = :user_id
                  AND token_hash = :token_hash
                  AND revoked_at IS NULL
                  AND expires_at > now()
                """
            ),
            {
                "session_id": user.session_id,
                "user_id": user.id,
                "token_hash": token_hash,
            },
        )
        if result.rowcount != 1:
            raise _unauthenticated()
    return user


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
    )


AuthenticatedUserDep = Annotated[CurrentUser, Depends(get_authenticated_user)]

PASSWORD_CHANGE_REQUIRED = "PASSWORD_CHANGE_REQUIRED"


def get_current_user(user: AuthenticatedUserDep) -> CurrentUser:
    """The session's user; refused until a lawyer-set password is changed.

    Only password change and logout use AuthenticatedUserDep instead.
    """
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{PASSWORD_CHANGE_REQUIRED}: Set a new password to continue.",
        )
    return user


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


async def get_user_session(
    session_factory: SessionFactoryDep,
    user: CurrentUserDep,
) -> AsyncIterator[AsyncSession]:
    async with user_transaction(session_factory, user.id) as session:
        yield session


UserSessionDep = Annotated[AsyncSession, Depends(get_user_session)]


async def get_authenticated_session(
    session_factory: SessionFactoryDep,
    user: AuthenticatedUserDep,
) -> AsyncIterator[AsyncSession]:
    async with user_transaction(session_factory, user.id) as session:
        yield session


AuthenticatedSessionDep = Annotated[AsyncSession, Depends(get_authenticated_session)]


def require_lawyer(user: CurrentUserDep) -> CurrentUser:
    if user.role != "lawyer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lawyer access is required.",
        )
    return user


def require_client(user: CurrentUserDep) -> CurrentUser:
    if user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client access is required.",
        )
    return user


LawyerDep = Annotated[CurrentUser, Depends(require_lawyer)]
ClientDep = Annotated[CurrentUser, Depends(require_client)]
