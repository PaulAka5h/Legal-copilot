"""RLS bypass suite (Security.md §15, database.md §12).

Runs as ``app_user`` against local Compose PostgreSQL. For every table that has a
``case_id`` it checks, against one seeded case owned by lawyer A:

- no ``app.current_user_id``          -> 0 rows
- lawyer B (another organization)     -> 0 rows
- lawyer A (owning lawyer)            -> rows
- active client of the case           -> rows only in client-visible tables
- lawyer A after membership revoked   -> 0 rows
- lawyer B INSERT with A's case_id    -> rejected by RLS WITH CHECK / grants

All data is synthetic and labelled ``SAMPLE_DATA_NOT_REAL_LAW``.
"""

import asyncio
import secrets
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine, user_transaction
from app.main import create_app

ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "correct horse battery staple"
SAMPLE = "SAMPLE_DATA_NOT_REAL_LAW"
INTERNAL_MARKER = f"{SAMPLE} lawyer-only internal note"

# table -> SQL predicate selecting the seeded case's rows
CASE_TABLES: dict[str, str] = {
    "cases": "id = :case_id",
    "case_members": "case_id = :case_id",
    "case_stages": "case_id = :case_id",
    "case_invitations": "case_id = :case_id",
    "audit_logs": "case_id = :case_id",
    "hearings": "case_id = :case_id",
    "client_visible_updates": "case_id = :case_id",
    "client_shared_documents": "case_id = :case_id",
    "client_tasks": "case_id = :case_id",
    "client_visible_case_fields": "case_id = :case_id",
    "strategies": "case_id = :case_id",
    "strategy_scenarios": "case_id = :case_id",
    "strategy_comparisons": "case_id = :case_id",
    "claims": "case_id = :case_id",
    "claim_sources": "case_id = :case_id",
    "verification_results": "case_id = :case_id",
}
CLIENT_VISIBLE = {
    "cases",
    "hearings",
    "client_visible_updates",
    "client_shared_documents",
    "client_tasks",
    "client_visible_case_fields",
}
# Self-scoped rows a user may always read: their own membership row and audit
# events they performed. These must never expose rows about anyone else.
SELF_SCOPED = {
    "case_members": "user_id = :me",
    "audit_logs": "actor_user_id = :me",
}


@dataclass(frozen=True)
class World:
    database_url: str
    case_id: UUID
    organization_id: UUID
    lawyer_a: UUID
    lawyer_b: UUID
    client: UUID
    client_profile_id: UUID
    client_payloads: str


# --- API setup helpers --------------------------------------------------------


def _client(app_settings, last_octet: int) -> TestClient:
    return TestClient(
        create_app(app_settings),
        base_url="https://testserver",
        client=(f"127.0.{secrets.randbelow(200) + 20}.{last_octet}", 50000),
    )


def _register_login(client: TestClient, label: str) -> UUID:
    email = f"{label}-{secrets.token_hex(8)}@example.com"
    assert client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": PASSWORD, "full_name": f"{SAMPLE} {label}"},
    ).status_code == 201
    assert client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": PASSWORD},
    ).status_code == 200
    return UUID(client.get("/api/v1/me").json()["id"])


def _post(client: TestClient, path: str, payload: dict, method: str = "post") -> dict:
    response = getattr(client, method)(path, headers=ORIGIN, json=payload)
    assert response.status_code in (200, 201), (path, response.text)
    return response.json()


