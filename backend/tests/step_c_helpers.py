"""Shared helpers for Step C tests. All documents are SAMPLE_DATA_NOT_REAL_LAW."""

import asyncio
import io
import secrets
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine, user_transaction
from app.main import create_app
from tests.test_phase2_exit import create_case, register_login

ORIGIN = {"Origin": "http://localhost:3000"}
BN_FONT = "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf"
SAMPLE = "SAMPLE_DATA_NOT_REAL_LAW"


def sample_pdf(lines_en: list[str], lines_bn: list[str] = ()) -> bytes:
    """A one-page PDF with a text layer; a random marker keeps each file's hash unique."""
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_font(fontname="bn", fontfile=BN_FONT)
    y = 60
    for line in [f"{SAMPLE} marker {secrets.token_hex(6)}.", *lines_en]:
        page.insert_text((40, y), line, fontsize=9)
        y += 18
    for line in lines_bn:
        page.insert_text((40, y), line, fontname="bn", fontsize=11)
        y += 22
    return document.tobytes()


def sample_png(text_line: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1400, 220), "white")
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    ImageDraw.Draw(image).text((30, 80), f"{text_line} {secrets.token_hex(3)}", fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def new_client(app_client: TestClient, octet: int) -> TestClient:
    return TestClient(create_app(app_client.app.state.settings), base_url="https://testserver")


def lawyer_with_case(client: TestClient, label: str) -> tuple[UUID, str]:
    user_id = UUID(register_login(client, label))
    return user_id, create_case(client, f"SAMPLE-{label}-{secrets.token_hex(3)}")


def upload(client: TestClient, case_id: str, data: bytes, filename: str = "sample.pdf"):
    return client.post(f"/api/v1/lawyer/cases/{case_id}/documents", headers=ORIGIN,
                       files={"file": (filename, data, "application/octet-stream")})


def sql_as(database_url: str, user_id: UUID, query: str, **params):
    async def run():
        engine = create_database_engine(database_url)
        try:
            async with user_transaction(async_sessionmaker(engine), user_id) as session:
                return (await session.execute(text(query), params)).all()
        finally:
            await engine.dispose()

    return asyncio.run(run())
