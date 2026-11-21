"""LLM retries (429/503: 2 s, 5 s, 10 s), GEMINI_FALLBACK_MODEL, labelled mock, request time budget.

Fake clock and sleep: nothing waits, nothing reaches the network.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai import structured
from app.ai.llm import GeminiLLM, resolve_provider
from app.ai.structured import RETRY_DELAYS, generate_structured, start_request_budget
from app.case_analysis.schemas import AnalysisDraft
from app.config import Settings
from app.main import create_app

VALID = json.dumps({"findings": [], "missing_information": ["SAMPLE_DATA_NOT_REAL_LAW"]})
REQUEST = httpx.Request("POST", "https://generativelanguage.googleapis.com/x")


def status(code: int) -> httpx.HTTPStatusError:
    return httpx.HTTPStatusError(str(code), request=REQUEST, response=httpx.Response(code, request=REQUEST))


@dataclass
class FakeGemini:
    """Dataclass like GeminiLLM, so the fallback model and the timeout cut apply."""

    model: str
    script: dict = field(repr=False)  # model -> list of outcomes (str answer or exception)
    calls: list = field(default_factory=list, repr=False)
    timeout: float = 120.0
    fallback_model: str | None = None
    provider: str = "gemini"
    cost: float = 0.0  # seconds each call takes on the fake clock
    clock: list = field(default_factory=lambda: [0.0], repr=False)

    def complete_json(self, system, user, name, schema):
        self.calls.append((self.model, self.timeout))
        self.clock[0] += self.cost
        outcome = self.script[self.model].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def fake_time(monkeypatch):
    now, sleeps = [0.0], []

    async def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(structured, "_clock", lambda: now[0])
    monkeypatch.setattr(structured, "_sleep", sleep)
    token = structured._request_deadline.set(None)
    yield now, sleeps
    structured._request_deadline.reset(token)


def mock():
    return AnalysisDraft(findings=[], missing_information=["mock"])


def run(llm):
    return asyncio.run(generate_structured(llm, AnalysisDraft, "s", "u", mock, True))


def llm(fake_time, script, **kwargs):
    now, _ = fake_time
    calls = []
    shared = {"script": script, "calls": calls, "clock": now}
    return FakeGemini("gemini-3.5-flash-lite", **shared, **kwargs)


def test_503_is_retried_with_backoff_and_the_primary_answers(fake_time):
    _, sleeps = fake_time
    model = llm(fake_time, {"gemini-3.5-flash-lite": [status(503), status(503), VALID]})
    out = run(model)
    assert (out.origin, out.model, out.attempts) == ("ai", "gemini-3.5-flash-lite", 3)
    assert sleeps == [2.0, 5.0]


def test_429_three_retries_then_fallback_model_answers(fake_time):
    _, sleeps = fake_time
    model = llm(fake_time, {"gemini-3.5-flash-lite": [status(429)] * 4, "gemini-2.5-flash": [VALID]},
                fallback_model="gemini-2.5-flash")
    out = run(model)
    assert sleeps == list(RETRY_DELAYS) == [2.0, 5.0, 10.0]
    assert (out.origin, out.provider, out.model, out.attempts) == ("ai", "gemini", "gemini-2.5-flash", 5)
    assert "fallback_model:gemini-2.5-flash" in out.warnings
    assert "provider_error:HTTPStatusError:429@gemini-3.5-flash-lite" in out.warnings
    assert [m for m, _ in model.calls] == ["gemini-3.5-flash-lite"] * 4 + ["gemini-2.5-flash"]


def test_both_models_overloaded_falls_back_to_labelled_mock(fake_time):
    _, sleeps = fake_time
    model = llm(fake_time, {"gemini-3.5-flash-lite": [status(503)] * 4, "gemini-2.5-flash": [status(503)] * 4},
                fallback_model="gemini-2.5-flash")
    out = run(model)
    assert out.origin == "ai_mock" and out.model is None and out.attempts == 8
    assert "fallback_to_mock" in out.warnings and "provider_error:HTTPStatusError:503@gemini-2.5-flash" in out.warnings
    assert sleeps == [2.0, 5.0, 10.0] * 2


@pytest.mark.parametrize("error", [status(400), status(404), httpx.ConnectError("down", request=REQUEST)])
def test_other_errors_skip_retries_and_go_to_the_fallback_model(fake_time, error):
    _, sleeps = fake_time
    model = llm(fake_time, {"gemini-3.5-flash-lite": [error], "gemini-2.5-flash": [VALID]},
                fallback_model="gemini-2.5-flash")
    out = run(model)
    assert out.model == "gemini-2.5-flash" and sleeps == []


def test_invalid_output_twice_moves_to_the_fallback_model(fake_time):
    model = llm(fake_time, {"gemini-3.5-flash-lite": ["not json", "{}"], "gemini-2.5-flash": [VALID]},
                fallback_model="gemini-2.5-flash")
    out = run(model)
    assert out.model == "gemini-2.5-flash" and out.warnings.count("invalid_model_output@gemini-3.5-flash-lite") == 2


def test_without_fallback_model_goes_to_mock(fake_time):
    out = run(llm(fake_time, {"gemini-3.5-flash-lite": [status(503)] * 4}))
    assert out.origin == "ai_mock" and not any(w.startswith("fallback_model") for w in out.warnings)


def test_request_budget_cuts_timeouts_and_skips_retries_that_do_not_fit(fake_time):
    now, sleeps = fake_time
    start_request_budget(25)  # each call takes 10 s on the fake clock
    model = llm(fake_time, {"gemini-3.5-flash-lite": [status(503)] * 4, "gemini-2.5-flash": [VALID]},
                fallback_model="gemini-2.5-flash", cost=10.0)
    out = run(model)
    assert out.origin == "ai_mock" and "llm_time_budget_exhausted" in out.warnings
    assert now[0] <= 25  # never past the deadline
    assert sleeps == [2.0]  # the 5 s retry would not leave MIN_ATTEMPT_SECONDS
    assert [t for _, t in model.calls] == [25.0, 13.0]  # HTTP timeout = time left, not 120 s
    assert "gemini-2.5-flash" not in [m for m, _ in model.calls]


def test_two_calls_in_one_request_share_the_deadline(fake_time):
    now, _ = fake_time
    start_request_budget(100)
    first = llm(fake_time, {"gemini-3.5-flash-lite": [status(503)] * 4}, cost=20.0)
    run(first)  # 4 calls x 20 s + 17 s of backoff = 97 s, or stops earlier
    spent = now[0]
    second = llm(fake_time, {"gemini-3.5-flash-lite": [VALID]}, cost=1.0)
    out = run(second)
    assert spent <= 100 and now[0] <= 100
    assert out.origin == "ai_mock" or 100 - spent >= structured.MIN_ATTEMPT_SECONDS


def test_answering_model_is_logged(fake_time):
    records = []

    class Grab(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = Grab()
    logging.getLogger("pokkhoai").addHandler(handler)
    try:
        run(llm(fake_time, {"gemini-3.5-flash-lite": [status(429)] * 4, "gemini-2.5-flash": [VALID]},
                fallback_model="gemini-2.5-flash"))
    finally:
        logging.getLogger("pokkhoai").removeHandler(handler)
    answered = [r for r in records if getattr(r, "event", None) == "llm.answered"]
    assert [(r.provider, r.model, r.attempts) for r in answered] == [("gemini", "gemini-2.5-flash", 5)]
    from app.logging_config import StructuredJSONFormatter

    line = json.loads(StructuredJSONFormatter().format(answered[0]))
    assert line["model"] == "gemini-2.5-flash" and line["attempts"] == 5


def test_fallback_model_comes_from_settings():
    settings = Settings(_env_file=None, app_env="development", llm_provider="gemini",
                        llm_approved_providers="gemini,mock", gemini_api_key="gm-secret-test-key",
                        gemini_model="gemini-3.5-flash-lite", gemini_fallback_model="gemini-2.5-flash")
    configured = resolve_provider(settings)
    assert isinstance(configured, GeminiLLM) and configured.fallback_model == "gemini-2.5-flash"
    assert "gm-secret-test-key" not in repr(configured)


def test_every_request_starts_a_budget():
    app = create_app(Settings(_env_file=None, app_env="test"))
    seen = {}

    @app.get("/_budget")
    def budget() -> dict:
        seen["deadline"] = structured._request_deadline.get()
        return {}

    TestClient(app).get("/_budget")
    assert seen["deadline"] is not None
    assert seen["deadline"] - structured._clock() <= structured.REQUEST_BUDGET_SECONDS
