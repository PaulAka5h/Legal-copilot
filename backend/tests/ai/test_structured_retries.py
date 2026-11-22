"""Structured generation: no backoff (429/503/timeouts move on at once), one repair on invalid
output, GEMINI_FALLBACK_MODEL, labelled mock, per-call budget within the request deadline.

Fake clock: nothing waits, nothing reaches the network.
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
from app.ai.structured import generate_structured, start_request_budget
from app.case_analysis.schemas import AnalysisDraft
from app.config import Settings
from app.main import create_app

VALID = json.dumps({"findings": [], "missing_information": ["SAMPLE_DATA_NOT_REAL_LAW"]})
REQUEST = httpx.Request("POST", "https://generativelanguage.googleapis.com/x")
PRIMARY, FALLBACK = "gemini-3.5-flash-lite", "gemini-2.5-flash"


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
    prompts: list = field(default_factory=list, repr=False)

    def complete_json(self, system, user, name, schema):
        self.calls.append((self.model, self.timeout))
        self.prompts.append(user)
        self.clock[0] += self.cost
        outcome = self.script[self.model].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def fake_time(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(structured, "_clock", lambda: now[0])
    token = structured._request_deadline.set(None)
    yield now
    structured._request_deadline.reset(token)


def mock():
    return AnalysisDraft(findings=[], missing_information=["mock"])


def run(llm, **kwargs):
    return asyncio.run(generate_structured(llm, AnalysisDraft, "s", "u", mock, True, **kwargs))


def llm(fake_time, script, **kwargs):
    return FakeGemini(PRIMARY, script=script, calls=[], clock=fake_time, **kwargs)


@pytest.mark.parametrize("error", [status(429), status(503), httpx.ReadTimeout("slow", request=REQUEST),
                                   status(400), httpx.ConnectError("down", request=REQUEST)])
def test_errors_move_to_the_fallback_model_at_once(fake_time, error):
    model = llm(fake_time, {PRIMARY: [error], FALLBACK: [VALID]}, fallback_model=FALLBACK)
    out = run(model)
    assert (out.origin, out.provider, out.model, out.attempts) == ("ai", "gemini", FALLBACK, 2)
    assert [m for m, _ in model.calls] == [PRIMARY, FALLBACK]  # no retry of the primary
    assert fake_time[0] == 0  # no backoff sleeps


def test_invalid_output_is_repaired_once_with_the_validation_errors(fake_time):
    model = llm(fake_time, {PRIMARY: ['{"findings": "x"}', VALID]})
    out = run(model)
    assert (out.origin, out.model, out.attempts) == ("ai", PRIMARY, 2)
    assert "repair_requested:schema_validation@gemini/" + PRIMARY in out.warnings
    repair = model.prompts[1]
    assert "<validation_errors>" in repair and "- findings: Input should be a valid array" in repair and "- missing_information: Field required" in repair
    assert '"findings": "x"' in repair  # the previous answer goes back for correction


def test_invalid_after_repair_moves_on(fake_time):
    model = llm(fake_time, {PRIMARY: ["not json", "{}"], FALLBACK: [VALID]}, fallback_model=FALLBACK)
    out = run(model)
    assert out.model == FALLBACK and out.attempts == 3
    assert "provider_error:schema_validation_after_repair@gemini/" + PRIMARY in out.warnings


def test_both_models_down_falls_back_to_labelled_mock(fake_time):
    model = llm(fake_time, {PRIMARY: [status(503)], FALLBACK: [status(429)]}, fallback_model=FALLBACK)
    out = run(model)
    assert out.origin == "ai_mock" and out.model is None and out.attempts == 2
    assert "fallback_to_mock" in out.warnings and "provider_error:http_429@gemini/" + FALLBACK in out.warnings


def test_own_budget_and_request_deadline_cut_timeouts(fake_time):
    start_request_budget(25)  # each call takes 10 s on the fake clock
    model = llm(fake_time, {PRIMARY: [status(503)], FALLBACK: [status(503)]}, fallback_model=FALLBACK, cost=10.0)
    out = run(model, budget_seconds=90)
    assert [t for _, t in model.calls] == [25.0, 15.0]  # HTTP timeout = time left, not 120 s
    assert out.origin == "ai_mock" and fake_time[0] <= 25
    fake_time[0] = 0
    start_request_budget(105)
    short = llm(fake_time, {PRIMARY: [VALID]})
    run(short, budget_seconds=30)  # the call's own budget is shorter than the request's
    assert short.calls[0][1] == 30.0


def test_attempt_skipped_when_too_little_time_is_left(fake_time):
    start_request_budget(structured.MIN_ATTEMPT_SECONDS - 1)
    model = llm(fake_time, {PRIMARY: [VALID]})
    out = run(model)
    assert out.origin == "ai_mock" and model.calls == []
    assert "provider_error:deadline@gemini/" + PRIMARY in out.warnings and "llm_time_budget_exhausted" in out.warnings


def test_answered_and_fallback_are_logged_with_reasons_and_no_prompt(fake_time):
    records = []

    class Grab(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = Grab()
    logging.getLogger("pokkhoai").addHandler(handler)
    try:
        run(llm(fake_time, {PRIMARY: [status(429)], FALLBACK: [VALID]}, fallback_model=FALLBACK))
        run(llm(fake_time, {PRIMARY: [httpx.ReadTimeout("t", request=REQUEST)]}))
    finally:
        logging.getLogger("pokkhoai").removeHandler(handler)
    from app.logging_config import StructuredJSONFormatter

    lines = [json.loads(StructuredJSONFormatter().format(r)) for r in records]
    answered = [line for line in lines if line["event"] == "llm.answered"]
    assert [(a["provider"], a["model"], a["attempts"], a["schema"]) for a in answered] == [
        ("gemini", FALLBACK, 2, "AnalysisDraft")]
    failed = [line for line in lines if line["event"] == "llm.provider_failed"]
    assert {(f["model"], f["reason"]) for f in failed} == {(PRIMARY, "http_429"), (PRIMARY, "timeout")}
    fallback = [line for line in lines if line["event"] == "llm.fallback_to_mock"]
    assert fallback[0]["reason"] == "gemini:timeout"
    assert all("u" != v for line in lines for v in line.values())  # the prompt text is never logged


def test_fallback_model_comes_from_settings():
    settings = Settings(_env_file=None, app_env="development", llm_provider="gemini",
                        llm_approved_providers="gemini,mock", gemini_api_key="gm-secret-test-key",
                        gemini_model=PRIMARY, gemini_fallback_model=FALLBACK)
    configured = resolve_provider(settings)
    assert isinstance(configured, GeminiLLM) and configured.fallback_model == FALLBACK
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
