import os
import secrets
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from app.config import Settings
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_ORIGIN = "http://localhost:3000"

load_dotenv(BACKEND_DIR / ".env")


@pytest.fixture
def local_app_user_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    url = make_url(database_url)
    if (
        url.drivername != "postgresql+asyncpg"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or url.username != "app_user"
        or url.database not in {"legal_copilot", "legal_copilot_test"}
        or not url.password
    ):
        pytest.fail(
            "TEST_DATABASE_URL must target the local Compose database as app_user"
        )
    return database_url


@pytest.fixture
def api_client(local_app_user_database_url: str):
    app = create_app(
        Settings(
            app_env="test",
            database_url=local_app_user_database_url,
            app_origin=APP_ORIGIN,
            session_cookie_secure=True,
            minio_bucket=os.getenv("TEST_MINIO_BUCKET") or None,
        )
    )
    client = TestClient(
        app,
        base_url="https://testserver",
        client=(
            f"127.0.{secrets.randbelow(256)}.{secrets.randbelow(254) + 1}",
            50000,
        ),
    )
    with client:
        yield client
