"""Structured-output LLM providers for app/ (DOCS/providers.md governs which may run).

- mock: no model; the fact extractor uses a deterministic stand-in. Development
  and test only; NOT_CONFIGURED in production.
- ollama: local OpenAI-compatible server. LLM_BASE_URL must be localhost so no
  data leaves the machine. Output is requested with a JSON schema
  (response_format json_schema) and validated by the caller with Pydantic.
- gemini: Google Gemini API, free tier, approved for SYNTHETIC SAMPLE DATA ONLY;
  refused in production. JSON schema output, temperature 0. The key is sent in
  a header, never in the URL.

Fallback chain: if the configured provider (gemini or ollama) cannot be used
here, resolution falls back to mock when mock is approved and not in
production; callers also fall back to mock per call on transport errors and
label that output ai_mock.

A provider must also be listed in LLM_APPROVED_PROVIDERS. Prompts and responses
are never logged.
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
class OllamaLLM:
    base_url: str
    model: str
    timeout: float
    transport: httpx.BaseTransport | None = None
    provider: str = "ollama"

    def complete_json(self, system: str, user: str, schema_name: str, schema: dict[str, Any]) -> str:
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": True},
            },
        }
        with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
            response = client.post(f"{self.base_url.rstrip('/')}/chat/completions", json=body)
            response.raise_for_status()
            payload = response.json()
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("unexpected completion shape") from error


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
                         settings.llm_timeout_seconds, transport)
    if not settings.llm_base_url or not settings.llm_model:
        raise LLMNotConfigured("LLM_BASE_URL and LLM_MODEL are required for ollama")
    if urlparse(settings.llm_base_url).hostname not in LOCAL_HOSTS:
        raise LLMNotConfigured("Ollama is approved only on localhost (DOCS/providers.md)")
    return OllamaLLM(settings.llm_base_url, settings.llm_model, settings.llm_timeout_seconds, transport)


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
