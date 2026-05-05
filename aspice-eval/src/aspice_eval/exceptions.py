"""Custom exceptions for the ASPICE evaluation tool.

Provides structured error types for KB validation, SDP ingestion,
configuration, and AI model interaction failures.
"""

from __future__ import annotations

from typing import Any


class KBValidationError(Exception):
    """Raised when a knowledge base file fails schema validation.

    Carries structured context about the validation failure including
    the file path and the list of schema violations.
    """

    def __init__(
        self,
        message: str,
        *,
        file_path: str = "",
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.file_path = file_path
        self.errors = errors or []


class UnsupportedFormatError(Exception):
    """Raised when a file format or report format is unsupported.

    Carries the file path and the actual extension that was rejected,
    along with a message identifying the expected format. Also supports
    listing available formats for renderer registry errors.
    """

    def __init__(
        self,
        message: str,
        *,
        file_path: str = "",
        actual_extension: str = "",
        supported_formats: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.file_path = file_path
        self.actual_extension = actual_extension
        self.supported_formats = supported_formats or []


class InvalidConfigError(Exception):
    """Raised when evaluation configuration parameters are invalid.

    Covers out-of-range target levels (outside 1–5) and unknown
    process group codes. Carries the parameter name, the invalid
    value, and the set of valid/expected values.
    """

    def __init__(
        self,
        message: str,
        *,
        parameter: str = "",
        actual_value: Any = None,
        expected_values: list[Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.parameter = parameter
        self.actual_value = actual_value
        self.expected_values = expected_values or []


class AIModelError(Exception):
    """Raised when the AI model API call fails.

    Covers transient failures such as timeouts, rate limits, and
    authentication errors. The evaluator retries with exponential
    backoff before surfacing this error.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        model_name: str = "",
        attempt: int = 0,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.model_name = model_name
        self.attempt = attempt


class AIResponseParseError(Exception):
    """Raised when the AI model response cannot be parsed into ratings.

    Carries the raw response text and any partial results that were
    successfully parsed before the error occurred.
    """

    def __init__(
        self,
        message: str,
        *,
        raw_response: str = "",
        partial_results: list[Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.raw_response = raw_response
        self.partial_results = partial_results or []
