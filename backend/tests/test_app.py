import json
import logging
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_user_session
from app.auth.schemas import CurrentUser
from app.config import Settings
from app.logging_config import StructuredJSONFormatter
from app.main import create_app


def test_health_endpoint_returns_minimal_status() -> None:
    client = TestClient(create_app(Settings(app_env="test")))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_endpoint_reports_database_health(api_client) -> None:
    response = api_client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "ok",
        "redis": "not_configured",
        "object_storage": "not_configured",
    }


def test_request_id_is_generated_and_valid_inbound_id_is_preserved() -> None:
    client = TestClient(create_app(Settings(app_env="test")))

    generated = client.get("/health").headers["x-request-id"]
    preserved = client.get(
        "/health",
        headers={"X-Request-ID": "8ae8a817-7c5e-47af-938f-5d5644fdc75c"},
    ).headers["x-request-id"]
    replaced = client.get(
        "/health",
        headers={"X-Request-ID": "not-a-uuid"},
    ).headers["x-request-id"]

    UUID(generated)
    assert preserved == "8ae8a817-7c5e-47af-938f-5d5644fdc75c"
    assert replaced != "not-a-uuid"
    UUID(replaced)


def test_http_errors_use_problem_json_with_request_id() -> None:
    client = TestClient(create_app(Settings(app_env="test")))

    response = client.get("/missing/private-document-text")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["status"] == 404
    assert problem["title"] == "Not Found"
    assert problem["request_id"] == response.headers["x-request-id"]
    assert problem["instance"] == f"urn:uuid:{problem['request_id']}"
    assert problem["detail"] == "Not Found"
    assert "private-document-text" not in response.text
    assert {"type", "detail", "instance"} <= problem.keys()


def test_http_problem_preserves_safe_domain_error_detail() -> None:
    app = create_app(Settings(app_env="test"))

    @app.get("/test/domain-error")
    def raise_domain_error() -> None:
        raise HTTPException(
            status_code=409,
            detail="Organization selection is required.",
        )

    response = TestClient(app).get("/test/domain-error")

    assert response.status_code == 409
    assert response.json()["detail"] == "Organization selection is required."


def test_validation_error_does_not_echo_submitted_text() -> None:
    app = create_app(Settings(app_env="test"))

    class NumericPayload(BaseModel):
        value: int

    @app.post("/test/validation")
    def validate_payload(payload: NumericPayload) -> NumericPayload:
        return payload

    client = TestClient(app)
    response = client.post(
        "/test/validation",
        json={"value": "private document text"},
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "private document text" not in response.text
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_unexpected_error_does_not_expose_exception_text(caplog) -> None:
    app = create_app(Settings(app_env="test"))

    @app.get("/test/unexpected")
    def raise_unexpected_error() -> None:
        raise RuntimeError("private document text and token")

    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR):
        response = client.get("/test/unexpected")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "private document text and token" not in response.text
    assert "private document text and token" not in caplog.text
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_structured_formatter_omits_raw_log_message() -> None:
    record = logging.LogRecord(
        "app",
        logging.INFO,
        __file__,
        1,
        "token=%s",
        ("private-token",),
        None,
    )
    record.event = "test.event"

    formatted = StructuredJSONFormatter().format(record)
    payload = json.loads(formatted)

    assert payload["event"] == "test.event"
    assert "private-token" not in formatted


def test_settings_load_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "Test API")
    monkeypatch.setenv("APP_ENV", "test")

    settings = Settings()

    assert settings.app_name == "Test API"
    assert settings.app_env == "test"


def test_docs_render_health_response_and_problem_content_type() -> None:
    client = TestClient(create_app(Settings(app_env="test")))

    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    health = client.get("/openapi.json").json()["paths"]["/health"]["get"]
    assert health["summary"]
    assert health["description"]
    assert (
        "application/problem+json"
        in health["responses"]["500"]["content"]
    )


def test_domain_openapi_operations_include_summaries_and_problem_responses() -> None:
    client = TestClient(create_app(Settings(app_env="test")))
    schema = client.get("/openapi.json").json()

    operations = (
        ("/api/v1/clients", "get", "200"),
        ("/api/v1/clients", "post", "201"),
        ("/api/v1/clients/{client_id}", "get", "200"),
        ("/api/v1/clients/{client_id}", "patch", "200"),
        ("/api/v1/cases", "get", "200"),
        ("/api/v1/cases", "post", "201"),
        ("/api/v1/cases/{case_id}", "get", "200"),
        ("/api/v1/cases/{case_id}", "patch", "200"),
    )
    for path, method, success_status in operations:
        operation = schema["paths"][path][method]
        assert operation["summary"]
        assert operation["description"]
        assert "application/json" in operation["responses"][success_status]["content"]
        assert (
            "application/problem+json"
            in operation["responses"]["401"]["content"]
        )

    case_parameters = schema["paths"]["/api/v1/cases/{case_id}"]["get"][
        "parameters"
    ]
    assert next(item for item in case_parameters if item["name"] == "case_id")[
        "description"
    ]


def test_client_role_is_blocked_from_lawyer_endpoints() -> None:
    app = create_app(Settings(app_env="test"))
    client_user = CurrentUser(
        id=uuid4(),
        email="client@example.com",
        role="client",
        full_name="Sample Client",
        preferred_language="en",
        session_id=uuid4(),
    )

    async def unused_session() -> AsyncIterator[AsyncSession]:
        yield AsyncMock(spec=AsyncSession)

    app.dependency_overrides[get_current_user] = lambda: client_user
    app.dependency_overrides[get_user_session] = unused_session
    client = TestClient(app)

    for path in ("/api/v1/cases", "/api/v1/clients"):
        response = client.get(path)
        assert response.status_code == 403
        assert response.headers["content-type"].startswith(
            "application/problem+json"
        )
