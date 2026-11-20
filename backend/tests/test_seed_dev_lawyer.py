"""Local dev lawyer seeding. Runs against legal_copilot_test only. SAMPLE_DATA_NOT_REAL_LAW."""

import asyncio
import os
import secrets

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth.schemas import RegisterRequest
from app.rag.ingest.repository import create_ingest_engine
from app.seed_dev_lawyer import check_local, seed_lawyer


def test_check_local_refuses_remote_and_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    with pytest.raises(SystemExit):
        check_local("postgresql+asyncpg://app_user:x@db.example.com:5432/legal_copilot")
    with pytest.raises(SystemExit):
        check_local(None)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(SystemExit):
        check_local("postgresql+asyncpg://app_user:x@localhost:5432/legal_copilot")


def test_seeded_lawyer_is_an_eligible_reviewer(local_app_user_database_url):
    ingest_url = os.getenv("LEGAL_INGEST_TEST_DATABASE_URL")
    if not ingest_url or not ingest_url.endswith("/legal_copilot_test"):
        pytest.skip("LEGAL_INGEST_TEST_DATABASE_URL must point at legal_copilot_test")
    if not local_app_user_database_url.endswith("/legal_copilot_test"):
        pytest.skip("TEST_DATABASE_URL must point at legal_copilot_test")

    email = f"seed-{secrets.token_hex(6)}@example.com"
    request = RegisterRequest(
        email=email, password=secrets.token_urlsafe(16), full_name="SAMPLE_DATA_NOT_REAL_LAW Dev Lawyer"
    )
    user = asyncio.run(seed_lawyer(local_app_user_database_url, request))
    assert user.role == "lawyer" and user.email == email

    async def reviewer_id():
        engine = create_ingest_engine(ingest_url)
        try:
            async with engine.connect() as conn:
                return await conn.scalar(text("SELECT app.find_legal_reviewer(:e)"), {"e": email})
        finally:
            await engine.dispose()

    assert asyncio.run(reviewer_id()) == user.id
    with pytest.raises(IntegrityError):
        asyncio.run(seed_lawyer(local_app_user_database_url, request))
