"""Role-specific login, shared documents, lawyer contact card, summary PDFs.

All case content is SAMPLE_DATA_NOT_REAL_LAW.
"""

import secrets
from pathlib import Path

import pymupdf

from app.auth.dependencies import SESSION_COOKIE_NAME
from tests.step_c_helpers import ORIGIN, lawyer_with_case, new_client, sql_as, upload
from tests.test_phase2_exit import PASSWORD, create_case
from tests.test_ui_bug_fixes import _client_with_login

PDF = Path(__file__).parent / "data" / "case1_cheque_dishonour.pdf"
BN_BODY = "SAMPLE_DATA_NOT_REAL_LAW আদালত ক্ষতিপূরণ ও স্বাক্ষর যাচাইয়ের নির্দেশ দিয়েছেন।"


def login(client, email: str, password: str, role: str | None):
    client.cookies.clear()
    body = {"email": email, "password": password, **({"expected_role": role} if role else {})}
    return client.post("/api/v1/auth/login", headers=ORIGIN, json=body)


def actions(database_url, user_id, case_id) -> list[str]:
    return [r[0] for r in sql_as(database_url, user_id,
                                 "SELECT action FROM public.audit_logs WHERE case_id = :c ORDER BY id", c=case_id)]


def pdf_fonts(data: bytes) -> set[str]:
    document = pymupdf.open(stream=data, filetype="pdf")
    return {font[3] for page in document for font in page.get_fonts()}


def test_login_is_role_specific_without_enumeration(api_client, local_app_user_database_url) -> None:
    lawyer_email = f"portal-lawyer-{secrets.token_hex(6)}@example.com"
    assert api_client.post("/api/v1/auth/register", headers=ORIGIN, json={
        "email": lawyer_email, "password": PASSWORD, "full_name": "SAMPLE Portal Lawyer"}).status_code == 201
    assert login(api_client, lawyer_email, PASSWORD, "lawyer").status_code == 200
    case_id = create_case(api_client, f"SAMPLE-portal-{secrets.token_hex(3)}")
    client = new_client(api_client, 0)
    with client:
        _client_with_login(api_client, client, case_id)
        client_email = sql_as(local_app_user_database_url, login(api_client, lawyer_email, PASSWORD, "lawyer").json()[
            "id"], "SELECT email::text FROM public.client_profiles WHERE organization_id = "
                   "(SELECT organization_id FROM public.cases WHERE id = :c)", c=case_id)[0][0]

        wrong_password = login(client, lawyer_email, PASSWORD + "x", "lawyer")
        for email, role in ((lawyer_email, "client"), (client_email, "lawyer")):
            mismatch = login(client, email, PASSWORD, role)
            assert mismatch.status_code == 401 == wrong_password.status_code
            assert mismatch.json()["detail"] == wrong_password.json()["detail"]  # no enumeration
            assert SESSION_COOKIE_NAME not in mismatch.cookies  # no session
            assert client.get("/api/v1/me").status_code == 401
        lawyer = login(client, lawyer_email, PASSWORD, "lawyer").json()
        assert lawyer["role"] == "lawyer"
        assert login(client, client_email, PASSWORD, "client").json()["role"] == "client"

        def failed_logins() -> int:
            return sql_as(local_app_user_database_url, lawyer["id"],
                          "SELECT failed_logins FROM public.users WHERE id = :u", u=lawyer["id"])[0][0]

        before = failed_logins()
        login(client, lawyer_email, PASSWORD, "client")
        assert failed_logins() == before  # a wrong portal is not counted toward lockout
        events = sql_as(local_app_user_database_url, lawyer["id"],
                        "SELECT count(*) FROM public.audit_logs WHERE actor_user_id = :u "
                        "AND action = 'auth.login_wrong_portal'", u=lawyer["id"])[0][0]
        assert events >= 2


def test_shared_documents_reach_only_their_client(api_client, local_app_user_database_url) -> None:
    user_id, case_id = lawyer_with_case(api_client, "share-docs")
    data = PDF.read_bytes()
    document_id = upload(api_client, case_id, data, "case1_cheque_dishonour.pdf").json()["document"]["id"]
    other_case = create_case(api_client, f"SAMPLE-share-other-{secrets.token_hex(3)}")
    share_url = f"/api/v1/cases/{case_id}/shared-documents"
    client, other = new_client(api_client, 0), new_client(api_client, 0)
    with client, other:
        _client_with_login(api_client, client, case_id)
        _client_with_login(api_client, other, other_case)
        download = f"/api/v1/client/documents/{document_id}/download"

        assert client.get(f"/api/v1/client/cases/{case_id}/documents").json() == []  # default off
        assert client.get(download).status_code == 404

        assert api_client.post(share_url, json={"document_id": document_id}).status_code == 403  # CSRF
        assert api_client.post(f"/api/v1/cases/{other_case}/shared-documents", headers=ORIGIN,
                               json={"document_id": document_id}).status_code == 404  # not that case's document
        shared = api_client.post(share_url, headers=ORIGIN, json={"document_id": document_id})
        assert shared.status_code == 201 and shared.json()["display_name"] == "case1_cheque_dishonour.pdf"

        listed = client.get(f"/api/v1/client/cases/{case_id}/documents").json()
        assert [d["document_id"] for d in listed] == [document_id]
        got = client.get(download)
        assert got.status_code == 200 and got.content == data
        assert got.headers["content-type"] == "application/pdf"
        assert got.headers["content-disposition"].startswith('attachment; filename="case1_cheque_dishonour.pdf"')
        assert other.get(download).status_code == 404  # another client
        assert other.get(f"/api/v1/client/cases/{case_id}/documents").status_code == 404
        assert client.post(share_url, headers=ORIGIN, json={"document_id": document_id}).status_code == 403

        revoked = api_client.delete(f"{share_url}/{document_id}", headers=ORIGIN)
        assert revoked.status_code == 200 and revoked.json()["revoked_at"]
        assert client.get(download).status_code == 404
        assert client.get(f"/api/v1/client/cases/{case_id}/documents").json() == []
        assert api_client.get(share_url).json()[0]["revoked_at"]  # history kept
        client_id = client.get("/api/v1/me").json()["id"]
        downloads = sql_as(local_app_user_database_url, client_id,
                           "SELECT details->>'case_id' FROM public.audit_logs WHERE actor_user_id = :u "
                           "AND action = 'client.document_downloaded'", u=client_id)
        assert [row[0] for row in downloads] == [case_id]
    events = actions(local_app_user_database_url, user_id, case_id)
    assert {"client_document.shared", "client_document.unshared"} <= set(events)


