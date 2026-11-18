"""Google Gemini Provider Adapter."""

import json
import os
from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel
from backend.src.ai.gateway import BaseLLMProvider, LLMResponse, LLMTokenUsage

T = TypeVar("T", bound=BaseModel)


def _clean_schema_for_gemini(schema: Any) -> Any:
    """Recursively strip additionalProperties / additional_properties for Gemini Developer API mode."""
    if isinstance(schema, dict):
        clean = {}
        for k, v in schema.items():
            if k in ("additionalProperties", "additional_properties"):
                continue
            clean[k] = _clean_schema_for_gemini(v)
        return clean
    elif isinstance(schema, list):
        return [_clean_schema_for_gemini(item) for item in schema]
    return schema


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider adapter using google-genai SDK."""

    def __init__(self, model_name: str = "gemini-3.5-flash-lite", api_key: Optional[str] = None):
        self._model_name = model_name
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self._api_key:
            # We don't crash at init, but warn/fail if invoked without key
            pass

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: Optional[Type[T]] = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        if not self._api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured in your environment or .env file.\n"
                "Please run: export GEMINI_API_KEY='your-key-here'\n"
                "Or pass api_key=... to GeminiProvider(api_key='...')."
            )

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self._api_key)

        config_args = {"temperature": temperature}
        if system_prompt:
            config_args["system_instruction"] = system_prompt
        if response_schema:
            config_args["response_mime_type"] = "application/json"
            if hasattr(response_schema, "model_json_schema"):
                raw_schema = response_schema.model_json_schema()
                config_args["response_schema"] = _clean_schema_for_gemini(raw_schema)
            elif isinstance(response_schema, dict):
                config_args["response_schema"] = _clean_schema_for_gemini(response_schema)
            else:
                config_args["response_schema"] = response_schema

        config = types.GenerateContentConfig(**config_args)
        response = client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=config,
        )

        content = response.text or ""
        # Strip potential markdown fences if present
        trimmed = content.strip()
        if trimmed.startswith("```json"):
            trimmed = trimmed[7:]
        elif trimmed.startswith("```"):
            trimmed = trimmed[3:]
        if trimmed.endswith("```"):
            trimmed = trimmed[:-3]
        clean_content = trimmed.strip()

        parsed = None
        if response_schema and clean_content:
            try:
                parsed = response_schema.model_validate_json(clean_content)
            except Exception:
                try:
                    data = json.loads(clean_content)
                    parsed = response_schema.model_validate(data)
                except Exception:
                    pass

        usage = LLMTokenUsage()
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage.prompt_tokens = response.usage_metadata.prompt_token_count or 0
            usage.completion_tokens = response.usage_metadata.candidates_token_count or 0
            usage.total_tokens = response.usage_metadata.total_token_count or 0

        return LLMResponse(
            content=content,
            parsed=parsed,
            provider="gemini",
            model=self._model_name,
            usage=usage,
        )
