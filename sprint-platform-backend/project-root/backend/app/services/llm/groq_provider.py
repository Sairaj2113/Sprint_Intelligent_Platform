"""Groq SDK adapter with vendor-specific error classification contained here."""

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

try:  # Keep application imports controlled if an optional SDK is absent.
    from groq import Groq
except ImportError:  # pragma: no cover - requirements install this in application runtime.
    Groq = None  # type: ignore[assignment,misc]


class GroqProvider:
    """Generate responses through Groq's chat-completions API."""

    provider_name = "groq"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model_name = model_name or settings.GROQ_MODEL_NAME
        if client is not None:
            self._client = client
            return

        configured_key = api_key or _configured_secret(settings.GROQ_API_KEY)
        if not configured_key:
            raise LLMNonRetryableError(self.provider_name, "Groq API key is not configured")
        if Groq is None:
            raise LLMNonRetryableError(self.provider_name, "Groq SDK is not installed")
        self._client = Groq(api_key=configured_key)

    def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        parameters: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
        }
        if request.temperature is not None:
            parameters["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            parameters["max_tokens"] = request.max_output_tokens
        try:
            response = self._client.chat.completions.create(**parameters)
            content = response.choices[0].message.content
        except Exception as error:
            _raise_normalized_error(error)

        if not isinstance(content, str) or not content.strip():
            raise LLMNonRetryableError(self.provider_name, "Groq returned an empty response")
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
    retryable_names = {"APITimeoutError", "APIConnectionError", "TimeoutException"}
    if isinstance(error, TimeoutError) or status_code == 429 or (status_code is not None and status_code >= 500) or error.__class__.__name__ in retryable_names:
        raise LLMRetryableError("groq", "Groq is temporarily unavailable") from error
    raise LLMNonRetryableError("groq", "Groq request failed") from error


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
        input_tokens=_usage_value(usage, "prompt_tokens", "input_tokens"),
        output_tokens=_usage_value(usage, "completion_tokens", "output_tokens"),
        total_tokens=_usage_value(usage, "total_tokens"),
    )
    return normalized if any(value is not None for value in normalized.__dict__.values()) else None
