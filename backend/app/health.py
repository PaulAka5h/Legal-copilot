from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth.dependencies import SessionFactoryDep

from app.errors import Problem

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ready"]
    database: Literal["ok"] = Field(description="PostgreSQL accepted a read query.")
    redis: Literal["not_configured"] = Field(
        description="Redis is not wired into the backend yet; not a failure."
    )
    object_storage: Literal["not_configured"] = Field(
        description="MinIO/S3 is not wired into the backend yet; not a failure."
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API liveness",
    description="Confirms that the API process is running without exposing service data.",
    responses={
        500: {
            "model": Problem,
            "description": "Internal server error in problem detail format.",
            "content": {"application/problem+json": {}},
        }
    },
)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadyResponse,
    summary="Check database readiness",
    description=(
        "Returns ready only when the API database accepts a read query. "
        "Services not yet wired into the backend are reported as not_configured."
    ),
    responses={
        503: {
            "model": Problem,
            "description": "Database unavailable.",
            "content": {"application/problem+json": {}},
        }
    },
)
async def ready(
    request: Request,
    session_factory: SessionFactoryDep,
) -> ReadyResponse:
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not ready.",
        ) from exc
    return ReadyResponse(
        status="ready",
        database="ok",
        redis="not_configured",
        object_storage="not_configured",
    )
