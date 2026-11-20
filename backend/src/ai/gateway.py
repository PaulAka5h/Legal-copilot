"""Provider-Agnostic LLM Gateway with Structured Output Validation.

Adheres strictly to:
- DOCS/providers.md: Provider whitelist enforcement.
- AGENTS.md Rule 10: No external AI provider not listed in DOCS/providers.md. Default to mock provider.
- AGENTS.md Rule 11: Do not claim a feature works if provider is missing (return NOT_CONFIGURED).
"""

from abc import ABC, abstractmethod
import os
import time
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class ProviderNotApprovedError(Exception):
    """Raised when an unapproved LLM provider is invoked."""
    pass


class LLMTokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    content: str
    parsed: Optional[Any] = None
    provider: str
    model: str
    usage: LLMTokenUsage = Field(default_factory=LLMTokenUsage)
    latency_ms: float = 0.0


class BaseLLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: Optional[Type[T]] = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Generate a response, optionally parsed into a Pydantic schema."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass


class LLMGateway:
    """Central gateway for all LLM calls across the platform."""

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        approved_providers: Optional[List[str]] = None,
    ):
        # DOCS/providers.md approves only "mock". Gemini stays disabled until a
        # review record exists there and LLM_APPROVED_PROVIDERS is set explicitly.
        raw_approved = os.getenv("LLM_APPROVED_PROVIDERS", "mock")
        self.approved_providers = approved_providers or [
            p.strip().lower() for p in raw_approved.split(",") if p.strip()
        ]
        
        # If no provider passed, initialize based on LLM_PROVIDER env
        if provider is None:
            provider_type = os.getenv("LLM_PROVIDER", "mock").strip().lower()
            if provider_type == "gemini":
                from backend.src.ai.providers.gemini import GeminiProvider
                model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
                self._provider = GeminiProvider(model_name=model_name)
            else:
                from backend.src.ai.providers.mock import MockLLMProvider
                self._provider = MockLLMProvider()
        else:
            self._provider = provider

        self._validate_provider(self._provider.provider_name)

    def _validate_provider(self, provider_name: str) -> None:
        """Ensure provider is approved per DOCS/providers.md."""
        clean_name = provider_name.strip().lower()
        if clean_name not in self.approved_providers:
            raise ProviderNotApprovedError(
                f"Provider '{provider_name}' is not in the approved list: {self.approved_providers}. "
                f"See DOCS/providers.md for approval records."
            )

    @property
    def current_provider(self) -> str:
        return self._provider.provider_name

    @property
    def current_model(self) -> str:
        return self._provider.model_name

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: Optional[Type[T]] = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Execute LLM call with timing and schema enforcement."""
        self._validate_provider(self._provider.provider_name)
        start_time = time.perf_counter()
        
        response = self._provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            response_schema=response_schema,
            temperature=temperature,
        )
        
        response.latency_ms = (time.perf_counter() - start_time) * 1000.0
        return response

    def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
    ) -> T:
        """Helper to directly return the parsed Pydantic model."""
        res = self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            response_schema=schema,
            temperature=temperature,
        )
        if res.parsed is not None and isinstance(res.parsed, schema):
            return res.parsed
        raise ValueError(f"Failed to parse LLM output into {schema.__name__}")
