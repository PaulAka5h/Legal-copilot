import asyncio
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.dependencies import LawyerDep, UserSessionDep
from app.auth.security import hash_token, new_session_token
from app.cases import repository as case_repository
from app.database import create_database_engine, user_transaction
from app.main import create_app

ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "correct horse battery staple"


def public_problem(response) -> dict[str, object]:
    body = response.json()
    return {key: body[key] for key in ("status", "title", "detail")}


def register_and_login(client: TestClient) -> None:
    email = f"lawyer-{secrets.token_hex(8)}@example.com"
    register = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "SAMPLE_DATA_NOT_REAL_LAW Lawyer",
        },
    )
    assert register.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": PASSWORD},
    )
    assert login.status_code == 200


def create_client_profile(client: TestClient) -> str:
    response = client.post(
        "/api/v1/clients",
        headers=ORIGIN,
        json={"display_name": "SAMPLE_DATA_NOT_REAL_LAW Client"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_case_record(client: TestClient) -> str:
    response = client.post(
        "/api/v1/cases",
        headers=ORIGIN,
        json={
            "reference_no": f"SAMPLE-{secrets.token_hex(6)}",
            "title": "SAMPLE_DATA_NOT_REAL_LAW Matter",
            "case_type": "sample",
            "description": "SAMPLE_DATA_NOT_REAL_LAW",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_client_and_case_endpoints_enforce_tenant_isolation(api_client) -> None:
    register_and_login(api_client)
    client_a_id = create_client_profile(api_client)
    case_a_id = create_case_record(api_client)

    second_client = TestClient(
        create_app(api_client.app.state.settings),
        base_url="https://testserver",
        client=(
            f"127.0.{secrets.randbelow(256)}.{secrets.randbelow(254) + 1}",
            50002,
        ),
    )
    with second_client:
        register_and_login(second_client)
        client_b_id = create_client_profile(second_client)
        case_b_id = create_case_record(second_client)

        clients = api_client.get("/api/v1/clients")
        cases = api_client.get("/api/v1/cases")
        assert clients.status_code == cases.status_code == 200
        assert {item["id"] for item in clients.json()["items"]} == {client_a_id}
        assert {item["id"] for item in cases.json()["items"]} == {case_a_id}

        missing_client = str(uuid4())
        not_owned_client = api_client.get(f"/api/v1/clients/{client_b_id}")
        unknown_client = api_client.get(f"/api/v1/clients/{missing_client}")
        assert not_owned_client.status_code == unknown_client.status_code == 404
        assert public_problem(not_owned_client) == public_problem(unknown_client)
        not_owned_client_patch = api_client.patch(
            f"/api/v1/clients/{client_b_id}",
            headers=ORIGIN,
            json={"display_name": "Changed"},
        )
        unknown_client_patch = api_client.patch(
            f"/api/v1/clients/{missing_client}",
            headers=ORIGIN,
            json={"display_name": "Changed"},
        )
        assert (
            not_owned_client_patch.status_code
            == unknown_client_patch.status_code
            == 404
        )
        assert public_problem(not_owned_client_patch) == public_problem(
            unknown_client_patch
        )

        missing_case = str(uuid4())
        not_owned_case = api_client.get(f"/api/v1/cases/{case_b_id}")
        unknown_case = api_client.get(f"/api/v1/cases/{missing_case}")
        assert not_owned_case.status_code == unknown_case.status_code == 404
        assert public_problem(not_owned_case) == public_problem(unknown_case)
        not_owned_patch = api_client.patch(
            f"/api/v1/cases/{case_b_id}",
            headers=ORIGIN,
            json={"title": "Changed"},
        )
        unknown_patch = api_client.patch(
            f"/api/v1/cases/{missing_case}",
            headers=ORIGIN,
            json={"title": "Changed"},
        )
        assert not_owned_patch.status_code == unknown_patch.status_code == 404
        assert public_problem(not_owned_patch) == public_problem(unknown_patch)


def test_case_creation_rolls_back_case_member_and_stages_after_failure(
    api_client,
    monkeypatch,
) -> None:
    register_and_login(api_client)
    failed_case_ids: list[str] = []

    async def fail_after_first_stage(
        session,
        *,
        case_id,
        organization_id,
    ) -> None:
        failed_case_ids.append(str(case_id))
        statement = text(
            """
            INSERT INTO public.case_stages
              (case_id, organization_id, position, name, client_label, status)
            VALUES (:case_id, :organization_id, 1, 'sample', 'sample', 'current')
            """
        )
        parameters = {"case_id": case_id, "organization_id": organization_id}
        await session.execute(statement, parameters)
        await session.execute(statement, parameters)

    monkeypatch.setattr(
        case_repository,
        "insert_default_stages",
        fail_after_first_stage,
    )
    response = api_client.post(
        "/api/v1/cases",
        headers=ORIGIN,
        json={
            "reference_no": f"SAMPLE-{secrets.token_hex(6)}",
            "title": "SAMPLE_DATA_NOT_REAL_LAW Atomicity",
            "case_type": "sample",
        },
    )
    assert response.status_code == 409
    assert len(failed_case_ids) == 1
    failed_case_id = failed_case_ids[0]

    async def row_counts(
        case_id: str,
        user: LawyerDep,
        session: UserSessionDep,
    ) -> tuple[int, int, int]:
        result = await session.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM public.cases WHERE id = :case_id),
                  (SELECT count(*) FROM public.case_members
                   WHERE case_id = :case_id AND user_id = :acting_user_id),
                  (SELECT count(*) FROM public.case_stages WHERE case_id = :case_id)
                """
            ),
            {"case_id": case_id, "acting_user_id": user.id},
        )
        row = result.one()
        return int(row[0]), int(row[1]), int(row[2])

    api_client.app.add_api_route(
        "/_test/case-row-counts/{case_id}",
        row_counts,
        response_model=tuple[int, int, int],
    )
    assert api_client.get(
        f"/_test/case-row-counts/{failed_case_id}"
    ).json() == [0, 0, 0]


def test_domain_writes_require_origin_and_patch_requires_fields(api_client) -> None:
    register_and_login(api_client)

    no_origin = api_client.post(
        "/api/v1/clients",
        json={"display_name": "SAMPLE_DATA_NOT_REAL_LAW Client"},
    )
    assert no_origin.status_code == 403

    client_id = create_client_profile(api_client)
    empty_patch = api_client.patch(
        f"/api/v1/clients/{client_id}",
        headers=ORIGIN,
        json={},
    )
    assert empty_patch.status_code == 422


def test_case_scoped_rls_hides_other_users_rows(api_client) -> None:
    register_and_login(api_client)
    user_id = UUID(api_client.get("/api/v1/me").json()["id"])
    client_id = create_client_profile(api_client)
    case = api_client.get(f"/api/v1/cases/{create_case_record(api_client)}").json()
    case_id = UUID(case["id"])
    organization_id = UUID(case["organization_id"])

    second_client = TestClient(
        create_app(api_client.app.state.settings),
        base_url="https://testserver",
        client=(
            f"127.0.{secrets.randbelow(256)}.{secrets.randbelow(254) + 1}",
            50003,
        ),
    )
    with second_client:
        register_and_login(second_client)
        create_client_profile(second_client)
        create_case_record(second_client)
        other_user_id = UUID(second_client.get("/api/v1/me").json()["id"])

    database_url = api_client.app.state.settings.database_url

    async def verify_rows() -> tuple[
        tuple[int, int, int, int],
        tuple[int, int, int, int],
        tuple[int, int, int, int],
    ]:
        engine = create_database_engine(database_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async def counts(session) -> tuple[int, int, int, int]:
            result = await session.execute(
                text(
                    """
                    SELECT
                      (SELECT count(*) FROM public.cases WHERE id = :case_id),
                      (SELECT count(*) FROM public.case_members
                       WHERE case_id = :case_id AND user_id = :acting_user_id),
                      (SELECT count(*) FROM public.case_stages
                       WHERE case_id = :case_id),
                      (SELECT count(*) FROM public.case_invitations
                       WHERE case_id = :case_id)
                    """
                ),
                {"case_id": case_id, "acting_user_id": user_id},
            )
            row = result.one()
            return int(row[0]), int(row[1]), int(row[2]), int(row[3])

        try:
            async with user_transaction(session_factory, user_id) as session:
                await session.execute(
                    text(
                        """
                        INSERT INTO public.case_invitations
                          (case_id, organization_id, client_profile_id, email,
                           client_reference, token_hash, expires_at, created_by)
                        VALUES
                          (:case_id, :organization_id, :client_profile_id,
                           'sample@example.com', 'SAMPLE_DATA_NOT_REAL_LAW',
                           :token_hash, :expires_at, :acting_user_id)
                        """
                    ),
                    {
                        "case_id": case_id,
                        "organization_id": organization_id,
                        "client_profile_id": UUID(client_id),
                        "token_hash": hash_token(new_session_token()),
                        "expires_at": datetime.now(UTC) + timedelta(days=1),
                        "acting_user_id": user_id,
                    },
                )
            async with session_factory() as session:
                async with session.begin():
                    without_context = await counts(session)
            async with user_transaction(session_factory, other_user_id) as session:
                other_user = await counts(session)
            async with user_transaction(session_factory, user_id) as session:
                own_user = await counts(session)
            return without_context, other_user, own_user
        finally:
            await engine.dispose()

    without_context, other_user, own_user = asyncio.run(verify_rows())
    assert without_context == (0, 0, 0, 0)
    assert other_user == (0, 0, 0, 0)
    assert own_user == (1, 1, 6, 1)


def test_revoked_case_membership_loses_access_on_next_request(api_client) -> None:
    register_and_login(api_client)
    case_id = UUID(create_case_record(api_client))
    user_id = UUID(api_client.get("/api/v1/me").json()["id"])
    database_url = api_client.app.state.settings.database_url

    async def revoke_membership() -> None:
        engine = create_database_engine(database_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with user_transaction(session_factory, user_id) as session:
                result = await session.execute(
                    text(
                        """
                        UPDATE public.case_members
                        SET status = 'revoked', revoked_at = now()
                        WHERE case_id = :case_id AND user_id = :acting_user_id
                        """
                    ),
                    {"case_id": case_id, "acting_user_id": user_id},
                )
                assert result.rowcount == 1
        finally:
            await engine.dispose()

    asyncio.run(revoke_membership())

    assert api_client.get(f"/api/v1/cases/{case_id}").status_code == 404
