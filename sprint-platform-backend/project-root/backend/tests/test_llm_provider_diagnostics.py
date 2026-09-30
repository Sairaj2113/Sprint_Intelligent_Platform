"""No-network tests for sanitized Groq provider failure diagnostics."""

from __future__ import annotations

import unittest

from app.services.llm import groq_provider
from app.services.llm.base import LLMNonRetryableError, LLMRetryableError


class SimulatedProviderError(Exception):
    def __init__(self, *, status_code: int, code: str) -> None:
        super().__init__("prompt=evidence contents must never be logged; api_key=secret-value")
        self.status_code = status_code
        self.code = code


class LLMProviderDiagnosticsTests(unittest.TestCase):
    def test_retryable_failure_logs_safe_metadata_before_normalization(self) -> None:
        error = SimulatedProviderError(status_code=503, code="server_error")

        with self.assertLogs(groq_provider.logger, level="WARNING") as logs:
            with self.assertRaises(LLMRetryableError):
                groq_provider._raise_normalized_error(error)

        message = logs.output[0]
        self.assertIn("provider=groq", message)
        self.assertIn("exception_type=SimulatedProviderError", message)
        self.assertIn("http_status=503", message)
        self.assertIn("provider_error_category=server_error", message)
        self.assertIn("classification=retryable", message)
        self.assertIn("fallback_will_be_attempted=True", message)
        self.assertNotIn("prompt=evidence", message)
        self.assertNotIn("api_key=secret-value", message)

    def test_non_retryable_failure_logs_safe_metadata_before_normalization(self) -> None:
        error = SimulatedProviderError(status_code=400, code="invalid_request_error")

        with self.assertLogs(groq_provider.logger, level="WARNING") as logs:
            with self.assertRaises(LLMNonRetryableError):
                groq_provider._raise_normalized_error(error)

        message = logs.output[0]
        self.assertIn("provider=groq", message)
        self.assertIn("exception_type=SimulatedProviderError", message)
        self.assertIn("http_status=400", message)
        self.assertIn("provider_error_category=invalid_request_error", message)
        self.assertIn("classification=non_retryable", message)
        self.assertIn("fallback_will_be_attempted=False", message)
        self.assertNotIn("prompt=evidence", message)
        self.assertNotIn("api_key=secret-value", message)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
