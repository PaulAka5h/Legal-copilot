"""Structured generation: validation, retries, a fallback model, then the labelled mock.

Used by case analysis, strategy, and hearing reassessment. For each model in order
(the configured model, then GEMINI_FALLBACK_MODEL when set):
- 429 / 503 (rate limit, overload) are retried RETRY_DELAYS = 2 s, 5 s, 10 s apart;
- invalid JSON or a schema mismatch is asked again once;
- any other HTTP or transport error moves on to the next model at once.
If no model answers, the deterministic mock builder runs when mock is allowed; that
output is labelled origin 'ai_mock' and carries warnings saying why.

Time budget: every LLM call in one HTTP request shares a deadline
(REQUEST_BUDGET_SECONDS, started by the request middleware; a hearing update makes
two calls), so the API answers before the frontend's 120 s BACKEND_TIMEOUT_MS. Each
attempt's HTTP timeout is cut to the time left, and a retry or fallback that cannot
fit is skipped. Outside a request (eval, scripts) each call gets its own budget.

Logged: which provider/model answered and after how many attempts (event
llm.answered), or llm.fallback_to_mock. Prompts and outputs are never logged.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field, is_dataclass, replace
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.llm import StructuredLLM, strict_json_schema

T = TypeVar("T", bound=BaseModel)

RETRY_STATUSES = frozenset({429, 503})
RETRY_DELAYS = (2.0, 5.0, 10.0)
# Frontend BACKEND_TIMEOUT_MS is 120 s; keep 20 s for retrieval, the database and the proxy.
REQUEST_BUDGET_SECONDS = 100.0
MIN_ATTEMPT_SECONDS = 8.0  # do not start an attempt with less time than this left

logger = logging.getLogger("pokkhoai")
_request_deadline: ContextVar[float | None] = ContextVar("llm_request_deadline", default=None)
_clock: Callable[[], float] = time.monotonic
_sleep: Callable[[float], Any] = asyncio.sleep


def start_request_budget(seconds: float = REQUEST_BUDGET_SECONDS) -> None:
    """Called once per HTTP request (middleware): all LLM calls in it share this deadline."""
    _request_deadline.set(_clock() + seconds)


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


def _models(llm: StructuredLLM) -> list[StructuredLLM]:
    fallback = getattr(llm, "fallback_model", None)
    if fallback and fallback != llm.model and is_dataclass(llm):
        return [llm, replace(llm, model=fallback, fallback_model=None)]
    return [llm]


def _bounded(llm: StructuredLLM, remaining: float) -> StructuredLLM:
    """The same model with its HTTP timeout cut to the time left in the budget."""
    timeout = getattr(llm, "timeout", None)
    if is_dataclass(llm) and timeout is not None and timeout > remaining:
        return replace(llm, timeout=remaining)
    return llm


class _Out:
    """Mutable run state shared across models."""

    def __init__(self) -> None:
        self.attempts = 0
        self.warnings: list[str] = []
        self.out_of_time = False


async def _try_model(llm: StructuredLLM, model_cls: type[T], system: str, user: str, schema: dict,
                     deadline: float, state: _Out) -> T | None:
    retries = invalid = 0
    while True:
        remaining = deadline - _clock()
        if remaining < MIN_ATTEMPT_SECONDS:
            state.out_of_time = True
            return None
        state.attempts += 1
        try:
            raw = await asyncio.to_thread(_bounded(llm, remaining).complete_json, system, user,
                                          model_cls.__name__, schema)
            return model_cls.model_validate_json(raw)
        except httpx.HTTPError as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            state.warnings.append(f"provider_error:{type(error).__name__}"
                                  + (f":{status}" if status else "") + f"@{llm.model}")
            if status not in RETRY_STATUSES or retries == len(RETRY_DELAYS):
                return None
            delay = RETRY_DELAYS[retries]
            retries += 1
            if _clock() + delay + MIN_ATTEMPT_SECONDS > deadline:
                state.out_of_time = True
                return None
            await _sleep(delay)
        except (ValidationError, ValueError):
            state.warnings.append(f"invalid_model_output@{llm.model}")
            invalid += 1
            if invalid == 2:
                return None


async def generate_structured(
    llm: StructuredLLM | None,
    model_cls: type[T],
    system: str,
    user: str,
    mock_builder: Callable[[], T],
    allow_mock: bool,
) -> Generated[T]:
    state = _Out()
    if llm is not None:
        schema = strict_json_schema(model_cls.model_json_schema())
        deadline = _request_deadline.get() or (_clock() + REQUEST_BUDGET_SECONDS)
        for index, candidate in enumerate(_models(llm)):
            if index:
                state.warnings.append(f"fallback_model:{candidate.model}")
            value = await _try_model(candidate, model_cls, system, user, schema, deadline, state)
            if value is not None:
                logger.info("llm.answered", extra={"event": "llm.answered", "provider": candidate.provider,
                                                    "model": candidate.model, "attempts": state.attempts})
                return Generated(value, "ai", candidate.provider, candidate.model, state.attempts, state.warnings)
            if state.out_of_time:
                state.warnings.append("llm_time_budget_exhausted")
                break
    if not allow_mock:
        raise GenerationFailed("Model output unavailable or invalid and the mock is not allowed here")
    if llm is not None:
        state.warnings.append("fallback_to_mock")
        logger.warning("llm.fallback_to_mock", extra={"event": "llm.fallback_to_mock", "provider": llm.provider,
                                                       "model": llm.model, "attempts": state.attempts})
    return Generated(model_cls.model_validate(mock_builder().model_dump()), "ai_mock", "mock", None,
                     state.attempts, state.warnings)