def test_lawyer_contact_card_shows_only_approved_filled_fields(api_client) -> None:
    _, case_id = lawyer_with_case(api_client, "contact")
    client, stranger = new_client(api_client, 0), new_client(api_client, 0)
    with client, stranger:
        _client_with_login(api_client, client, case_id)
        url = f"/api/v1/client/cases/{case_id}/lawyer"
        card = client.get(url).json()
        assert card["full_name"].startswith("SAMPLE_DATA_NOT_REAL_LAW") and card["phone"] is None  # not filled in
        assert api_client.patch("/api/v1/lawyer/profile", headers=ORIGIN, json={
            "phone": "+880 1700-000000", "chamber_name": "SAMPLE Chamber"}).status_code == 200
        card = client.get(url).json()
        assert (card["firm"], card["phone"]) == ("SAMPLE Chamber", "+880 1700-000000") and card["email"]
        assert api_client.patch("/api/v1/lawyer/profile", headers=ORIGIN,
                                json={"show_contact_to_clients": False}).status_code == 200
        hidden = client.get(url).json()
        assert hidden["full_name"] and (hidden["firm"], hidden["phone"], hidden["email"]) == (None, None, None)
        other_case = create_case(api_client, f"SAMPLE-contact-{secrets.token_hex(3)}")
        _client_with_login(api_client, stranger, other_case)
        assert stranger.get(url).status_code == 404
        assert api_client.get(url).status_code == 403  # client API only


def test_summary_pdfs_are_server_rendered_with_bangla_font(api_client, local_app_user_database_url) -> None:
    user_id, case_id = lawyer_with_case(api_client, "pdf")
    update = api_client.post(f"/api/v1/cases/{case_id}/client-updates", headers=ORIGIN, json={
        "title": "শুনানির হালনাগাদ", "body": BN_BODY, "language": "bn"}).json()
    client, other = new_client(api_client, 0), new_client(api_client, 0)
    with client, other:
        _client_with_login(api_client, client, case_id)
        _client_with_login(api_client, other, create_case(api_client, f"SAMPLE-pdf-{secrets.token_hex(3)}"))
        url = f"/api/v1/client/updates/{update['id']}/pdf?language=bn"
        assert client.get(url).status_code == 404  # draft: not approved
        assert api_client.post(f"/api/v1/client-updates/{update['id']}/publish", headers=ORIGIN).status_code == 200
        pdf = client.get(url)
        assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
        assert pdf.headers["content-disposition"].startswith('attachment; filename="case-update-')
        assert {"Noto Sans Bengali Regular", "Noto Sans Regular"} <= pdf_fonts(pdf.content)
        assert other.get(url).status_code == 404

        hearing = api_client.post(f"/api/v1/lawyer/cases/{case_id}/hearings", headers=ORIGIN, json={
            "scheduled_at": "2025-01-10T10:00:00Z", "purpose": "SAMPLE", "date_confirmed": True}).json()
        lawyer_url = f"/api/v1/lawyer/cases/{case_id}/hearings/{hearing['id']}/summary-pdf"
        body = {"eyebrow": "শুনানির সারসংক্ষেপ", "title": "Hearing 1 summary", "filename": "hearing-1-summary.pdf",
                "meta": [{"label": "Court", "value": "SAMPLE court"}], "notice": "Draft — not legal advice.",
                "sections": [{"heading": "মূল নোট", "items": [
                    {"text": BN_BODY, "tags": ["Lawyer entered", "Verified"], "source": "Hearing record"}]}]}
        lawyer_pdf = api_client.post(lawyer_url, headers=ORIGIN, json=body)
        assert lawyer_pdf.status_code == 200, lawyer_pdf.text
        assert lawyer_pdf.headers["content-disposition"].startswith('attachment; filename="hearing-1-summary.pdf"')
        assert {"Noto Sans Bengali Regular", "Noto Sans Bengali Bold"} <= pdf_fonts(lawyer_pdf.content)
        assert client.post(lawyer_url, headers=ORIGIN, json=body).status_code == 403
        assert api_client.post(lawyer_url, headers=ORIGIN, json={**body, "filename": "../x.pdf"}).status_code == 422
    assert "hearing_summary.downloaded" in actions(local_app_user_database_url, user_id, case_id)
