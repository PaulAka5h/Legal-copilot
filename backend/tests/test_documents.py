"""Step C1: document upload, storage, extraction, OCR, page versions. SAMPLE_DATA_NOT_REAL_LAW."""

import pytest

from app.config import Settings
from app.documents.extraction import ocr_engine_for
from app.documents.processing import ScannerNotConfigured, scan_status_for
from app.documents.storage import MinioStore
from tests.step_c_helpers import ORIGIN, SAMPLE, lawyer_with_case, sample_pdf, sample_png, upload

EN = [f"{SAMPLE}: On 12 March 2024 the sample buyer paid the sample seller."]
BN = ["১২ মার্চ ২০২৪ তারিখে নমুনা ক্রেতা টাকা পরিশোধ করেন।"]


def test_production_refuses_without_malware_scanner():
    with pytest.raises(ScannerNotConfigured):
        scan_status_for(Settings(app_env="production", malware_scanner="none"))
    assert scan_status_for(Settings(app_env="development")) == "not_configured"


def test_upload_pdf_stores_original_and_versioned_pages(api_client):
    _, case_id = lawyer_with_case(api_client, "doc-upload")
    data = sample_pdf(EN, BN)
    response = upload(api_client, case_id, data)
    assert response.status_code == 201, response.text
    body = response.json()
    document = body["document"]
    assert document["processing_status"] == "ready"
    assert document["scan_status"] == "not_configured"
    assert document["page_count"] == 1 and document["language"] == "mixed"
    assert any(w.startswith("malware_scan_not_configured") for w in body["warnings"])

    store = MinioStore(api_client.app.state.settings)
    key = f"cases/{case_id}/documents/{document['id']}"
    assert store.get(key) == data  # original kept byte for byte, key scoped by case

    page = api_client.get(f"/api/v1/lawyer/cases/{case_id}/documents/{document['id']}/pages/1").json()
    assert page["current"]["source_method"] == "text_layer" and page["current"]["version"] == 1
    assert BN[0] in page["current"]["text"]

    assert upload(api_client, case_id, data).status_code == 409  # duplicate in the same case
    listed = api_client.get(f"/api/v1/lawyer/cases/{case_id}/documents").json()
    assert [d["id"] for d in listed] == [document["id"]]

    corrected = api_client.post(
        f"/api/v1/lawyer/cases/{case_id}/documents/{document['id']}/pages/1/versions",
        headers=ORIGIN, json={"text": f"{SAMPLE} corrected page"},
    )
    assert corrected.status_code == 201
    versions = corrected.json()
    assert versions["current"]["version"] == 2 and versions["current"]["source_method"] == "lawyer_edit"
    assert [v["version"] for v in versions["history"]] == [2, 1]
    assert not versions["history"][1]["is_current"]


def test_upload_rejections(api_client):
    import pymupdf

    _, case_id = lawyer_with_case(api_client, "doc-reject")
    assert upload(api_client, case_id, b"plain text, not a document", "a.txt").status_code == 415
    assert upload(api_client, case_id, b"%PDF-" + b"0" * (20 * 1024 * 1024)).status_code == 413

    document = pymupdf.open()
    document.new_page().insert_text((40, 60), SAMPLE)
    encrypted = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
    response = upload(api_client, case_id, encrypted)
    assert response.status_code == 422 and "encrypted_pdf" in response.text

    no_origin = api_client.post(f"/api/v1/lawyer/cases/{case_id}/documents",
                                files={"file": ("a.pdf", sample_pdf(EN), "application/pdf")})
    assert no_origin.status_code == 403  # same-origin check on writes


def test_scanned_image_uses_ocr_or_flags_not_configured(api_client):
    _, case_id = lawyer_with_case(api_client, "doc-ocr")
    response = upload(api_client, case_id, sample_png("SAMPLE notice dated 2024"), "scan.png")
    assert response.status_code == 201, response.text
    body = response.json()
    page = api_client.get(
        f"/api/v1/lawyer/cases/{case_id}/documents/{body['document']['id']}/pages/1"
    ).json()["current"]
    assert page["source_method"] == "ocr"
    if ocr_engine_for("ben+eng") is None:
        assert page["ocr_engine"] == "not_configured" and page["text"] == ""
        assert page["quality_flag"] == "needs_review"
        assert body["document"]["processing_status"] == "needs_review"
        assert any(w.startswith("ocr_not_configured") for w in body["warnings"])
    else:
        assert page["ocr_engine"].startswith("tesseract")
        assert 0 <= page["ocr_confidence"] <= 1 and "SAMPLE" in page["text"]


