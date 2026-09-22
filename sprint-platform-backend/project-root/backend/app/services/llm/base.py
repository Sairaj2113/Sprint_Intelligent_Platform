"""Provider-neutral LLM request, result, usage, and error contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LLMProviderError(Exception):
    """Base controlled error raised by an LLM provider adapter."""

    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(detail)
        self.provider = provider
        self.detail = detail


class LLMRetryableError(LLMProviderError):
    """A temporary provider failure for which one fallback is allowed."""


class LLMNonRetryableError(LLMProviderError):
    """A configuration, validation, authentication, or permanent provider error."""


@dataclass(frozen=True)
class LLMGenerationRequest:
    """A vendor-independent single-turn generation request."""

    system_prompt: str
    user_prompt: str
    temperature: float | None = None
    max_output_tokens: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.system_prompt, str) or not self.system_prompt.strip():
            raise LLMNonRetryableError("application", "System prompt must not be blank")
        if not isinstance(self.user_prompt, str) or not self.user_prompt.strip():
            raise LLMNonRetryableError("application", "User prompt must not be blank")
        if self.temperature is not None and not 0 <= self.temperature <= 2:
            raise LLMNonRetryableError("application", "Temperature must be between 0 and 2")
        if self.max_output_tokens is not None and self.max_output_tokens < 1:
            raise LLMNonRetryableError(
                "application", "max_output_tokens must be greater than zero"
            )


@dataclass(frozen=True)
class LLMUsage:
    """Normalized token metadata, when a provider returns it."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class LLMGenerationResult:
    """A provider-neutral response which never exposes a vendor SDK object."""

    content: str
    provider: str
    model: str
    fallback_used: bool = False
    usage: LLMUsage | None = None


class LLMProvider(Protocol):
    """Minimal adapter contract used by the fallback orchestrator."""

    provider_name: str

    def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        """Generate one response or raise a controlled provider error."""

