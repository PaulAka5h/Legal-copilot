"""Smoke test for the Render demo (also drives the local memory measurement).

    cd backend
    DEMO_LAWYER_PASSWORD='...' uv run python ../deploy/smoke_test.py \
        --api https://<your-service>.onrender.com --origin https://<your-app>.vercel.app

Checks, in order: /health, /health/ready, login as the demo lawyer, the synthetic
case is listed, legal search returns approved statutes (EMBEDDING_PROVIDER), case
analysis runs on one confirmed fact (Gemini or the mock fallback), and a scanned
one-page PDF is OCR'd (Tesseract ben+eng) and stored in B2. Everything it writes is
labelled SAMPLE_DATA_NOT_REAL_LAW. The password is read from the environment and
never printed. Exit code 0 only if every step passed.
"""

import argparse
import io
import os
import sys
import time

import httpx

SAMPLE = "SAMPLE_DATA_NOT_REAL_LAW"
SEARCH_QUERY = "cheque dishonoured for insufficient funds, legal notice, prosecution"
FACT = (f"{SAMPLE}: The client's cheque of BDT 1,500,000 was returned unpaid for insufficient funds "
        "and no payment was made within 30 days of the legal notice.")


def step(name: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{': ' + detail if detail else ''}", flush=True)
    return ok


def scanned_pdf() -> bytes:
    """An A4 page with no text layer (an image only), like a phone scan."""
    import pymupdf
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (2480, 3508), "white")  # A4 at 300 DPI
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 48)
    except OSError:
        font = ImageFont.load_default(size=48)
    lines = [SAMPLE, "LEGAL NOTICE", "Cheque No. 4928192 dated 10 January 2023",
             "returned unpaid for insufficient funds on 2 February 2023.",
             "Payment is demanded within thirty days of receipt."]
    for i, line in enumerate(lines):
        draw.text((200, 300 + i * 110), line, fill="black", font=font)
    jpeg = io.BytesIO()
    image.convert("L").save(jpeg, "JPEG", quality=70)  # grey JPEG, like a phone scan
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=jpeg.getvalue())
        return pdf.tobytes()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", required=True, help="Backend base URL, e.g. https://x.onrender.com")
    parser.add_argument("--origin", required=True, help="APP_ORIGIN the backend expects (the Vercel URL)")
    parser.add_argument("--email", default=os.getenv("DEMO_LAWYER_EMAIL", "demo.lawyer@example.com"))
    parser.add_argument("--skip-analysis", action="store_true")
    parser.add_argument("--skip-ocr", action="store_true")
    parser.add_argument("--timeout", type=float, default=180, help="Seconds per request (Render cold start)")
    args = parser.parse_args()
    password = os.environ.get("DEMO_LAWYER_PASSWORD")
    if not password:
        print("Set DEMO_LAWYER_PASSWORD in the environment", file=sys.stderr)
        return 2

    api = args.api.rstrip("/")
    client = httpx.Client(base_url=api, timeout=args.timeout, headers={"Origin": args.origin.rstrip("/")})
    ok = True

    r = client.get("/health")
    ok &= step("GET /health", r.status_code == 200, f"HTTP {r.status_code}")
    r = client.get("/health/ready")
    ok &= step("GET /health/ready (Neon)", r.status_code == 200, f"HTTP {r.status_code}")
    if not ok:
        return 1

    r = client.post("/api/v1/auth/login", json={"email": args.email, "password": password})
    if not step("login as demo lawyer", r.status_code == 200, f"HTTP {r.status_code}"):
        return 1

    r = client.get("/api/v1/cases")
    body = r.json() if r.status_code == 200 else {}
    cases = body.get("items", body) if isinstance(body, dict) else body
    demo = next((c for c in cases if str(c.get("title", "")).startswith(SAMPLE)), None)
    if not step("synthetic demo case listed", demo is not None, f"{len(cases)} case(s)"):
        return 1
    case = f"/api/v1/lawyer/cases/{demo['id']}"

    t = time.monotonic()
    r = client.post(f"{case}/research/search", json={"query": SEARCH_QUERY, "k": 5})
    found = r.json() if r.status_code == 200 else {}
    hits = found.get("results", [])
    ok &= step("legal search", bool(hits),
               f"HTTP {r.status_code}, {len(hits)} hits in {time.monotonic() - t:.1f}s, "
               f"embeddings {found.get('embedding_model')}"
               + (f", top: {hits[0].get('act_title')} s.{hits[0].get('section_number')} "
                  f"(cosine {hits[0].get('dense_similarity')})" if hits else "")
               + ("" if r.status_code == 200 else f", {r.text[:200]}"))

    if not args.skip_analysis:
        confirmed = client.get(f"{case}/facts/confirmed")
        if confirmed.status_code == 200 and not confirmed.json():
            r = client.post(f"{case}/facts", json={"category": "act_or_omission", "statement": FACT})
            step("enter one synthetic fact", r.status_code == 201, f"HTTP {r.status_code}")
        t = time.monotonic()
        r = client.post(f"{case}/analysis", json={})
        detail = f"HTTP {r.status_code} in {time.monotonic() - t:.1f}s"
        result = r.json() if r.status_code == 201 else {}
        if result:
            detail += (f", status {result.get('status')}, origin {result.get('origin')} ({result.get('provider')}), "
                       f"{len(result.get('findings') or [])} finding(s)")
        # The cheque-dishonour fact is squarely in the knowledge base: abstaining here
        # would mean the similarity threshold does not fit the embedding model.
        ok &= step("case analysis", result.get("status") == "succeeded", detail)

    if not args.skip_ocr:
        t = time.monotonic()
        files = {"file": ("smoke-scan.pdf", scanned_pdf(), "application/pdf")}
        r = client.post(f"{case}/documents", files=files, data={"title": f"{SAMPLE} smoke scan"})
        doc = r.json().get("document", {}) if r.status_code == 201 else {}
        ok &= step("OCR upload to B2", r.status_code == 201 and doc.get("processing_status") in {"ready", "needs_review"},
                   f"HTTP {r.status_code}, {doc.get('processing_status')}, {time.monotonic() - t:.1f}s")

    client.post("/api/v1/auth/logout")
    print("ALL PASSED" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