def _seed_via_api(lawyer: TestClient, client: TestClient) -> tuple[dict, UUID, UUID]:
    case = _post(
        lawyer,
        "/api/v1/cases",
        {
            "reference_no": f"SAMPLE-RLS-{secrets.token_hex(4)}",
            "title": f"{SAMPLE} Matter",
            "case_type": "sample",
            "internal_notes": INTERNAL_MARKER,
        },
    )
    case_id = case["id"]
    profile = _post(
        lawyer,
        "/api/v1/clients",
        {"display_name": f"{SAMPLE} Client", "email": f"rls-client-{secrets.token_hex(8)}@example.com"},
    )
    invite = _post(lawyer, f"/api/v1/cases/{case_id}/invitations", {"client_profile_id": profile["id"]})
    assert client.post(
        "/api/v1/auth/invitations/accept",
        headers=ORIGIN,
        json={"token": invite["development_token"], "password": PASSWORD},
    ).status_code == 200
    client_id = UUID(client.get("/api/v1/me").json()["id"])

    update = _post(lawyer, f"/api/v1/cases/{case_id}/client-updates", {"title": f"{SAMPLE} update", "body": f"{SAMPLE} body"})
    _post(lawyer, f"/api/v1/client-updates/{update['id']}/publish", {})
    _post(lawyer, f"/api/v1/cases/{case_id}/shared-documents", {"document_id": str(uuid4()), "display_name": f"{SAMPLE}.pdf"})
    _post(lawyer, f"/api/v1/cases/{case_id}/tasks", {"title": f"{SAMPLE} task"})
    _post(lawyer, f"/api/v1/cases/{case_id}/client-visibility", {"status_label": f"{SAMPLE} status"}, method="patch")
    return case, client_id, UUID(profile["id"])


# --- direct SQL helpers -------------------------------------------------------


async def _with_factory(database_url: str, fn):
    engine = create_database_engine(database_url)
    try:
        return await fn(async_sessionmaker(engine, expire_on_commit=False))
    finally:
        await engine.dispose()


async def _seed_direct(factory, w: World) -> None:
    params = {"case_id": w.case_id, "org": w.organization_id, "me": w.lawyer_a}
    async with user_transaction(factory, w.lawyer_a) as s:
        await s.execute(
            text(
                "INSERT INTO public.hearings (case_id, organization_id, date_status, purpose) "
                "VALUES (:case_id, :org, 'confirmed', 'SAMPLE_DATA_NOT_REAL_LAW')"
            ),
            params,
        )
        strategy_id = (
            await s.execute(
                text(
                    "INSERT INTO public.strategies (case_id, organization_id, lineage_id, version, "
                    "name, legal_basis, origin, created_by) VALUES (:case_id, :org, gen_random_uuid(), 1, "
                    "'SAMPLE_DATA_NOT_REAL_LAW', 'SAMPLE_DATA_NOT_REAL_LAW', 'lawyer', :me) RETURNING id"
                ),
                params,
            )
        ).scalar_one()
        await s.execute(
            text(
                "INSERT INTO public.strategy_scenarios (case_id, organization_id, strategy_id, node_type, text) "
                "VALUES (:case_id, :org, :sid, 'strategy_root', 'SAMPLE_DATA_NOT_REAL_LAW')"
            ),
            {**params, "sid": strategy_id},
        )
        await s.execute(
            text(
                "INSERT INTO public.strategy_comparisons (case_id, organization_id, version) "
                "VALUES (:case_id, :org, 1)"
            ),
            params,
        )
        claim_id = (
            await s.execute(
                text(
                    "INSERT INTO public.claims (case_id, organization_id, strategy_id, text, claim_type, "
                    "confidence_label) VALUES (:case_id, :org, :sid, 'SAMPLE_DATA_NOT_REAL_LAW', "
                    "'lawyer_entered', 'medium') RETURNING id"
                ),
                {**params, "sid": strategy_id},
            )
        ).scalar_one()
        await s.execute(
            text(
                "INSERT INTO public.claim_sources (claim_id, case_id, organization_id, source_kind) "
                "VALUES (:cid, :case_id, :org, 'lawyer_note')"
            ),
            {**params, "cid": claim_id},
        )
        await s.execute(
            text(
                "INSERT INTO public.verification_results (case_id, organization_id, claim_id, verdict) "
                "VALUES (:case_id, :org, :cid, 'cannot_verify')"
            ),
            {**params, "cid": claim_id},
        )


