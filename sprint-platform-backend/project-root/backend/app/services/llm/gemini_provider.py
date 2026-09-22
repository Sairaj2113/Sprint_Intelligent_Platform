"""Gemini SDK adapter with vendor-specific error classification contained here."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services.llm.base import (
    LLMGenerationRequest,
    LLMGenerationResult,
    LLMNonRetryableError,
    LLMRetryableError,
    LLMUsage,
)

try:  # The verified experimental script uses this package and API surface.
    from google import genai
except ImportError:  # pragma: no cover - requirements install this in application runtime.
    genai = None  # type: ignore[assignment]


class GeminiProvider:
    """Generate responses through Gemini's verified interactions API."""

    provider_name = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model_name = model_name or settings.GEMINI_MODEL_NAME
        if client is not None:
            self._client = client
            return

        configured_key = api_key or _configured_secret(settings.GEMINI_API_KEY)
        if not configured_key:
            raise LLMNonRetryableError(self.provider_name, "Gemini API key is not configured")
        if genai is None:
            raise LLMNonRetryableError(self.provider_name, "Gemini SDK is not installed")
        self._client = genai.Client(api_key=configured_key)

    def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        input_text = f"{request.system_prompt}\n\n{request.user_prompt}"
        parameters: dict[str, Any] = {
            "model": self.model_name,
            "input": input_text,
            "store": False,
        }
        # The verified interactions API does not require generation configuration.
        # Do not send provider-specific options it may not support.
        try:
            response = self._client.interactions.create(**parameters)
            content = response.output_text
        except Exception as error:
            _raise_normalized_error(error)

        if not isinstance(content, str) or not content.strip():
            raise LLMNonRetryableError(self.provider_name, "Gemini returned an empty response")
        return LLMGenerationResult(
            content=content,
            provider=self.provider_name,
            model=_string_or_default(getattr(response, "model", None), self.model_name),
            usage=_normalize_usage(getattr(response, "usage", None)),
        )


def _configured_secret(secret: Any) -> str | None:
    return secret.get_secret_value() if secret is not None else None


def _status_code(error: Exception) -> int | None:
    value = getattr(error, "status_code", None)
    if value is None:
        response = getattr(error, "response", None)
        value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _raise_normalized_error(error: Exception) -> None:
    status_code = _status_code(error)
    retryable_names = {"APITimeoutError", "APIConnectionError", "DeadlineExceeded"}
    if isinstance(error, TimeoutError) or status_code == 429 or (status_code is not None and status_code >= 500) or error.__class__.__name__ in retryable_names:
        raise LLMRetryableError("gemini", "Gemini is temporarily unavailable") from error
    raise LLMNonRetryableError("gemini", "Gemini request failed") from error


def _string_or_default(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default


def _usage_value(usage: Any, *names: str) -> int | None:
    for name in names:
        value = getattr(usage, name, None)
        if isinstance(value, int):
            return value
    return None


def _normalize_usage(usage: Any) -> LLMUsage | None:
    if usage is None:
        return None
    normalized = LLMUsage(
        input_tokens=_usage_value(usage, "input_tokens", "prompt_tokens"),
        output_tokens=_usage_value(usage, "output_tokens", "completion_tokens", "candidates_token_count"),
        total_tokens=_usage_value(usage, "total_tokens", "total_token_count"),
    )
    return normalized if any(value is not None for value in normalized.__dict__.values()) else None
