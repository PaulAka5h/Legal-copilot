"""Seed the demo lawyer and one synthetic case into the demo dump's scratch database.

Run by deploy/make_demo_dump.sh (never against production). Reads DATABASE_URL
(app_user), DEMO_LAWYER_EMAIL and DEMO_LAWYER_PASSWORD from the environment. Uses the same code paths as the API
(Argon2id hash, organization, lawyer profile, case + default stages, audit
events). Idempotent: an existing demo lawyer is left unchanged. The password is
never printed.
"""

import asyncio
import os
import sys
from ipaddress import IPv4Address
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.auth.repository import create_lawyer, write_audit_event  # noqa: E402
from app.auth.schemas import RegisterRequest  # noqa: E402
from app.auth.security import hash_password  # noqa: E402
from app.cases.repository import create_case  # noqa: E402
from app.cases.schemas import CaseCreate  # noqa: E402
from app.database import create_database_engine, user_transaction, verify_runtime_role  # noqa: E402

LOCALHOST = IPv4Address("127.0.0.1")
AGENT = "deploy.seed_demo"

DEMO_CASE = CaseCreate(
    reference_no="DEMO-0001",
    title="SAMPLE_DATA_NOT_REAL_LAW Rahman Traders v. Karim Enterprises (cheque dishonour)",
    case_type="Cheque Dishonour",
    court="Chief Judicial Magistrate Court, Dhaka (synthetic)",
    jurisdiction="Dhaka",
    opposing_party="Karim Enterprises (synthetic)",
    description=(
        "SYNTHETIC DEMO CASE. Our client supplied goods worth BDT 1,500,000 and received "
        "cheque no. 4928192 dated 10 January 2023. The bank returned it unpaid for "
        "insufficient funds on 2 February 2023. A legal notice was sent on 15 February 2023 "
        "and no payment followed within 30 days."
    ),
    client_objectives="Recover the cheque amount and costs; consider a prosecution under the Negotiable Instruments Act.",
)


async def seed(database_url: str, request: RegisterRequest) -> None:
    engine = create_database_engine(database_url)
    try:
        await verify_runtime_role(engine)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        password_hash = await asyncio.to_thread(hash_password, request.password)
        try:
            user = await create_lawyer(
                factory,
                email=str(request.email).lower(),
                password_hash=password_hash,
                full_name=request.full_name,
                preferred_language=request.preferred_language,
                ip_address=LOCALHOST,
                user_agent=AGENT,
                request_id=None,
            )
        except IntegrityError:
            raise SystemExit(f"[seed] {request.email} already exists; the scratch database must be empty")
        async with user_transaction(factory, user.id) as session:
            case = await create_case(session, acting_user_id=user.id, payload=DEMO_CASE)
            await write_audit_event(
                session,
                action="case.created",
                actor_user_id=user.id,
                actor_role="lawyer",
                object_type="case",
                object_id=case.id,
                ip_address=LOCALHOST,
                user_agent=AGENT,
                request_id=None,
                organization_id=case.organization_id,
                case_id=case.id,
                details={"fields": sorted(DEMO_CASE.model_fields_set)},
            )
        print(f"[seed] Created demo lawyer {user.email} and demo case {case.reference_no}")
        print(f"DEMO_LAWYER_ID={user.id}")
    finally:
        await engine.dispose()


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("[seed] DATABASE_URL is not set")
    request = RegisterRequest(
        email=os.environ.get("DEMO_LAWYER_EMAIL", "demo.lawyer@example.com"),
        password=os.environ["DEMO_LAWYER_PASSWORD"],  # validated by RegisterRequest
        full_name=os.environ.get("DEMO_LAWYER_NAME", "Demo Lawyer"),
    )
    asyncio.run(seed(database_url, request))


if __name__ == "__main__":
    main()
