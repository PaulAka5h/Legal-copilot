"""Create a local development lawyer account.

uv run python -m app.seed_dev_lawyer --email EMAIL [--full-name NAME] [--password-stdin]

Uses the same validation and code path as POST /api/v1/auth/register (Argon2id
hash, individual organization, owner membership, lawyer profile, audit event).
The password is prompted twice without echo, or read from one stdin line with
--password-stdin. It is never printed or logged. Refuses to run unless
APP_ENV is development or test and DATABASE_URL points at localhost.
"""

import argparse
import asyncio
import getpass
import os
import sys
from ipaddress import IPv4Address
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.repository import create_lawyer
from app.auth.schemas import RegisterRequest, UserResponse
from app.auth.security import hash_password
from app.database import create_database_engine, verify_runtime_role

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def read_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("Password (min 12 characters): ")
    if first != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords do not match; no account created")
    return first


def check_local(database_url: str | None) -> str:
    if os.getenv("APP_ENV", "development") not in {"development", "test"}:
        raise SystemExit("Refusing to seed outside APP_ENV=development/test")
    if not database_url:
        raise SystemExit("DATABASE_URL is required (app_user on the local database)")
    if make_url(database_url).host not in LOCAL_HOSTS:
        raise SystemExit("Refusing to seed a non-local database")
    return database_url


async def seed_lawyer(database_url: str, request: RegisterRequest) -> UserResponse:
    engine = create_database_engine(database_url)
    try:
        await verify_runtime_role(engine)
        password_hash = await asyncio.to_thread(hash_password, request.password)
        return await create_lawyer(
            async_sessionmaker(engine, expire_on_commit=False),
            email=str(request.email).lower(),
            password_hash=password_hash,
            full_name=request.full_name,
            preferred_language=request.preferred_language,
            ip_address=IPv4Address("127.0.0.1"),
            user_agent="app.seed_dev_lawyer",
            request_id=None,
        )
    finally:
        await engine.dispose()


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    parser = argparse.ArgumentParser(prog="python -m app.seed_dev_lawyer", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", default="Local Dev Lawyer")
    parser.add_argument("--password-stdin", action="store_true", help="Read the password from one stdin line")
    args = parser.parse_args()

    database_url = check_local(os.getenv("DATABASE_URL"))
    try:
        request = RegisterRequest(
            email=args.email, password=read_password(args.password_stdin), full_name=args.full_name
        )
    except ValidationError as error:
        fields = sorted({".".join(map(str, e["loc"])) for e in error.errors()})
        raise SystemExit(f"Invalid input for: {', '.join(fields)}; no account created") from None
    try:
        user = asyncio.run(seed_lawyer(database_url, request))
    except IntegrityError:
        raise SystemExit("An account with this email already exists; nothing changed") from None
    print(f"Created lawyer {user.email} (id {user.id})")


if __name__ == "__main__":
    main()