async def _counts(session, w: World, me: UUID | None) -> dict[str, int]:
    out = {}
    for table, predicate in CASE_TABLES.items():
        sql = f"SELECT count(*) FROM public.{table} WHERE {predicate}"
        if me is not None and table in SELF_SCOPED:
            sql += f" AND NOT ({SELF_SCOPED[table]})"
        out[table] = (
            await session.execute(text(sql), {"case_id": w.case_id, "me": me})
        ).scalar_one()
    return out


async def _counts_as(factory, w: World, user: UUID | None) -> dict[str, int]:
    if user is None:
        async with factory() as session, session.begin():
            return await _counts(session, w, None)
    async with user_transaction(factory, user) as session:
        return await _counts(session, w, user)


FOREIGN_INSERTS: dict[str, str] = {
    "cases": "INSERT INTO public.cases (organization_id, reference_no, title, case_type, status, created_by) "
    "VALUES (:org, 'SAMPLE-X', 'SAMPLE_DATA_NOT_REAL_LAW', 'sample', 'open', :me)",
    "case_members": "INSERT INTO public.case_members (case_id, organization_id, user_id, role, granted_by) "
    "VALUES (:case_id, :org, :me, 'team_lawyer', :me)",
    "case_stages": "INSERT INTO public.case_stages (case_id, organization_id, position, name) "
    "VALUES (:case_id, :org, 99, 'SAMPLE_DATA_NOT_REAL_LAW')",
    "case_invitations": "INSERT INTO public.case_invitations (case_id, organization_id, client_profile_id, email, "
    "client_reference, token_hash, expires_at, created_by) VALUES (:case_id, :org, :profile, 'x@example.com', "
    "'SAMPLE', '\\x00'::bytea, now() + interval '1 day', :me)",
    "audit_logs": "INSERT INTO public.audit_logs (action, case_id, actor_user_id) VALUES ('sample', :case_id, :me)",
    "hearings": "INSERT INTO public.hearings (case_id, organization_id) VALUES (:case_id, :org)",
    "client_visible_updates": "INSERT INTO public.client_visible_updates (case_id, organization_id, title, body) "
    "VALUES (:case_id, :org, 'SAMPLE', 'SAMPLE')",
    "client_shared_documents": "INSERT INTO public.client_shared_documents (case_id, organization_id, document_id, "
    "display_name, shared_by) VALUES (:case_id, :org, gen_random_uuid(), 'SAMPLE', :me)",
    "client_tasks": "INSERT INTO public.client_tasks (case_id, organization_id, title, created_by) "
    "VALUES (:case_id, :org, 'SAMPLE', :me)",
    "client_visible_case_fields": "INSERT INTO public.client_visible_case_fields (case_id, organization_id) "
    "VALUES (:case_id, :org) ON CONFLICT DO NOTHING",
    "strategies": "INSERT INTO public.strategies (case_id, organization_id, lineage_id, version, name, legal_basis, "
    "origin) VALUES (:case_id, :org, gen_random_uuid(), 1, 'SAMPLE', 'SAMPLE', 'lawyer')",
    "strategy_scenarios": "INSERT INTO public.strategy_scenarios (case_id, organization_id, strategy_id, node_type, "
    "text) SELECT :case_id, :org, gen_random_uuid(), 'strategy_root', 'SAMPLE'",
    "strategy_comparisons": "INSERT INTO public.strategy_comparisons (case_id, organization_id, version) "
    "VALUES (:case_id, :org, 99)",
    "claims": "INSERT INTO public.claims (case_id, organization_id, text, claim_type, confidence_label) "
    "VALUES (:case_id, :org, 'SAMPLE', 'assumption', 'low')",
    "claim_sources": "INSERT INTO public.claim_sources (claim_id, case_id, organization_id, source_kind) "
    "VALUES (gen_random_uuid(), :case_id, :org, 'lawyer_note')",
    "verification_results": "INSERT INTO public.verification_results (case_id, organization_id, claim_id, verdict) "
    "VALUES (:case_id, :org, gen_random_uuid(), 'cannot_verify')",
}
# Tables app_user may never INSERT into directly (append-only audit via function).
NO_DIRECT_INSERT = {"audit_logs"}


