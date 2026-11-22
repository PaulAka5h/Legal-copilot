"""Structured-output LLM providers for app/ (DOCS/providers.md governs which may run).

- mock: no model; the fact extractor uses a deterministic stand-in. Development
  and test only; NOT_CONFIGURED in production.
- ollama: local OpenAI-compatible server. LLM_BASE_URL must be localhost so no
  data leaves the machine. Output is requested with a JSON schema
  (response_format json_schema) and validated by the caller with Pydantic.
- gemini: Google Gemini API, free tier, approved for SYNTHETIC SAMPLE DATA ONLY;
  refused in production. JSON schema output, temperature 0. The key is sent in
  a header, never in the URL.

- groq, openrouter: free-tier OpenAI-compatible APIs, approved for
  SYNTHETIC/PUBLIC DATA ONLY and refused in production (same rule as Gemini).
  JSON mode (response_format json_object) plus the JSON schema in the system
  prompt; the caller validates with Pydantic.

Fallback chain (resolve_chain): LLM_FALLBACK_CHAIN, e.g.
"gemini,gemini_fallback,groq,openrouter,mock". A provider without a key or
model, or not in LLM_APPROVED_PROVIDERS, is skipped; "mock" (or no usable provider)
ends in the deterministic mock, labelled ai_mock, when mock is allowed here.

Prompts and responses are never logged.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from app.config import Settings

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class LLMNotConfigured(RuntimeError):
    """The requested provider cannot run here; endpoints answer NOT_CONFIGURED."""


class StructuredLLM(Protocol):
    provider: str
    model: str

    def complete_json(self, system: str, user: str, schema_name: str, schema: dict[str, Any]) -> str: ...


@dataclass
class OpenAICompatibleLLM:
    """Chat-completions API (Ollama, Groq, OpenRouter).

    json_mode "json_schema" sends the schema as response_format (local Ollama);
    "json_object" asks for a JSON object and puts the schema in the system prompt,
    which every hosted free-tier model accepts.
    """

    base_url: str
    model: str
    timeout: float
    transport: httpx.BaseTransport | None = None
    provider: str = "ollama"
    api_key: str | None = field(default=None, repr=False)
    json_mode: str = "json_schema"

    def complete_json(self, system: str, user: str, schema_name: str, schema: dict[str, Any]) -> str:
        if self.json_mode == "json_schema":
            response_format: dict[str, Any] = {
                "type": "json_schema", "json_schema": {"name": schema_name, "schema": schema, "strict": True}}
        else:
            response_format = {"type": "json_object"}
            system = (f"{system}\n\nAnswer with one JSON object only (no prose, no code fence) that is valid "
                      f"against this JSON Schema named {schema_name}:\n{json.dumps(schema, separators=(',', ':'))}")
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": response_format,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
            response = client.post(f"{self.base_url.rstrip('/')}/chat/completions", json=body, headers=headers)
            response.raise_for_status()
            payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("unexpected completion shape") from error
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty completion")
        return _strip_fence(content)


OllamaLLM = OpenAICompatibleLLM  # backwards-compatible name


def _strip_fence(text: str) -> str:
    """Some free models wrap JSON in a ```json fence even in JSON mode."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        stripped = stripped.rsplit("```", 1)[0]
    return stripped.strip()


GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _gemini_schema(node: Any) -> Any:
    """Copy of the schema for Gemini without keywords its decoder rejects or cannot compile.

    Length, item-count, pattern, format, and numeric bounds make Gemini answer 400
    "too many states". Pydantic still enforces every one of them on the response.
    """
    unsupported = {"additionalProperties", "title", "default", "maxLength", "minLength", "maxItems",
                   "minItems", "pattern", "format", "minimum", "maximum", "exclusiveMinimum",
                   "exclusiveMaximum"}
    if isinstance(node, dict):
        return {k: _gemini_schema(v) for k, v in node.items() if k not in unsupported}
    if isinstance(node, list):
        return [_gemini_schema(v) for v in node]
    return node


