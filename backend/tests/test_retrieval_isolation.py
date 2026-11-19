"""Retrieval isolation (TRD §14, database.md §6/§16) — Phase 4 exit check.

Two organizations, two lawyers, a client, and near-identical chunk text in two
cases. Each lawyer's text search returns only their own case's chunks even with
no case filter (RLS), an explicit filter on the other case returns nothing, and
a client gets nothing from ``document_chunks``.

BLOCKED until Backend Dev 2 lands ``documents``, ``extracted_pages`` and
``document_chunks`` with RLS (requests R12). Until then the test skips with that
reason instead of passing. Inserts follow the database.md §6 columns.
"""

import hashlib
import secrets
from uuid import UUID

import pytest

from tests.test_auth_hardening import _run_as
from tests.test_b13_gaps import _invite
from tests.test_rls_bypass import SAMPLE, _client, _post, _register_login

REQUIRED_TABLES = ("documents", "extracted_pages", "document_chunks")
QUERY = "cheque dishonour notice"


def _missing_tables(database_url: str, user_id: UUID) -> list[str]:
    rows = _run_as(
        database_url,
        user_id,
        "SELECT t FROM unnest(CAST(:tables AS text[])) AS t WHERE to_regclass('public.' || t) IS NULL",
        {"tables": list(REQUIRED_TABLES)},
    )
    return [row[0] for row in rows]


def _seed_chunk(database_url: str, lawyer_id: UUID, case: dict, variant: str) -> None:
    text = f"{SAMPLE} cheque dishonour notice served on the drawer {variant}"
    params = {
        "case_id": UUID(case["id"]),
        "org": UUID(case["organization_id"]),
        "me": lawyer_id,
        "sha": hashlib.sha256(text.encode()).digest(),
        "text": text,
    }
    _run_as(
        database_url,
        lawyer_id,
        """
        WITH d AS (
          INSERT INTO public.documents (case_id, organization_id, title, original_filename, mime_type,
            size_bytes, sha256, storage_key, uploaded_by)
          VALUES (:case_id, :org, 'SAMPLE', 'sample.pdf', 'application/pdf', 1, :sha, 'sample', :me)
          RETURNING id),
        p AS (
          INSERT INTO public.extracted_pages (document_id, case_id, organization_id, page_no, text, source_method)
          SELECT d.id, :case_id, :org, 1, :text, 'text_layer' FROM d
          RETURNING id, document_id)
        INSERT INTO public.document_chunks (case_id, organization_id, document_id, page_id, page_no,
          chunk_index, char_start, char_end, text, embedding_model, embedding_version, processing_version)
        SELECT :case_id, :org, p.document_id, p.id, 1, 0, 0, length(:text), :text, 'mock', 1, 1 FROM p
        """,
        params,
    )


def _search(database_url: str, user_id: UUID, case_id: str | None = None) -> set[str]:
    sql = (
        "SELECT DISTINCT case_id::text FROM public.document_chunks "
        "WHERE is_active AND tsv @@ plainto_tsquery('simple', :q)"
    )
    params: dict = {"q": QUERY}
    if case_id is not None:
        sql += " AND case_id = :case_id"
        params["case_id"] = UUID(case_id)
    return {row[0] for row in _run_as(database_url, user_id, sql, params)}


def test_case_retrieval_never_crosses_cases_or_tenants(api_client) -> None:
    settings = api_client.app.state.settings
    lawyer_a = _register_login(api_client, "retrieval-a")
    missing = _missing_tables(settings.database_url, lawyer_a)
    if missing:
        pytest.skip(f"BLOCKED on Dev 2 schema (request R12): missing tables {missing}")

    case_a = _post(api_client, "/api/v1/cases", {
        "reference_no": f"SAMPLE-RET-A-{secrets.token_hex(4)}", "title": SAMPLE, "case_type": "sample"})
    with _client(settings, 71) as lawyer_b_tc, _client(settings, 72) as client_a:
        lawyer_b = _register_login(lawyer_b_tc, "retrieval-b")
        case_b = _post(lawyer_b_tc, "/api/v1/cases", {
            "reference_no": f"SAMPLE-RET-B-{secrets.token_hex(4)}", "title": SAMPLE, "case_type": "sample"})
        _invite(api_client, client_a, case_a["id"])
        client_id = UUID(client_a.get("/api/v1/me").json()["id"])

    _seed_chunk(settings.database_url, lawyer_a, case_a, "variant A")
    _seed_chunk(settings.database_url, lawyer_b, case_b, "variant B")

    assert _search(settings.database_url, lawyer_a) == {case_a["id"]}
    assert _search(settings.database_url, lawyer_b) == {case_b["id"]}
    assert _search(settings.database_url, lawyer_a, case_id=case_b["id"]) == set()
    assert _search(settings.database_url, client_id) == set()
