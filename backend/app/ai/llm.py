"""Structured-output LLM providers for app/ (DOCS/providers.md governs which may run).

- mock: no model; the fact extractor uses a deterministic stand-in. Development
  and test only; NOT_CONFIGURED in production.
- ollama: local OpenAI-compatible server. LLM_BASE_URL must be localhost so no
  data leaves the machine. Output is requested with a JSON schema
  (response_format json_schema) and validated by the caller with Pydantic.

A provider must also be listed in LLM_APPROVED_PROVIDERS. Prompts and responses
are never logged.
"""

import json
from dataclasses import dataclass
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


def approved_providers(settings: Settings) -> set[str]:
    return {p.strip().lower() for p in settings.llm_approved_providers.split(",") if p.strip()}


def resolve_provider(settings: Settings, transport: httpx.BaseTransport | None = None) -> StructuredLLM | None:
    """Return the configured LLM, None for the mock extractor, or raise LLMNotConfigured."""
    provider = settings.llm_provider
    if provider not in approved_providers(settings):
        raise LLMNotConfigured(f"LLM provider {provider!r} is not in LLM_APPROVED_PROVIDERS")
    if provider == "mock":
        if settings.app_env == "production":
            raise LLMNotConfigured("The mock extractor is not allowed in production")
        return None
    if not settings.llm_base_url or not settings.llm_model:
        raise LLMNotConfigured("LLM_BASE_URL and LLM_MODEL are required for ollama")
    if urlparse(settings.llm_base_url).hostname not in LOCAL_HOSTS:
        raise LLMNotConfigured("Ollama is approved only on localhost (DOCS/providers.md)")
    return OllamaLLM(settings.llm_base_url, settings.llm_model, settings.llm_timeout_seconds, transport)


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
