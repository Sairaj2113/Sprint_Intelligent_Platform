"""Primary Groq generation with one controlled Gemini fallback."""

from __future__ import annotations

from dataclasses import replace

from app.services.llm.base import (
    LLMGenerationRequest,
    LLMGenerationResult,
    LLMNonRetryableError,
    LLMProvider,
    LLMRetryableError,
)
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.groq_provider import GroqProvider


class LLMService:
    """Provider-neutral orchestration with no retries beyond one fallback call."""

    def __init__(
        self,
        primary_provider: LLMProvider | None = None,
        fallback_provider: LLMProvider | None = None,
    ) -> None:
        self._primary_provider = primary_provider or GroqProvider()
        # Gemini configuration is only required if Groq has a retryable failure.
        self._fallback_provider = fallback_provider

    def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        """Generate with Groq, using Gemini once only for a retryable Groq failure."""
        try:
            return self._primary_provider.generate(request)
        except LLMNonRetryableError:
            raise
        except LLMRetryableError:
            fallback_provider = self._fallback_provider or GeminiProvider()
            self._fallback_provider = fallback_provider
            try:
                fallback_result = fallback_provider.generate(request)
            except LLMRetryableError as fallback_error:
                raise LLMRetryableError(
                    fallback_provider.provider_name,
                    "Primary and fallback LLM providers are temporarily unavailable",
                ) from fallback_error
            except LLMNonRetryableError:
                raise
            return replace(fallback_result, fallback_used=True)
