"""LLM provider chain: Gemini, Groq, OpenRouter (mocked HTTP), order, skips, failover."""

import asyncio
import json

import httpx
import pytest

from app.ai import structured
from app.ai.llm import GeminiLLM, LLMChain, LLMNotConfigured, OpenAICompatibleLLM, resolve_chain
from app.ai.structured import generate_structured
from app.case_analysis.schemas import AnalysisDraft
from app.config import Settings

VALID = {"findings": [], "missing_information": ["SAMPLE_DATA_NOT_REAL_LAW"]}
PROMPT = "SAMPLE_DATA_NOT_REAL_LAW prompt text that must never be logged"
ALL = "gemini,gemini_fallback,groq,openrouter,mock"
OPENROUTER_MODEL = "nvidia/nemotron-3.5-super-vl:free"
HOSTS = {"generativelanguage.googleapis.com": "gemini", "api.groq.com": "groq", "openrouter.ai": "openrouter"}


def settings(**overrides) -> Settings:
    values = dict(_env_file=None, app_env="development", llm_fallback_chain=ALL,
                  llm_approved_providers="gemini,groq,openrouter,mock",
                  gemini_api_key="gm-key", gemini_model="gemini-a", gemini_fallback_model="gemini-b",
                  groq_api_key="gq-key", groq_model="openai/gpt-oss-120b",
                  openrouter_api_key="or-key", openrouter_model=OPENROUTER_MODEL)
    values.update(overrides)
    return Settings(**values)


def answer(provider: str, text: str) -> httpx.Response:
    if provider == "gemini":
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


class Server:
    """Mock transport: per provider (or Gemini model) a list of outcomes; records every request."""

    def __init__(self, script: dict):
        self.script, self.seen = script, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        provider = HOSTS[request.url.host]
        key = request.url.path.split("/models/")[1].split(":")[0] if provider == "gemini" else provider
        body = json.loads(request.content)
        self.seen.append((key, request, body))
        outcome = self.script[key].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, int):
            return httpx.Response(outcome, json={"error": {"message": "x"}})
        return answer(provider, outcome)


def run(chain, **kwargs):
    return asyncio.run(generate_structured(chain, AnalysisDraft, "system", PROMPT,
                                           lambda: AnalysisDraft(findings=[], missing_information=["mock"]), True,
                                           **kwargs))


@pytest.fixture(autouse=True)
def _no_request_deadline():
    token = structured._request_deadline.set(None)
    yield
    structured._request_deadline.reset(token)


def test_chain_order_from_settings_and_secrets_hidden():
    chain = resolve_chain(settings())
    assert isinstance(chain, LLMChain)
    assert [(p.provider, p.model) for p in chain.providers] == [
        ("gemini", "gemini-a"), ("gemini", "gemini-b"), ("groq", "openai/gpt-oss-120b"),
        ("openrouter", OPENROUTER_MODEL)]
    for secret in ("gm-key", "gq-key", "or-key"):
        assert secret not in repr(chain)
    custom = resolve_chain(settings(llm_fallback_chain="openrouter,groq,mock"))
    assert [p.provider for p in custom.providers] == ["openrouter", "groq"]


def test_providers_without_key_or_approval_are_skipped():
    chain = resolve_chain(settings(groq_api_key=None, llm_approved_providers="gemini,groq,mock"))
    assert [p.provider for p in chain.providers] == ["gemini", "gemini"]
    assert chain.skipped == ["groq:no_key_or_model", "openrouter:not_approved"]
    assert resolve_chain(settings(openrouter_model=None, gemini_api_key=None, groq_api_key=None)) is None
    assert resolve_chain(settings(gemini_api_key=None, groq_api_key=None,
                                  openrouter_api_key=None)) is None  # only the mock is left
    for unknown in ("nonsense", "gemini,cerebras,mock"):  # Cerebras is not a provider (it needs payment)
        with pytest.raises(LLMNotConfigured):
            resolve_chain(settings(llm_fallback_chain=unknown))


def test_free_tier_providers_are_refused_in_production():
    with pytest.raises(LLMNotConfigured):  # no provider may run and the mock is never allowed in production
        resolve_chain(settings(app_env="production", llm_approved_providers="gemini,groq,openrouter"))


