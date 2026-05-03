"""OpenAI image describer provider.

Implements ``OpenAIImageDescriber`` using the OpenAI Chat Completions API
with ``image_url`` content parts for multimodal image description.

Requirements: 6.1, 6.5
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import time

from confluence_exporter.describer import ImageDescriber
from confluence_exporter.exceptions import ImageDescriptionError
from confluence_exporter.models import ImageContext, ImageDescriberConfig

logger = logging.getLogger(__name__)

# Retry configuration
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = [1, 2]  # wait times between retries

# HTTP status codes considered retryable
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# HTTP status codes that should NOT be retried
_NON_RETRYABLE_STATUS_CODES = frozenset({401, 403})


class OpenAIImageDescriber(ImageDescriber):
    """Image describer using OpenAI GPT-4o's vision capabilities.

    The API key is resolved from ``config.api_key`` first, falling
    back to the ``OPENAI_API_KEY`` environment variable.

    Parameters
    ----------
    config:
        Configuration including ``model`` (e.g. ``"gpt-4o"``)
        and optionally ``api_key``.
    """

    def __init__(self, config: ImageDescriberConfig) -> None:
        super().__init__(config)
        try:
            from openai import OpenAI  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImageDescriptionError(
                image_path="",
                provider="openai",
                message=(
                    "The 'openai' package is required for the OpenAI "
                    "provider. Install it with: "
                    "pip install confluence-exporter[openai]"
                ),
            ) from exc

        api_key = config.api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client = OpenAI(api_key=api_key)

    def describe(self, image_path: str, context: ImageContext) -> str:
        """Send image to GPT-4o with a description prompt.

        Reads the image as base64, constructs a data URL, and sends it
        via the OpenAI Chat Completions API with an ``image_url`` content
        part. For Gliffy diagrams the prompt emphasises process flow
        elements.

        Retries transient errors (429, 5xx, timeouts) up to 3 attempts
        with exponential backoff (1 s, 2 s). Non-retryable errors (401,
        403, invalid model) raise ``ImageDescriptionError`` immediately.
        """
        prompt = self._build_prompt(context)
        image_data = self._read_image_base64(image_path)
        media_type = self._detect_media_type(image_path)
        data_url = f"data:{media_type};base64,{image_data}"

        last_error: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = self._client.chat.completions.create(
                    model=self._config.model,
                    max_tokens=self._config.max_tokens,
                    temperature=self._config.temperature,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": data_url},
                                },
                                {
                                    "type": "text",
                                    "text": prompt,
                                },
                            ],
                        }
                    ],
                )
                return response.choices[0].message.content
            except Exception as exc:
                last_error = exc
                if self._is_retryable(exc) and attempt < _MAX_ATTEMPTS - 1:
                    wait = _BACKOFF_SECONDS[attempt]
                    logger.warning(
                        "OpenAI API transient error (attempt %d/%d), "
                        "retrying in %ds: %s",
                        attempt + 1,
                        _MAX_ATTEMPTS,
                        wait,
                        exc,
                    )
                    time.sleep(wait)
                    continue

                raise ImageDescriptionError(
                    image_path=image_path,
                    provider="openai",
                    message=f"OpenAI API error: {exc}",
                ) from exc

        # Should not reach here, but guard against it
        raise ImageDescriptionError(
            image_path=image_path,
            provider="openai",
            message=f"OpenAI API failed after {_MAX_ATTEMPTS} attempts: {last_error}",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_retryable(self, exc: Exception) -> bool:
        """Determine whether an exception is transient and retryable."""
        exc_type = type(exc).__name__

        # Timeout errors are always retryable
        if "Timeout" in exc_type or "timeout" in str(exc).lower():
            return True

        # Rate limit errors (429)
        if "RateLimitError" in exc_type:
            return True

        # Authentication / permission errors are NOT retryable
        if "AuthenticationError" in exc_type or "PermissionDenied" in exc_type:
            return False

        # Check for HTTP status code on the exception
        status_code = getattr(exc, "status_code", None)
        if status_code is not None:
            if status_code in _NON_RETRYABLE_STATUS_CODES:
                return False
            if status_code in _RETRYABLE_STATUS_CODES:
                return True

        # Server errors (5xx) indicated by name
        if "InternalServerError" in exc_type or "APIStatusError" in exc_type:
            status = getattr(exc, "status_code", 0)
            return status >= 500

        return False

    @staticmethod
    def _read_image_base64(image_path: str) -> str:
        """Read an image file and return its base64-encoded content."""
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except OSError as exc:
            raise ImageDescriptionError(
                image_path=image_path,
                provider="openai",
                message=f"Cannot read image file: {exc}",
            ) from exc

    @staticmethod
    def _detect_media_type(image_path: str) -> str:
        """Detect the MIME type of an image file."""
        mime_type, _ = mimetypes.guess_type(image_path)
        return mime_type or "image/png"
