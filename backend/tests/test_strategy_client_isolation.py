"""A client of a case cannot read strategy data (Legal Product Rule 8).

Clients see strategy information only through client-visible tables and the
/client API namespace. All data is SAMPLE_DATA_NOT_REAL_LAW.
"""

import asyncio
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine, user_transaction
from app.main import create_app
from tests.test_phase2_exit import create_case, create_invite_and_accept, register_login

STRATEGY_TABLES = ("strategies", "strategy_scenarios", "strategy_comparisons")
LAWYER_ONLY_TABLES = STRATEGY_TABLES + ("hearing_updates", "hearing_reassessments")


def _client_reads(database_url: str, client_user_id: UUID, case_id: UUID) -> dict[str, object]:
    """Per table: row count visible to the client, or 'denied' on a privilege error."""

    async def run() -> dict[str, object]:
        engine = create_database_engine(database_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        results: dict[str, object] = {}
        try:
            for table in STRATEGY_TABLES:
                try:
                    async with user_transaction(session_factory, client_user_id) as session:
                        results[table] = await session.scalar(
                            text(f"SELECT count(*) FROM public.{table} WHERE case_id = :case_id"),
                            {"case_id": case_id},
                        )
                except DBAPIError as error:
                    assert "permission denied" in str(error.orig).lower(), error
                    results[table] = "denied"
        finally:
            await engine.dispose()
        return results

    return asyncio.run(run())


def _policies(database_url: str, user_id: UUID) -> list[tuple[str, str, str]]:
    async def run() -> list[tuple[str, str, str]]:
        engine = create_database_engine(database_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with user_transaction(session_factory, user_id) as session:
                rows = await session.execute(
                    text(
                        """
                        SELECT tablename, policyname,
                               coalesce(qual, '') || ' ' || coalesce(with_check, '')
                        FROM pg_policies
                        WHERE schemaname = 'public' AND tablename = ANY(:tables)
                          -- Owner-only policies (0019, Neon) cannot admit app_user.
                          AND roles <> ARRAY['app_owner']::name[]
                        """
                    ),
                    {"tables": list(LAWYER_ONLY_TABLES)},
                )
                return [tuple(row) for row in rows]
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_client_member_cannot_read_strategy_tables(api_client) -> None:
    lawyer = api_client
    lawyer_id = UUID(register_login(lawyer, "strat-iso-lawyer"))
    case_id = UUID(create_case(lawyer, "SAMPLE-STRAT-ISO"))
    database_url = lawyer.app.state.settings.database_url

    client = TestClient(
        create_app(lawyer.app.state.settings),
        base_url="https://testserver",
    )
    with client:
        create_invite_and_accept(lawyer, client, case_id, "strat-iso-client")
        client_user_id = UUID(client.get("/api/v1/me").json()["id"])

        # 1. No policy on lawyer-only tables admits clients; each requires lawyer membership.
        policies = _policies(database_url, lawyer_id)
        assert {name for _, name, _ in policies} >= {
            "strategies_lawyer_manage",
            "strategy_scenarios_lawyer_manage",
            "strategy_comparisons_lawyer_manage",
            "hearing_updates_lawyer_manage",
            "hearing_reassessments_lawyer_manage",
        }
        for table, name, expression in policies:
            assert "is_client_member" not in expression, (table, name)
            assert "is_lawyer_member" in expression, (table, name)

        # 2. Direct SQL as the client: denied, or no rows.
        for table, visible in _client_reads(database_url, client_user_id, case_id).items():
            assert visible in ("denied", 0), (table, visible)

        # 3. The client API namespace exposes no strategy endpoint.
        # OpenAPI lists every mounted path, including those of included routers.
        client_paths = [p for p in client.app.openapi()["paths"] if p.startswith("/api/v1/client")]
        assert client_paths, "expected /api/v1/client routes"
        assert not any("strateg" in path for path in client_paths)