async def _foreign_insert_errors(factory, w: World) -> dict[str, str]:
    """Return table -> problem for each foreign-case INSERT that was not rejected."""
    problems = {}
    params = {"case_id": w.case_id, "org": w.organization_id, "me": w.lawyer_b, "profile": w.client_profile_id}
    for table, sql in FOREIGN_INSERTS.items():
        try:
            async with user_transaction(factory, w.lawyer_b) as session:
                await session.execute(text(sql), params)
        except DBAPIError as exc:
            message = str(exc.orig).lower()
            expected = "permission denied" if table in NO_DIRECT_INSERT else "row-level security"
            if expected not in message:
                problems[table] = f"rejected for the wrong reason: {message[:160]}"
        else:
            problems[table] = "INSERT with another organization's case_id was accepted"
    return problems


# --- the suite ----------------------------------------------------------------


@pytest.fixture
def world(api_client) -> World:
    settings = api_client.app.state.settings
    lawyer_a_id = _register_login(api_client, "rls-lawyer-a")
    client_tc = _client(settings, 11)
    lawyer_b_tc = _client(settings, 12)
    with client_tc, lawyer_b_tc:
        case, client_id, profile_id = _seed_via_api(api_client, client_tc)
        payloads = []
        for path in (
            "/api/v1/client/cases",
            f"/api/v1/client/cases/{case['id']}/updates",
            f"/api/v1/client/cases/{case['id']}/hearing",
            f"/api/v1/client/cases/{case['id']}/tasks",
            f"/api/v1/client/cases/{case['id']}/documents",
        ):
            response = client_tc.get(path)
            assert response.status_code == 200, (path, response.text)
            payloads.append(response.text)
        lawyer_b_id = _register_login(lawyer_b_tc, "rls-lawyer-b")
        _post(
            lawyer_b_tc,
            "/api/v1/cases",
            {"reference_no": f"SAMPLE-RLS-B-{secrets.token_hex(4)}", "title": f"{SAMPLE} B", "case_type": "sample"},
        )
    w = World(
        database_url=settings.database_url,
        case_id=UUID(case["id"]),
        organization_id=UUID(case["organization_id"]),
        lawyer_a=lawyer_a_id,
        lawyer_b=lawyer_b_id,
        client=client_id,
        client_profile_id=profile_id,
        client_payloads="\n".join(payloads),
    )
    asyncio.run(_with_factory(w.database_url, lambda f: _seed_direct(f, w)))
    return w


def test_rls_matrix_for_every_case_table(world: World) -> None:
    async def run(factory):
        result = {
            "no_context": await _counts_as(factory, world, None),
            "other_org_lawyer": await _counts_as(factory, world, world.lawyer_b),
            "owning_lawyer": await _counts_as(factory, world, world.lawyer_a),
            "client": await _counts_as(factory, world, world.client),
            "foreign_insert": await _foreign_insert_errors(factory, world),
        }
        async with user_transaction(factory, world.lawyer_a) as s:
            await s.execute(
                text(
                    "UPDATE public.case_members SET status = 'revoked', revoked_at = now() "
                    "WHERE case_id = :case_id AND user_id = :me"
                ),
                {"case_id": world.case_id, "me": world.lawyer_a},
            )
        result["revoked_lawyer"] = await _counts_as(factory, world, world.lawyer_a)
        return result

    r = asyncio.run(_with_factory(world.database_url, run))
    failures = []
    for table in CASE_TABLES:
        if r["no_context"][table]:
            failures.append(f"{table}: rows visible without user context")
        if r["other_org_lawyer"][table]:
            failures.append(f"{table}: rows visible to another organization's lawyer")
        owning = r["owning_lawyer"][table] + (1 if table in SELF_SCOPED else 0)
        if not owning:
            failures.append(f"{table}: owning lawyer sees no rows (seed or policy gap)")
        if table in CLIENT_VISIBLE and not r["client"][table]:
            failures.append(f"{table}: client of the case sees no client-visible rows")
        if table not in CLIENT_VISIBLE and r["client"][table]:
            failures.append(f"{table}: client sees lawyer-only rows")
        if r["revoked_lawyer"][table]:
            failures.append(f"{table}: revoked lawyer still sees rows")
    failures += [f"{t}: {p}" for t, p in r["foreign_insert"].items()]

    assert failures == []


