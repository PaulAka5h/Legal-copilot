from http import HTTPStatus
import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.rag.search.errors import EmbeddingModelMismatch, ProviderNotConfigured

PROBLEM_MEDIA_TYPE = "application/problem+json"


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    request_id: str


def problem_response(
    request: Request,
    status_code: int,
    title: str,
    detail: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    if request_id is None:
        request_id = str(uuid4())
        request.state.request_id = request_id
    problem = Problem(
        title=title,
        status=status_code,
        detail=detail,
        instance=f"urn:uuid:{request_id}",
        request_id=request_id,
    )
    response_headers = dict(headers or {})
    response_headers["X-Request-ID"] = request_id
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(),
        media_type=PROBLEM_MEDIA_TYPE,
        headers=response_headers,
    )


def problem_responses(*status_codes: int) -> dict[int, dict[str, object]]:
    return {
        status_code: {
            "description": _http_title(status_code),
            "content": {
                PROBLEM_MEDIA_TYPE: {"schema": Problem.model_json_schema()}
            },
        }
        for status_code in status_codes
    }


def _http_title(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "HTTP Error"


def register_exception_handlers(app: FastAPI) -> None:
    logger = logging.getLogger("pokkhoai")

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        title = _http_title(exc.status_code)
        detail = (
            exc.detail
            if isinstance(exc.detail, str)
            else "The request could not be completed."
        )
        return problem_response(
            request,
            exc.status_code,
            title,
            detail,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return problem_response(
            request,
            422,
            "Unprocessable Entity",
            "Request validation failed.",
        )

    @app.exception_handler(EmbeddingModelMismatch)
    async def handle_embedding_mismatch(request: Request, exc: EmbeddingModelMismatch) -> JSONResponse:
        # Model names are configuration, not case data; the query text is never logged.
        logger.error(
            "search.embedding_model_mismatch",
            extra={
                "event": "search.embedding_model_mismatch",
                "request_id": getattr(request.state, "request_id", "unknown"),
                "query_model": f"{exc.query_model} v{exc.query_version}",
                "stored_models": [f"{m} v{v}" for m, v in exc.stored],
            },
        )
        return problem_response(request, 503, "Service Unavailable", f"EMBEDDING_MODEL_MISMATCH: {exc}")

    @app.exception_handler(ProviderNotConfigured)
    async def handle_provider_unavailable(
        request: Request, exc: ProviderNotConfigured
    ) -> JSONResponse:
        # Raised mid-request when the embedding model or API fails (e.g. hf_api down).
        logger.warning(
            "provider.unavailable",
            extra={
                "event": "provider.unavailable",
                "request_id": getattr(request.state, "request_id", "unknown"),
                "exception_type": type(exc).__name__,
            },
        )
        return problem_response(
            request,
            503,
            "Service Unavailable",
            "NOT_CONFIGURED: legal search models are not available on this server.",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "request.failed",
            extra={
                "event": "request.failed",
                "request_id": request_id,
                "exception_type": type(exc).__name__,
            },
        )
        return problem_response(
            request,
            500,
            "Internal Server Error",
            "An internal server error occurred.",
        )
