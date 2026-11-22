"""Structured generation: provider chain, one repair, then the labelled mock.

Used by case analysis, strategy, and hearing reassessment. Candidates are the
providers of the chain in order (app.ai.llm.resolve_chain: e.g. gemini,
gemini_fallback, groq, openrouter), or one provider and its
GEMINI_FALLBACK_MODEL. For each candidate:
- 429 / 503, a timeout, or any other HTTP/transport error: move on to the next
  provider at once (no backoff; free tiers recover slower than a request waits);
- invalid JSON or a schema mismatch: ask the same provider once more with the
  validation errors (field paths and messages, never input values), then move on.
If no provider answers, the deterministic mock builder runs when mock is allowed;
that output is labelled origin 'ai_mock' and carries warnings saying why.

Time budget: each call has its own budget (budget_seconds; strategy and analysis
pass their own) capped by the HTTP request's deadline (REQUEST_BUDGET_SECONDS,
started by the request middleware), so the API answers before the frontend's
120 s BACKEND_TIMEOUT_MS. Each attempt's HTTP timeout is cut to the time left, and
an attempt that cannot fit is skipped.

Logged (never prompts or outputs): llm.provider_failed (provider, model, reason),
llm.answered (provider, model, attempts, schema), llm.fallback_to_mock (reasons).
"""

import asyncio
import logging
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field, is_dataclass, replace
from typing import Generic, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.llm import LLMChain, StructuredLLM, strict_json_schema

T = TypeVar("T", bound=BaseModel)

# Frontend BACKEND_TIMEOUT_MS is 120 s; keep the rest for retrieval, the database and the proxy.
REQUEST_BUDGET_SECONDS = 105.0
DEFAULT_CALL_BUDGET_SECONDS = 100.0
MIN_ATTEMPT_SECONDS = 8.0  # do not start an attempt with less time than this left
MAX_REPAIR_ERRORS = 15

logger = logging.getLogger("pokkhoai")
_request_deadline: ContextVar[float | None] = ContextVar("llm_request_deadline", default=None)
_clock: Callable[[], float] = time.monotonic


def start_request_budget(seconds: float = REQUEST_BUDGET_SECONDS) -> None:
    """Called once per HTTP request (middleware): no LLM call in it may run past this deadline."""
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


def candidates(llm: StructuredLLM | LLMChain) -> list[StructuredLLM]:
    if isinstance(llm, LLMChain):
        return list(llm.providers)
    fallback = getattr(llm, "fallback_model", None)
    if fallback and fallback != llm.model and is_dataclass(llm):
        return [llm, replace(llm, model=fallback, fallback_model=None)]
    return [llm]


def _bounded(llm: StructuredLLM, remaining: float) -> StructuredLLM:
    """The same provider with its HTTP timeout cut to the time left in the budget."""
    timeout = getattr(llm, "timeout", None)
    if is_dataclass(llm) and timeout is not None and timeout > remaining:
        return replace(llm, timeout=remaining)
    return llm


def _error_reason(error: Exception) -> str:
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    status = getattr(getattr(error, "response", None), "status_code", None)
    if status is not None:
        return f"http_{status}"
    if isinstance(error, httpx.HTTPError):
        return f"transport_{type(error).__name__}"
    if isinstance(error, ValidationError) and any(e["type"] != "json_invalid" for e in error.errors()):
        return "schema_validation"
    return "invalid_json"


def validation_summary(error: Exception) -> str:
    """What was wrong, by field path; no input values (they may hold case text)."""
    if isinstance(error, ValidationError):
        lines = [f"- {'.'.join(str(p) for p in e['loc']) or '(root)'}: {e['msg']}"
                 for e in error.errors(include_input=False, include_url=False)[:MAX_REPAIR_ERRORS]]
        more = error.error_count() - len(lines)
        return "\n".join(lines + ([f"- ... and {more} more"] if more > 0 else []))
    return "- The answer was not valid JSON."


def repair_prompt(user: str, raw: str, error: Exception) -> str:
    return (f"{user}\n\n<previous_answer>\n{raw[:60000]}\n</previous_answer>\n"
            "<validation_errors>\n" + validation_summary(error) + "\n</validation_errors>\n"
            "Your previous answer did not match the required JSON schema. Return the complete corrected "
            "JSON object only, fixing every listed error and keeping everything else the same.")


@dataclass
class _Run:
    attempts: int = 0
    warnings: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def _failed(state: _Run, llm: StructuredLLM, reason: str) -> None:
    state.reasons.append(f"{llm.provider}:{reason}")
    state.warnings.append(f"provider_error:{reason}@{llm.provider}/{llm.model}")
    logger.warning("llm.provider_failed", extra={"event": "llm.provider_failed", "provider": llm.provider,
                                                  "model": llm.model, "reason": reason})


async def _try(llm: StructuredLLM, model_cls: type[T], system: str, user: str, schema: dict,
               deadline: float, state: _Run) -> T | None:
    prompt = user
    for attempt in range(2):  # the answer, then at most one repair
        remaining = deadline - _clock()
        if remaining < MIN_ATTEMPT_SECONDS:
            _failed(state, llm, "deadline")
            return None
        state.attempts += 1
        raw = ""
        try:
            raw = await asyncio.to_thread(_bounded(llm, remaining).complete_json, system, prompt,
                                          model_cls.__name__, schema)
            return model_cls.model_validate_json(raw)
        except httpx.HTTPError as error:
            _failed(state, llm, _error_reason(error))
            return None  # 429/503/timeouts: the next provider, at once
        except (ValidationError, ValueError) as error:
            reason = _error_reason(error)
            if attempt == 1 or not raw:
                _failed(state, llm, reason + ("_after_repair" if attempt else ""))
                return None
            state.warnings.append(f"repair_requested:{reason}@{llm.provider}/{llm.model}")
            prompt = repair_prompt(user, raw, error)
    return None


async def generate_structured(
    llm: StructuredLLM | LLMChain | None,
    model_cls: type[T],
    system: str,
    user: str,
    mock_builder: Callable[[], T],
    allow_mock: bool,
    budget_seconds: float = DEFAULT_CALL_BUDGET_SECONDS,
) -> Generated[T]:
    state = _Run()
    if isinstance(llm, LLMChain):
        state.warnings.extend(f"provider_skipped:{s}" for s in llm.skipped)
    if llm is not None:
        schema = strict_json_schema(model_cls.model_json_schema())
        own = _clock() + budget_seconds
        request = _request_deadline.get()
        deadline = min(own, request) if request is not None else own
        for candidate in candidates(llm):
            value = await _try(candidate, model_cls, system, user, schema, deadline, state)
            if value is not None:
                logger.info("llm.answered", extra={"event": "llm.answered", "provider": candidate.provider,
                                                    "model": candidate.model, "attempts": state.attempts,
                                                    "schema": model_cls.__name__})
                return Generated(value, "ai", candidate.provider, candidate.model, state.attempts, state.warnings)
            if deadline - _clock() < MIN_ATTEMPT_SECONDS:
                state.warnings.append("llm_time_budget_exhausted")
                break
    if not allow_mock:
        raise GenerationFailed("Model output unavailable or invalid and the mock is not allowed here")
    state.warnings.append("fallback_to_mock")
    logger.warning("llm.fallback_to_mock", extra={
        "event": "llm.fallback_to_mock", "schema": model_cls.__name__, "attempts": state.attempts,
        "reason": ",".join(state.reasons) or ("no_provider_configured" if llm is None else "deadline")})
    return Generated(model_cls.model_validate(mock_builder().model_dump()), "ai_mock", "mock", None,
                     state.attempts, state.warnings)

