"""Route-inventory guards: every mounted route is checked, so new routes cannot slip
past case authorization or CSRF protection.

These tests inspect the dependency tree of the single app factory and need no
database. Behavioural checks (401/404/403 over HTTP) are in the DB-backed tests
at the bottom of this module.
"""

import secrets
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from app.auth.dependencies import (
    get_current_user,
    require_same_origin,
    require_same_origin_for_writes,
)
from app.cases.dependencies import get_case_access
from app.config import Settings
from app.main import create_app

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Routes that act on a case_id but are client-namespace reads authorized by
# client RLS policies plus SQL filters, not by the lawyer CaseAccess dependency.
CLIENT_PREFIX = "/api/v1/client/"
DEV2_CASE_PATHS = ("/analysis", "/timeline", "/contradictions", "/evidence", "/strategies")


def _calls(dependant: Dependant) -> set:
    found = set()
    for dep in dependant.dependencies:
        found.add(dep.call)
        found |= _calls(dep)
    return found


def _api_routes() -> list:
    """Every effective API route with its full path and merged dependant.

    FastAPI 0.164 keeps included routers nested (``_IncludedRouter``) instead of
    flattening them into ``app.routes``; their ``effective_route_contexts()``
    expose full paths and router-level dependencies. Older versions flatten.
    """
    app = create_app(Settings(app_env="test"))
    routes: list = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes.append(route)
        elif hasattr(route, "effective_route_contexts"):
            routes.extend(route.effective_route_contexts())
    assert len(routes) > 40, "route inventory looks incomplete"
    return routes


def test_every_lawyer_case_route_requires_case_access() -> None:
    missing = [
        f"{sorted(r.methods)} {r.path}"
        for r in _api_routes()
        if "{case_id}" in r.path
        and not r.path.startswith(CLIENT_PREFIX)
        and get_case_access not in _calls(r.dependant)
    ]
    assert missing == []


def test_every_state_changing_route_requires_same_origin() -> None:
    guards = {require_same_origin, require_same_origin_for_writes}
    missing = [
        f"{sorted(r.methods)} {r.path}"
        for r in _api_routes()
        if r.methods - SAFE_METHODS and not guards & _calls(r.dependant)
    ]
    assert missing == []


def test_every_api_route_except_public_auth_requires_a_session() -> None:
    public = {
        "/health",
        "/health/ready",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/password/forgot",
        "/api/v1/auth/password/reset",
        "/api/v1/auth/invitations/accept",
    }
    missing = [
        f"{sorted(r.methods)} {r.path}"
        for r in _api_routes()
        if r.path not in public and get_current_user not in _calls(r.dependant)
    ]
    assert missing == []


def test_dev2_case_routers_are_mounted_once_in_the_single_app() -> None:
    routes = _api_routes()
    keys = [(frozenset(r.methods), r.path) for r in routes]
    assert len(keys) == len(set(keys)), "duplicate method+path"
    for suffix in DEV2_CASE_PATHS:
        assert any(
            r.path.startswith("/api/v1/cases/{case_id}") and suffix in r.path
            for r in routes
        ), suffix


# --- DB-backed behaviour (skipped without TEST_DATABASE_URL) -----------------

ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "correct horse battery staple"


def _register_and_login(client: TestClient) -> None:
    email = f"guards-{secrets.token_hex(8)}@example.com"
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


def _create_case(client: TestClient) -> str:
    response = client.post(
        "/api/v1/cases",
        headers=ORIGIN,
        json={
            "reference_no": f"SAMPLE-GUARD-{secrets.token_hex(4)}",
            "title": "SAMPLE_DATA_NOT_REAL_LAW Matter",
            "case_type": "sample",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def registered_lawyer(api_client) -> None:
    _register_and_login(api_client)


def test_dev2_case_routes_reject_anonymous_callers(api_client) -> None:
    response = api_client.get(f"/api/v1/cases/{uuid4()}/strategies")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.parametrize(
    ("method", "suffix"),
    [
        ("get", "/analysis"),
        ("get", "/timeline"),
        ("get", "/strategies"),
        ("post", "/strategies/generate"),
    ],
)
def test_dev2_case_routes_return_404_for_unknown_case(
    api_client, registered_lawyer, method: str, suffix: str
) -> None:
    kwargs = {"headers": ORIGIN}
    if method == "post":
        kwargs["json"] = {}
    response = getattr(api_client, method)(
        f"/api/v1/cases/{uuid4()}{suffix}", **kwargs
    )

    assert response.status_code == 404


def test_dev2_case_write_without_origin_is_rejected(
    api_client, registered_lawyer
) -> None:
    response = api_client.post(
        f"/api/v1/cases/{uuid4()}/strategies/generate", json={}
    )

    assert response.status_code == 403


def test_dev2_case_routes_isolate_cases_between_lawyers(api_client) -> None:
    _register_and_login(api_client)
    own_case = _create_case(api_client)
    assert api_client.get(f"/api/v1/cases/{own_case}/timeline").status_code == 200

    _register_and_login(api_client)  # second lawyer, different organization
    other = api_client.get(f"/api/v1/cases/{own_case}/timeline")
    unknown = api_client.get(f"/api/v1/cases/{uuid4()}/timeline")

    assert other.status_code == 404
    assert unknown.status_code == 404
    assert other.json()["detail"] == unknown.json()["detail"]


def test_dev1_routes_declare_typed_response_models() -> None:
    """Dev 1 routes never return raw dicts (Dev 2 routes tracked as request R14)."""
    untyped = []
    for route in _api_routes():
        endpoint = getattr(route, "endpoint", None) or route.original_route.endpoint
        if endpoint.__module__.startswith("backend.src"):
            continue
        model = route.response_model
        origin = getattr(model, "__origin__", None)
        if model in (None, dict) or origin is dict:
            untyped.append(f"{sorted(route.methods)} {route.path}")
    assert untyped == []
