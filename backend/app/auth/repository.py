import json
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine.row import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.security import hash_token
from app.auth.schemas import UserResponse
from app.database import user_transaction

IpAddress = IPv4Address | IPv6Address


async def consume_login_attempt(
    session_factory: async_sessionmaker[AsyncSession],
    ip_address: IpAddress,
) -> bool:
    async with session_factory() as session:
        async with session.begin():
            return bool(
                await session.scalar(
                    text("SELECT app.consume_login_attempt(CAST(:ip AS inet))"),
                    {"ip": str(ip_address)},
                )
            )


async def find_login_user(
    session_factory: async_sessionmaker[AsyncSession],
    email: str,
) -> RowMapping | None:
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM app.lookup_login_user(:email)"),
            {"email": email},
        )
        return result.mappings().one_or_none()


async def find_session(
    session_factory: async_sessionmaker[AsyncSession],
    token_hash: bytes,
) -> RowMapping | None:
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM app.lookup_session(:token_hash)"),
            {"token_hash": token_hash},
        )
        return result.mappings().one_or_none()


async def record_login_result(
    session: AsyncSession,
    user_id: UUID,
    succeeded: bool,
) -> None:
    await session.execute(
        text("SELECT app.record_login_result(:user_id, :succeeded)"),
        {"user_id": user_id, "succeeded": succeeded},
    )


async def create_lawyer(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str,
    password_hash: str,
    full_name: str,
    preferred_language: str,
    ip_address: IpAddress,
    user_agent: str | None,
    request_id: str | None,
) -> UserResponse:
    user_id = uuid4()
    organization_id = uuid4()
    async with user_transaction(session_factory, user_id) as session:
        await session.execute(
            text(
                """
                INSERT INTO public.users
                  (id, email, password_hash, role, full_name, preferred_language)
                VALUES (:id, :email, :password_hash, 'lawyer', :full_name,
                        :preferred_language)
                """
            ),
            {
                "id": user_id,
                "email": email,
                "password_hash": password_hash,
                "full_name": full_name,
                "preferred_language": preferred_language,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO public.organizations (id, name, kind, created_by)
                VALUES (:id, :name, 'individual', :created_by)
                """
            ),
            {
                "id": organization_id,
                "name": full_name,
                "created_by": user_id,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO public.organization_members
                  (organization_id, user_id, org_role)
                VALUES (:organization_id, :user_id, 'owner')
                """
            ),
            {"organization_id": organization_id, "user_id": user_id},
        )
        await session.execute(
            text("INSERT INTO public.lawyer_profiles (user_id) VALUES (:user_id)"),
            {"user_id": user_id},
        )
        await write_audit_event(
            session,
            action="auth.registered",
            actor_user_id=user_id,
            actor_role="lawyer",
            object_type="user",
            object_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
    return UserResponse(
        id=user_id,
        email=email,
        role="lawyer",
        full_name=full_name,
        preferred_language=preferred_language,
    )


async def create_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    token: str,
    user_role: str,
    expires_at: datetime,
    ip_address: IpAddress,
    user_agent: str | None,
    request_id: str | None,
) -> UUID:
    session_id = uuid4()
    await session.execute(
        text(
            """
            INSERT INTO public.sessions
              (id, user_id, token_hash, expires_at, ip, user_agent)
            VALUES (:id, :user_id, :token_hash, :expires_at,
                    CAST(:ip AS inet), :user_agent)
            """
        ),
        {
            "id": session_id,
            "user_id": user_id,
            "token_hash": hash_token(token),
            "expires_at": expires_at,
            "ip": str(ip_address),
            "user_agent": user_agent,
        },
    )
    await write_audit_event(
        session,
        action="auth.login_succeeded",
        actor_user_id=user_id,
        actor_role=user_role,
        object_type="session",
        object_id=session_id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )
    return session_id


async def write_audit_event(
    session: AsyncSession,
    *,
    action: str,
    actor_user_id: UUID | None,
    actor_role: str | None,
    object_type: str | None,
    object_id: UUID | None,
    ip_address: IpAddress | None,
    user_agent: str | None,
    request_id: str | None,
    details: dict[str, object] | None = None,
    organization_id: UUID | None = None,
    case_id: UUID | None = None,
) -> None:
    await session.execute(
        text(
            """
            SELECT app.write_audit_event(
              :organization_id, :case_id, :actor_user_id, :actor_role,
              :action, :object_type, :object_id, CAST(:ip AS inet),
              :user_agent, :request_id, CAST(:details AS jsonb)
            )
            """
        ),
        {
            "organization_id": organization_id,
            "case_id": case_id,
            "actor_user_id": actor_user_id,
            "actor_role": actor_role,
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "ip": str(ip_address) if ip_address else None,
            "user_agent": user_agent,
            "request_id": request_id,
            "details": json.dumps(details or {}),
        },
    )