def test_lawyer_cannot_grant_client_membership_to_an_unrelated_user(world: World) -> None:
    """A client membership row must match the profile's linked user and organization."""

    async def attempt(factory):
        async with user_transaction(factory, world.lawyer_a) as s:
            await s.execute(
                text(
                    "INSERT INTO public.case_members "
                    "(case_id, organization_id, user_id, role, client_profile_id, granted_by) "
                    "VALUES (:case_id, :org, :intruder, 'client', :profile, :me)"
                ),
                {
                    "case_id": world.case_id,
                    "org": world.organization_id,
                    "intruder": world.lawyer_b,
                    "profile": world.client_profile_id,
                    "me": world.lawyer_a,
                },
            )

    with pytest.raises(DBAPIError, match="row-level security"):
        asyncio.run(_with_factory(world.database_url, attempt))


def _claim_tx(world: World, claim_type: str, with_source: bool):
    async def run(factory):
        async with user_transaction(factory, world.lawyer_a) as s:
            claim_id = (
                await s.execute(
                    text(
                        "INSERT INTO public.claims (case_id, organization_id, text, claim_type, confidence_label) "
                        "VALUES (:case_id, :org, 'SAMPLE_DATA_NOT_REAL_LAW', :ct, 'low') RETURNING id"
                    ),
                    {"case_id": world.case_id, "org": world.organization_id, "ct": claim_type},
                )
            ).scalar_one()
            if with_source:
                await s.execute(
                    text(
                        "INSERT INTO public.claim_sources (claim_id, case_id, organization_id, source_kind) "
                        "VALUES (:cid, :case_id, :org, 'lawyer_note')"
                    ),
                    {"cid": claim_id, "case_id": world.case_id, "org": world.organization_id},
                )
            return claim_id

    return asyncio.run(_with_factory(world.database_url, run))


@pytest.mark.parametrize("claim_type", ["fact_from_document", "lawyer_entered", "verified_record", "inference"])
def test_sourced_claim_types_need_a_source_at_commit(world: World, claim_type: str) -> None:
    with pytest.raises(DBAPIError, match="claim requires at least one source"):
        _claim_tx(world, claim_type, with_source=False)
    assert _claim_tx(world, claim_type, with_source=True)


@pytest.mark.parametrize("claim_type", ["assumption", "prediction"])
def test_assumptions_and_predictions_may_be_unsourced(world: World, claim_type: str) -> None:
    assert _claim_tx(world, claim_type, with_source=False)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE public.claims SET text = 'changed' WHERE case_id = :case_id",
        "DELETE FROM public.claims WHERE case_id = :case_id",
        "UPDATE public.strategies SET legal_basis = 'changed' WHERE case_id = :case_id",
        "DELETE FROM public.strategies WHERE case_id = :case_id",
    ],
)
def test_claims_and_strategy_content_are_immutable_for_app_user(world: World, sql: str) -> None:
    async def attempt(factory):
        async with user_transaction(factory, world.lawyer_a) as s:
            await s.execute(text(sql), {"case_id": world.case_id})

    with pytest.raises(DBAPIError, match="permission denied"):
        asyncio.run(_with_factory(world.database_url, attempt))


def test_client_namespace_never_returns_internal_notes(world: World) -> None:
    assert world.case_id and str(world.case_id) in world.client_payloads
    assert INTERNAL_MARKER not in world.client_payloads
    assert "internal_notes" not in world.client_payloads