@dataclass
class GeminiLLM:
    api_key: str = field(repr=False)
    model: str
    timeout: float
    transport: httpx.BaseTransport | None = None
    provider: str = "gemini"
    fallback_model: str | None = None  # GEMINI_FALLBACK_MODEL: tried when `model` gives up (app.ai.structured)

    def complete_json(self, system: str, user: str, schema_name: str, schema: dict[str, Any]) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseJsonSchema": _gemini_schema(schema),
            },
        }
        with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
            response = client.post(
                GEMINI_ENDPOINT.format(model=self.model), json=body,
                headers={"x-goog-api-key": self.api_key},
            )
            response.raise_for_status()
            payload = response.json()
        try:
            return "".join(p.get("text", "") for p in payload["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("unexpected Gemini response shape") from error


def approved_providers(settings: Settings) -> set[str]:
    return {p.strip().lower() for p in settings.llm_approved_providers.split(",") if p.strip()}


def _configured_llm(settings: Settings, transport: httpx.BaseTransport | None) -> StructuredLLM:
    provider = settings.llm_provider
    if provider not in approved_providers(settings):
        raise LLMNotConfigured(f"LLM provider {provider!r} is not in LLM_APPROVED_PROVIDERS")
    if provider == "gemini":
        if settings.app_env == "production":
            raise LLMNotConfigured("Gemini is approved for synthetic sample data only, not production")
        if not settings.gemini_api_key or not settings.gemini_model:
            raise LLMNotConfigured("GEMINI_API_KEY and GEMINI_MODEL are required for gemini")
        return GeminiLLM(settings.gemini_api_key.get_secret_value(), settings.gemini_model,
                         settings.llm_timeout_seconds, transport, fallback_model=settings.gemini_fallback_model)
    if not settings.llm_base_url or not settings.llm_model:
        raise LLMNotConfigured("LLM_BASE_URL and LLM_MODEL are required for ollama")
    if urlparse(settings.llm_base_url).hostname not in LOCAL_HOSTS:
        raise LLMNotConfigured("Ollama is approved only on localhost (DOCS/providers.md)")
    return OpenAICompatibleLLM(settings.llm_base_url, settings.llm_model, settings.llm_timeout_seconds, transport)


def mock_allowed(settings: Settings) -> bool:
    return "mock" in approved_providers(settings) and settings.app_env != "production"


def resolve_provider(settings: Settings, transport: httpx.BaseTransport | None = None) -> StructuredLLM | None:
    """Return the configured LLM, None for the mock (fallback chain), or raise LLMNotConfigured."""
    if settings.llm_provider == "mock":
        if not mock_allowed(settings):
            raise LLMNotConfigured("The mock provider is not approved here (never in production)")
        return None
    try:
        return _configured_llm(settings, transport)
    except LLMNotConfigured:
        if mock_allowed(settings):
            return None  # fallback chain: configured provider unusable -> mock
        raise


def strict_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Pydantic schema with $defs inlined; strict providers reject $ref in some versions."""
    defs = schema.get("$defs", {})

    def inline(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return inline(defs[node["$ref"].split("/")[-1]])
            return {k: inline(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [inline(v) for v in node]
        return node

    return json.loads(json.dumps(inline(schema)))


# ------------------------------------------------------------------ provider chain
CHAIN_PROVIDERS = ("gemini", "gemini_fallback", "groq", "openrouter", "ollama", "mock")
HOSTED_FREE_TIER = {"groq", "openrouter"}


@dataclass
class LLMChain:
    """Providers in order; app.ai.structured tries each in turn, then the labelled mock."""

    providers: list[StructuredLLM]
    skipped: list[str] = field(default_factory=list)  # "name:reason", for logs and warnings

    @property
    def provider(self) -> str:
        return self.providers[0].provider

    @property
    def model(self) -> str:
        return self.providers[0].model

    def complete_json(self, system: str, user: str, schema_name: str, schema: dict[str, Any]) -> str:
        """First provider that answers (fact extraction validates and falls back to mock itself)."""
        last: Exception | None = None
        for llm in self.providers:
            try:
                return llm.complete_json(system, user, schema_name, schema)
            except httpx.HTTPError as error:
                last = error
        assert last is not None
        raise last


def chain_names(settings: Settings) -> list[str]:
    if settings.llm_fallback_chain:
        names = [n.strip().lower() for n in settings.llm_fallback_chain.split(",") if n.strip()]
    else:
        names = [settings.llm_provider] + (["gemini_fallback"] if settings.llm_provider == "gemini" else [])
    unknown = [n for n in names if n not in CHAIN_PROVIDERS]
    if unknown:
        raise LLMNotConfigured(f"Unknown provider(s) in LLM_FALLBACK_CHAIN: {', '.join(unknown)}")
    return names


def _secret(value) -> str | None:
    return value.get_secret_value() if value is not None and value.get_secret_value().strip() else None


def _build(name: str, settings: Settings, transport: httpx.BaseTransport | None) -> StructuredLLM:
    """One chain entry, or LLMNotConfigured with the reason it cannot run here."""
    approval = "gemini" if name == "gemini_fallback" else name
    if approval not in approved_providers(settings):
        raise LLMNotConfigured("not_approved")
    timeout = settings.llm_timeout_seconds
    if name in ("gemini", "gemini_fallback") or name in HOSTED_FREE_TIER:
        if settings.app_env == "production":
            raise LLMNotConfigured("synthetic_data_only")  # free tiers: never production (DOCS/providers.md)
    if name in ("gemini", "gemini_fallback"):
        key = _secret(settings.gemini_api_key)
        model = settings.gemini_model if name == "gemini" else settings.gemini_fallback_model
        if not key or not model:
            raise LLMNotConfigured("no_key_or_model")
        return GeminiLLM(key, model, timeout, transport)
    if name in HOSTED_FREE_TIER:
        key = _secret(getattr(settings, f"{name}_api_key"))
        model = getattr(settings, f"{name}_model")
        if not key or not model:
            raise LLMNotConfigured("no_key_or_model")
        return OpenAICompatibleLLM(getattr(settings, f"{name}_base_url"), model, timeout, transport,
                                   provider=name, api_key=key, json_mode="json_object")
    if name == "ollama":
        if not settings.llm_base_url or not settings.llm_model:
            raise LLMNotConfigured("no_key_or_model")
        if urlparse(settings.llm_base_url).hostname not in LOCAL_HOSTS:
            raise LLMNotConfigured("not_localhost")
        return OpenAICompatibleLLM(settings.llm_base_url, settings.llm_model, timeout, transport)
    raise LLMNotConfigured("unknown")


def resolve_chain(settings: Settings, transport: httpx.BaseTransport | None = None) -> LLMChain | None:
    """The usable providers in chain order; None means only the mock (or LLMNotConfigured)."""
    providers: list[StructuredLLM] = []
    skipped: list[str] = []
    for name in chain_names(settings):
        if name == "mock":
            break  # the mock always comes last
        try:
            providers.append(_build(name, settings, transport))
        except LLMNotConfigured as reason:
            skipped.append(f"{name}:{reason}")
    if providers:
        return LLMChain(providers, skipped)
    if mock_allowed(settings):
        return None
    raise LLMNotConfigured("No LLM provider in the chain can run here and the mock is not allowed: "
                           + ", ".join(skipped))
