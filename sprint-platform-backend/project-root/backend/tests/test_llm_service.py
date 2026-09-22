"""No-network unit tests for Phase 10A provider fallback orchestration."""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from app.services.llm.base import (
    LLMGenerationRequest,
    LLMGenerationResult,
    LLMNonRetryableError,
    LLMRetryableError,
    LLMUsage,
)
from app.services.llm.llm_service import LLMService


@dataclass
class FakeProvider:
    provider_name: str
    result: LLMGenerationResult | None = None
    error: Exception | None = None
    calls: int = 0

    def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def request() -> LLMGenerationRequest:
    return LLMGenerationRequest(
        system_prompt="You are a concise assistant.",
        user_prompt="Summarize this sprint.",
        temperature=0.2,
        max_output_tokens=120,
    )


class LLMServiceTests(unittest.TestCase):
    def test_groq_success_does_not_call_gemini(self) -> None:
        groq = FakeProvider(
            "groq",
            result=LLMGenerationResult(content="Groq answer", provider="groq", model="openai/gpt-oss-20b"),
        )
        gemini = FakeProvider(
            "gemini",
            result=LLMGenerationResult(content="Gemini answer", provider="gemini", model="gemini-3.6-flash"),
        )

        result = LLMService(groq, gemini).generate(request())

        self.assertEqual(groq.calls, 1)
        self.assertEqual(gemini.calls, 0)
        self.assertEqual(result.provider, "groq")
        self.assertFalse(result.fallback_used)

    def test_retryable_groq_error_calls_gemini_once(self) -> None:
        groq = FakeProvider("groq", error=LLMRetryableError("groq", "rate limited"))
        gemini = FakeProvider(
            "gemini",
            result=LLMGenerationResult(content="Gemini answer", provider="gemini", model="gemini-3.6-flash"),
        )

        result = LLMService(groq, gemini).generate(request())

        self.assertEqual(groq.calls, 1)
        self.assertEqual(gemini.calls, 1)
        self.assertEqual(result.provider, "gemini")
        self.assertTrue(result.fallback_used)

    def test_non_retryable_groq_error_does_not_call_gemini(self) -> None:
        groq = FakeProvider("groq", error=LLMNonRetryableError("groq", "invalid credentials"))
        gemini = FakeProvider("gemini")

        with self.assertRaises(LLMNonRetryableError):
            LLMService(groq, gemini).generate(request())

        self.assertEqual(groq.calls, 1)
        self.assertEqual(gemini.calls, 0)

    def test_two_retryable_provider_failures_raise_controlled_error_without_loop(self) -> None:
        groq = FakeProvider("groq", error=LLMRetryableError("groq", "timeout"))
        gemini = FakeProvider("gemini", error=LLMRetryableError("gemini", "unavailable"))

        with self.assertRaises(LLMRetryableError) as error:
            LLMService(groq, gemini).generate(request())

        self.assertEqual(error.exception.provider, "gemini")
        self.assertEqual(groq.calls, 1)
        self.assertEqual(gemini.calls, 1)

    def test_result_metadata_is_normalized(self) -> None:
        usage = LLMUsage(input_tokens=12, output_tokens=8, total_tokens=20)
        groq = FakeProvider(
            "groq",
            result=LLMGenerationResult(
                content="Normalized response", provider="groq", model="openai/gpt-oss-20b", usage=usage
            ),
        )

        result = LLMService(groq, FakeProvider("gemini")).generate(request())

        self.assertEqual(result.content, "Normalized response")
        self.assertEqual(result.usage, usage)
        self.assertNotIn("response", result.__dict__)
        self.assertNotIn("raw", result.__dict__)

    def test_invalid_request_is_rejected_before_any_provider_call(self) -> None:
        with self.assertRaises(LLMNonRetryableError):
            LLMGenerationRequest(system_prompt=" ", user_prompt="valid")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
