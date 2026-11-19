"""Batch 4: case API contract (TRD §3.1).

- ``ETag`` on case reads and writes; ``If-Match`` required on case PATCH
  (428 missing, 412 stale) so concurrent edits cannot silently overwrite.
- Cursor pagination (``?cursor=&limit=``) on cases, clients and case audit,
  scoped by RLS so a cursor never reveals another tenant's rows.
Synthetic data only.
"""

import re
import secrets

from fastapi.testclient import TestClient

from tests.test_rls_bypass import ORIGIN, SAMPLE, _client, _post, _register_login

ETAG = re.compile(r'^"\d+"$')


def _new_case(lawyer: TestClient) -> str:
    return _post(
        lawyer,
        "/api/v1/cases",
        {"reference_no": f"SAMPLE-B4-{secrets.token_hex(4)}", "title": f"{SAMPLE} Matter", "case_type": "sample"},
    )["id"]


def _all_pages(lawyer: TestClient, path: str, limit: int) -> list[list[str]]:
    pages, cursor = [], None
    while True:
        params = {"limit": limit} | ({"cursor": cursor} if cursor else {})
        response = lawyer.get(path, params=params)
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) == {"items", "next_cursor"}
        pages.append([item["id"] if isinstance(item["id"], str) else str(item["id"]) for item in body["items"]])
        cursor = body["next_cursor"]
        if cursor is None:
            return pages


def test_case_patch_requires_a_matching_if_match(api_client) -> None:
    _register_login(api_client, "etag")
    case_id = _new_case(api_client)

    read = api_client.get(f"/api/v1/cases/{case_id}")
    etag = read.headers.get("etag")
    assert etag and ETAG.match(etag)

    missing = api_client.patch(f"/api/v1/cases/{case_id}", headers=ORIGIN, json={"title": f"{SAMPLE} A"})
    assert missing.status_code == 428
    assert missing.headers["content-type"].startswith("application/problem+json")

    first = api_client.patch(
        f"/api/v1/cases/{case_id}", headers=ORIGIN | {"If-Match": etag}, json={"title": f"{SAMPLE} A"}
    )
    assert first.status_code == 200
    new_etag = first.headers.get("etag")
    assert new_etag and new_etag != etag

    stale = api_client.patch(
        f"/api/v1/cases/{case_id}", headers=ORIGIN | {"If-Match": etag}, json={"title": f"{SAMPLE} B"}
    )
    assert stale.status_code == 412
    garbage = api_client.patch(
        f"/api/v1/cases/{case_id}", headers=ORIGIN | {"If-Match": "W/not-a-tag"}, json={"title": f"{SAMPLE} B"}
    )
    assert garbage.status_code == 412
    assert api_client.get(f"/api/v1/cases/{case_id}").json()["title"] == f"{SAMPLE} A"
    assert api_client.get(f"/api/v1/cases/{case_id}").headers["etag"] == new_etag


def test_case_list_is_cursor_paginated_without_gaps_or_duplicates(api_client) -> None:
    _register_login(api_client, "page-cases")
    created = {_new_case(api_client) for _ in range(5)}

    pages = _all_pages(api_client, "/api/v1/cases", limit=2)

    assert [len(page) for page in pages] == [2, 2, 1]
    seen = [case_id for page in pages for case_id in page]
    assert len(seen) == len(set(seen)) == 5
    assert set(seen) == created


def test_client_list_and_case_audit_are_cursor_paginated(api_client) -> None:
    _register_login(api_client, "page-clients")
    for index in range(3):
        _post(api_client, "/api/v1/clients", {"display_name": f"{SAMPLE} Client {index}"})
    client_pages = _all_pages(api_client, "/api/v1/clients", limit=2)
    assert [len(page) for page in client_pages] == [2, 1]

    case_id = _new_case(api_client)
    for _ in range(3):
        _post(api_client, f"/api/v1/cases/{case_id}/client-updates", {"title": SAMPLE, "body": SAMPLE})
    audit_pages = _all_pages(api_client, f"/api/v1/cases/{case_id}/audit", limit=3)
    audit_ids = [event for page in audit_pages for event in page]
    assert len(audit_ids) == len(set(audit_ids)) >= 4
    assert len(audit_pages) >= 2


def test_pagination_rejects_bad_input(api_client) -> None:
    _register_login(api_client, "page-bad")
    for params in ({"limit": 0}, {"limit": 101}):
        assert api_client.get("/api/v1/cases", params=params).status_code == 422
    for cursor in ("not-base64!", "eyJhdCI6IjIwMjYiLCJpZCI6Im5vdC1hLXV1aWQifQ"):
        bad = api_client.get("/api/v1/cases", params={"cursor": cursor})
        assert bad.status_code == 400
        assert bad.headers["content-type"].startswith("application/problem+json")


def test_a_cursor_never_reveals_another_tenants_rows(api_client) -> None:
    settings = api_client.app.state.settings
    _register_login(api_client, "page-a")
    for _ in range(3):
        _new_case(api_client)
    cursor = api_client.get("/api/v1/cases", params={"limit": 1}).json()["next_cursor"]
    assert cursor

    with _client(settings, 51) as other:
        _register_login(other, "page-b")
        own = _new_case(other)
        page = other.get("/api/v1/cases", params={"cursor": cursor, "limit": 50}).json()
        assert {item["id"] for item in page["items"]} <= {own}
