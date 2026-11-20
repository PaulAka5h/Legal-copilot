"""Structured generation with validation, one retry, and the gemini/ollama -> mock fallback.

Used by case analysis and strategy. The model's JSON is validated with Pydantic;
invalid output is retried once. A transport error, or a second invalid answer,
falls back to the deterministic mock builder when mock is allowed; that output is
labelled origin 'ai_mock' and carries a warning. Prompts and outputs are never
logged.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Generic, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.llm import StructuredLLM, strict_json_schema

T = TypeVar("T", bound=BaseModel)


class GenerationFailed(RuntimeError):
    pass


@dataclass
class Generated(Generic[T]):
    value: T
    origin: str  # ai | ai_mock
    provider: str
    model: str | None
    attempts: int
    warnings: list[str] = field(default_factory=list)


async def generate_structured(
    llm: StructuredLLM | None,
    model_cls: type[T],
    system: str,
    user: str,
    mock_builder: Callable[[], T],
    allow_mock: bool,
) -> Generated[T]:
    warnings: list[str] = []
    attempts = 0
    if llm is not None:
        schema = strict_json_schema(model_cls.model_json_schema())
        for _ in range(2):
            attempts += 1
            try:
                raw = await asyncio.to_thread(llm.complete_json, system, user, model_cls.__name__, schema)
                return Generated(model_cls.model_validate_json(raw), "ai", llm.provider, llm.model, attempts, warnings)
            except httpx.HTTPError as error:
                warnings.append(f"provider_error:{type(error).__name__}")
                break
            except (ValidationError, ValueError):
                warnings.append("invalid_model_output")
                continue
    if not allow_mock:
        raise GenerationFailed("Model output unavailable or invalid and the mock is not allowed here")
    if llm is not None:
        warnings.append("fallback_to_mock")
    return Generated(model_cls.model_validate(mock_builder().model_dump()), "ai_mock", "mock", None, attempts, warnings)