def test_bangla_scanned_statute_page_ocr_quality(api_client):
    """Public statute text (bdlaws Act 609, not client data), rendered as a scanned page."""
    import difflib
    import io
    import json
    import random
    import textwrap
    import unicodedata
    from pathlib import Path

    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    if ocr_engine_for("ben+eng") is None:
        pytest.skip("Tesseract with ben+eng is not installed")
    dataset = Path(__file__).resolve().parents[2] / "data-scrapper" / "data" / "processed" / "sections.jsonl"
    if not dataset.exists():
        pytest.skip("sections.jsonl not exported")
    with open(dataset, encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if '"act_id": "609"' in line]
    source = "\n".join([r["section_content"] for r in rows if r["language"] == "bn"][:4])

    font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf", 38,
                              layout_engine=ImageFont.Layout.RAQM)
    lines = [w for para in source.split("\n") for w in (textwrap.wrap(para, 70) or [""])]
    image = Image.new("L", (2480, 120 + 64 * len(lines)), 255)
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text((120, 60 + 64 * i), line, fill=0, font=font)
    random.seed(7)
    image = image.filter(ImageFilter.GaussianBlur(0.8))
    pixels = image.load()
    for _ in range(image.width * image.height // 400):
        pixels[random.randrange(image.width), random.randrange(image.height)] = random.choice((0, 255))
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")

    _, case_id = lawyer_with_case(api_client, "doc-bn-ocr")
    body = upload(api_client, case_id, buffer.getvalue(), "act-609-scan.png").json()
    page = api_client.get(
        f"/api/v1/lawyer/cases/{case_id}/documents/{body['document']['id']}/pages/1"
    ).json()["current"]
    norm = lambda s: " ".join(unicodedata.normalize("NFC", s).split())  # noqa: E731
    accuracy = difflib.SequenceMatcher(None, norm(source), norm(page["text"])).ratio()
    print(f"\nBangla OCR: confidence={page['ocr_confidence']}, char_accuracy={accuracy:.3f}")
    assert page["source_method"] == "ocr" and page["ocr_engine"].startswith("tesseract")
    assert page["language"] == "bn" and page["quality_flag"] == "ok"
    assert page["ocr_confidence"] >= 0.8  # measured 0.92 on 2026-11-20
    assert accuracy >= 0.9  # measured 0.969


def test_oversized_pdf_pages_are_refused_and_renders_are_bounded():
    import pymupdf

    from app.documents.extraction import render_dpi
    from app.documents.validation import MAX_IMAGE_PIXELS, DocumentRejected, validate_upload

    huge = pymupdf.open()
    huge.new_page(width=14400, height=14400)  # 522-byte PDF that would render at 3.6 gigapixels
    with pytest.raises(DocumentRejected) as rejected:
        validate_upload(huge.tobytes(), 200)
    assert rejected.value.code == "page_too_large"

    a4 = (595, 842)
    assert render_dpi(*a4) == 300  # normal pages keep full OCR resolution
    for width, height in (a4, (3370, 4768), (5000, 5000)):
        dpi = render_dpi(width, height)
        assert (width / 72 * dpi) * (height / 72 * dpi) <= MAX_IMAGE_PIXELS


def test_oversized_bodies_are_refused_before_authentication(api_client):
    from fastapi.testclient import TestClient

    from app.main import create_app

    anonymous = TestClient(create_app(api_client.app.state.settings), base_url="https://testserver",
                           client=("127.0.9.1", 50000))
    url = "/api/v1/lawyer/cases/00000000-0000-0000-0000-000000000000/documents"
    with anonymous:
        declared = anonymous.post(url, headers={**ORIGIN, "Content-Type": "application/octet-stream"},
                                  content=b"0" * (22 * 1024 * 1024))
        assert declared.status_code == 413  # not 401: the body is refused before auth runs
        assert declared.headers["content-type"] == "application/problem+json"

        def chunks():  # no Content-Length: counted while streaming
            for _ in range(30):
                yield b"0" * (1024 * 1024)

        # Multipart is what FastAPI actually reads and spools before auth; non-multipart
        # bodies are never read on this route.
        streamed = anonymous.post(url, headers={**ORIGIN, "Content-Type": "multipart/form-data; boundary=x"},
                                  content=chunks())
        assert streamed.status_code == 413

        json_route = anonymous.post("/api/v1/auth/login", headers=ORIGIN, content=b"{" + b" " * (3 * 1024 * 1024))
        assert json_route.status_code == 413  # 2 MB default for other routes
        assert anonymous.post(url, headers=ORIGIN, files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")}
                              ).status_code == 401  # small bodies still reach auth


def test_ocr_resolution_is_capped_by_ocr_dpi():
    from app.documents.extraction import A4_AREA_IN2, ocr_size, render_dpi

    assert render_dpi(595, 842, 200) == 200
    assert ocr_size(1000, 1000, 200) == (1000, 1000)  # small photos untouched
    width, height = ocr_size(4000, 6000, 200)  # 24 MP phone photo
    assert width * height <= A4_AREA_IN2 * 200 * 200
    assert abs(width / height - 4000 / 6000) < 0.01