def test_default_chain_without_setting_is_provider_then_gemini_fallback():
    chain = resolve_chain(settings(llm_fallback_chain=None, llm_provider="gemini"))
    assert [p.model for p in chain.providers] == ["gemini-a", "gemini-b"]


@pytest.mark.parametrize(("provider", "url", "token"), [
    ("groq", "https://api.groq.com/openai/v1/chat/completions", "gq-key"),
    ("openrouter", "https://openrouter.ai/api/v1/chat/completions", "or-key"),
])
def test_openai_compatible_request_shape(provider, url, token):
    server = Server({provider: ["```json\n" + json.dumps(VALID) + "\n```"]})
    chain = resolve_chain(settings(llm_fallback_chain=f"{provider},mock"), transport=httpx.MockTransport(server))
    llm = chain.providers[0]
    assert isinstance(llm, OpenAICompatibleLLM) and llm.json_mode == "json_object"
    out = run(chain)
    assert (out.origin, out.provider, out.model) == ("ai", provider, llm.model)  # the fenced JSON is accepted
    _, request, body = server.seen[0]
    assert str(request.url) == url and request.headers["authorization"] == f"Bearer {token}"
    assert body["model"] == llm.model and body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    system = body["messages"][0]["content"]
    assert "JSON Schema named AnalysisDraft" in system and '"missing_information"' in system
    assert body["messages"][1] == {"role": "user", "content": PROMPT}


def test_gemini_request_uses_json_mode_and_header_key():
    server = Server({"gemini-a": [json.dumps(VALID)]})
    chain = resolve_chain(settings(llm_fallback_chain="gemini,mock"), transport=httpx.MockTransport(server))
    assert isinstance(chain.providers[0], GeminiLLM)
    assert run(chain).model == "gemini-a"
    _, request, body = server.seen[0]
    assert request.headers["x-goog-api-key"] == "gm-key" and "gm-key" not in str(request.url)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "responseJsonSchema" in body["generationConfig"]


def test_failover_goes_down_the_chain_immediately(caplog):
    server = Server({
        "gemini-a": [429],
        "gemini-b": [httpx.ReadTimeout("slow")],
        "groq": ["not json", '{"findings": 1}'],  # invalid, then invalid after the one repair
        "openrouter": [json.dumps(VALID)],
    })
    chain = resolve_chain(settings(), transport=httpx.MockTransport(server))
    with caplog.at_level("INFO", logger="pokkhoai"):
        out = run(chain)
    assert (out.origin, out.provider, out.model) == ("ai", "openrouter", OPENROUTER_MODEL)
    assert [key for key, _, _ in server.seen] == ["gemini-a", "gemini-b", "groq", "groq", "openrouter"]
    assert "<validation_errors>" in server.seen[3][2]["messages"][1]["content"]  # the repair request
    reasons = [(r.provider, r.reason) for r in caplog.records if getattr(r, "event", "") == "llm.provider_failed"]
    assert reasons == [("gemini", "http_429"), ("gemini", "timeout"), ("groq", "schema_validation_after_repair")]
    assert "repair_requested:invalid_json@groq/openai/gpt-oss-120b" in out.warnings
    answered = [r for r in caplog.records if getattr(r, "event", "") == "llm.answered"]
    assert [(r.provider, r.model) for r in answered] == [("openrouter", OPENROUTER_MODEL)]
    assert PROMPT not in caplog.text


def test_whole_chain_down_ends_in_labelled_mock(caplog):
    server = Server({"gemini-a": [429], "gemini-b": [503], "groq": [500], "openrouter": [429]})
    with caplog.at_level("INFO", logger="pokkhoai"):
        out = run(resolve_chain(settings(), transport=httpx.MockTransport(server)))
    assert out.origin == "ai_mock" and out.provider == "mock" and "fallback_to_mock" in out.warnings
    fallback = [r for r in caplog.records if getattr(r, "event", "") == "llm.fallback_to_mock"][0]
    assert fallback.reason == "gemini:http_429,gemini:http_503,groq:http_500,openrouter:http_429"
