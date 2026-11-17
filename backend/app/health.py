from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.errors import Problem

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


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
