"""Authorization matrix (Security.md §15), generated from the live route inventory.

Every mounted API route is called by each actor with a real session. New routes
are covered automatically; a route whose guard is missing fails here.

Expected outcomes:
- anonymous                      -> 401 on every non-public route
- client of the case             -> 403 on every lawyer route
- lawyer, other organization     -> 404 on case routes, 403 on client routes
- lawyer, read_only membership   -> 404 on case routes (read_only grants nothing yet)
- lawyer, revoked membership     -> 404 on case routes
- owning lead lawyer (GET only)  -> never 401/403/404 on case routes
"""

import re
import secrets
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from tests.test_auth_hardening import _run_as
from tests.test_b13_gaps import _invite
from tests.test_route_guards import _api_routes
from tests.test_rls_bypass import ORIGIN, SAMPLE, _client, _post, _register_login

PUBLIC = {
    "/health",
    "/health/ready",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/password/forgot",
    "/api/v1/auth/password/reset",
    "/api/v1/auth/invitations/accept",
}
# Session-management routes are exercised anonymously only: calling them as a
# signed-in actor would log that actor out or change MFA state mid-matrix.
SELF_SERVICE_PREFIXES = ("/api/v1/auth/", "/api/v1/me")
CLIENT_PREFIX = "/api/v1/client/"
PARAM = re.compile(r"\{(\w+)\}")


def _url(path: str, case_id: str) -> str:
    return PARAM.sub(lambda m: case_id if m.group(1) == "case_id" else str(uuid4()), path)


def _call(client: TestClient, method: str, url: str) -> int:
    kwargs = {"headers": ORIGIN}
    if method in {"POST", "PATCH", "PUT"}:
        kwargs["json"] = {}
    return client.request(method, url, **kwargs).status_code


def _join_case(lead: TestClient, lead_id: UUID, case: dict, member: TestClient, label: str, status: str) -> None:
    member_id = _register_login(member, label)
    database_url = lead.app.state.settings.database_url
    _run_as(
        database_url,
        lead_id,
        "INSERT INTO public.organization_members (organization_id, user_id, org_role) "
        "VALUES (:org, :user, 'lawyer')",
        {"org": UUID(case["organization_id"]), "user": member_id},
    )
    _post(lead, f"/api/v1/cases/{case['id']}/members", {"user_id": str(member_id), "role": "team_lawyer"})
    _run_as(
        database_url,
        lead_id,
        "UPDATE public.case_members SET status = :status, "
        "revoked_at = CASE WHEN :status = 'revoked' THEN now() END "
        "WHERE case_id = :case_id AND user_id = :user_id",
        {"status": status, "case_id": UUID(case["id"]), "user_id": member_id},
    )


def test_authorization_matrix_covers_every_route(api_client) -> None:
    settings = api_client.app.state.settings
    lead_id = _register_login(api_client, "matrix-lead")
    case = _post(
        api_client,
        "/api/v1/cases",
        {"reference_no": f"SAMPLE-MX-{secrets.token_hex(4)}", "title": f"{SAMPLE} Matter", "case_type": "sample"},
    )
    case_id = case["id"]
    routes = [
        (method, route.path)
        for route in _api_routes()
        for method in sorted(route.methods - {"HEAD", "OPTIONS"})
    ]
    assert len(routes) > 40

    with (
        _client(settings, 41) as anonymous,
        _client(settings, 42) as client,
        _client(settings, 43) as other_lawyer,
        _client(settings, 44) as read_only,
        _client(settings, 45) as revoked,
    ):
        _invite(api_client, client, case_id)
        _register_login(other_lawyer, "matrix-other")
        _join_case(api_client, lead_id, case, read_only, "matrix-readonly", "read_only")
        _join_case(api_client, lead_id, case, revoked, "matrix-revoked", "revoked")

        failures = []
        checks = []

        def expect(actor: str, tc: TestClient, method: str, path: str, allowed: set[int]) -> None:
            code = _call(tc, method, _url(path, case_id))
            checks.append(code)
            if code not in allowed:
                failures.append(f"{actor:9} {method:6} {path} -> {code}, expected {sorted(allowed)}")

        for method, path in routes:
            if path in PUBLIC:
                continue
            expect("anonymous", anonymous, method, path, {401})
            if path.startswith(SELF_SERVICE_PREFIXES):
                continue
            is_client_route = path.startswith(CLIENT_PREFIX)
            is_case_route = "{case_id}" in path and not is_client_route
            if not is_client_route:
                expect("client", client, method, path, {403})
            for actor, tc in (("other", other_lawyer), ("read_only", read_only), ("revoked", revoked)):
                if is_client_route:
                    expect(actor, tc, method, path, {403})
                elif is_case_route:
                    expect(actor, tc, method, path, {404})
            if is_case_route and method == "GET":
                code = _call(api_client, method, _url(path, case_id))
                unexpected_404 = code == 404 and path.count("{") == 1
                if code in {401, 403} or unexpected_404:
                    failures.append(f"owner     {method:6} {path} -> {code}")

    assert len(checks) > 150, len(checks)
    assert failures == []
