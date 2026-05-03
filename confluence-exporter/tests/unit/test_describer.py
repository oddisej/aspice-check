"""Unit tests for the image describer base class and AI provider error handling.

Tests cover:
- Placeholder description on provider failure
- Retry on transient errors (mock API)
- ``--no-ai`` flag skips description generation (describe_batch with empty list)

Requirements: 6.5, 6.6
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from confluence_exporter.describer import ImageDescriber, _PLACEHOLDER_DESCRIPTION
from confluence_exporter.exceptions import ImageDescriptionError
from confluence_exporter.models import ImageContext, ImageDescriberConfig


# ---------------------------------------------------------------------------
# Concrete test describer (for testing base class behaviour)
# ---------------------------------------------------------------------------


class _FakeDescriber(ImageDescriber):
    """Concrete describer for testing base class logic."""

    def __init__(
        self,
        config: ImageDescriberConfig,
        side_effects: list | None = None,
    ) -> None:
        super().__init__(config)
        self._side_effects = list(side_effects or [])
        self._call_count = 0

    def describe(self, image_path: str, context: ImageContext) -> str:
        if self._side_effects:
            effect = self._side_effects[self._call_count]
            self._call_count += 1
            if isinstance(effect, Exception):
                raise effect
            return effect
        return "test description"


def _make_config(**overrides) -> ImageDescriberConfig:
    defaults = {
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "api_key": "test-key",
    }
    defaults.update(overrides)
    return ImageDescriberConfig(**defaults)


# ---------------------------------------------------------------------------
# Tests: placeholder on failure
# ---------------------------------------------------------------------------


class TestPlaceholderOnFailure:
    """Test that describe_batch uses placeholder when describe() fails."""

    def test_single_failure_gets_placeholder(self) -> None:
        """A failing describe() call produces the placeholder description."""
        config = _make_config()
        describer = _FakeDescriber(
            config,
            side_effects=[
                ImageDescriptionError(
                    image_path="img.png", provider="anthropic"
                )
            ],
        )

        context = ImageContext(is_gliffy=False)
        results = describer.describe_batch([("img.png", context)])

        assert results["img.png"] == _PLACEHOLDER_DESCRIPTION

    def test_mixed_success_and_failure(self) -> None:
        """Successful and failed descriptions are handled independently."""
        config = _make_config()
        describer = _FakeDescriber(
            config,
            side_effects=[
                "good description",
                ImageDescriptionError(
                    image_path="bad.png", provider="anthropic"
                ),
                "another good one",
            ],
        )

        context = ImageContext(is_gliffy=False)
        images = [
            ("good.png", context),
            ("bad.png", context),
            ("also_good.png", context),
        ]
        results = describer.describe_batch(images)

        assert results["good.png"] == "good description"
        assert results["bad.png"] == _PLACEHOLDER_DESCRIPTION
        assert results["also_good.png"] == "another good one"


# ---------------------------------------------------------------------------
# Tests: retry on transient errors (Anthropic provider)
# ---------------------------------------------------------------------------


class TestAnthropicRetry:
    """Test retry behaviour of the Anthropic image describer."""

    def test_retry_on_rate_limit(self, tmp_path) -> None:
        """Transient 429 errors trigger retry with eventual success."""
        # Create a small test image
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        config = _make_config(provider="anthropic")

        # Mock the anthropic module
        mock_anthropic_mod = MagicMock()
        mock_client = MagicMock()

        # First call raises RateLimitError, second succeeds
        rate_limit_exc = type("RateLimitError", (Exception,), {
            "status_code": 429,
        })("rate limited")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="description after retry")]

        mock_client.messages.create.side_effect = [
            rate_limit_exc,
            mock_response,
        ]
        mock_anthropic_mod.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic_mod}):
            from confluence_exporter.providers.anthropic_describer import (
                AnthropicImageDescriber,
            )

            describer = AnthropicImageDescriber.__new__(AnthropicImageDescriber)
            describer._config = config
            describer._client = mock_client
            describer._anthropic_mod = mock_anthropic_mod

            with patch("confluence_exporter.providers.anthropic_describer.time.sleep"):
                result = describer.describe(
                    str(img_file), ImageContext(is_gliffy=False)
                )

        assert result == "description after retry"
        assert mock_client.messages.create.call_count == 2

    def test_non_retryable_error_raises_immediately(self, tmp_path) -> None:
        """Authentication errors (401) raise immediately without retry."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        config = _make_config(provider="anthropic")

        mock_anthropic_mod = MagicMock()
        mock_client = MagicMock()

        auth_exc = type("AuthenticationError", (Exception,), {
            "status_code": 401,
        })("invalid key")
        mock_client.messages.create.side_effect = auth_exc
        mock_anthropic_mod.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic_mod}):
            from confluence_exporter.providers.anthropic_describer import (
                AnthropicImageDescriber,
            )

            describer = AnthropicImageDescriber.__new__(AnthropicImageDescriber)
            describer._config = config
            describer._client = mock_client
            describer._anthropic_mod = mock_anthropic_mod

            with pytest.raises(ImageDescriptionError, match="Anthropic API error"):
                describer.describe(
                    str(img_file), ImageContext(is_gliffy=False)
                )

        # Should only attempt once — no retry
        assert mock_client.messages.create.call_count == 1


# ---------------------------------------------------------------------------
# Tests: retry on transient errors (OpenAI provider)
# ---------------------------------------------------------------------------


class TestOpenAIRetry:
    """Test retry behaviour of the OpenAI image describer."""

    def test_retry_on_server_error(self, tmp_path) -> None:
        """Transient 500 errors trigger retry with eventual success."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        config = _make_config(provider="openai", model="gpt-4o")

        mock_openai_mod = MagicMock()
        mock_client = MagicMock()

        server_exc = type("InternalServerError", (Exception,), {
            "status_code": 500,
        })("server error")
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="description after retry"))
        ]

        mock_client.chat.completions.create.side_effect = [
            server_exc,
            mock_response,
        ]
        mock_openai_mod.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_mod}):
            from confluence_exporter.providers.openai_describer import (
                OpenAIImageDescriber,
            )

            describer = OpenAIImageDescriber.__new__(OpenAIImageDescriber)
            describer._config = config
            describer._client = mock_client

            with patch("confluence_exporter.providers.openai_describer.time.sleep"):
                result = describer.describe(
                    str(img_file), ImageContext(is_gliffy=False)
                )

        assert result == "description after retry"
        assert mock_client.chat.completions.create.call_count == 2

    def test_non_retryable_error_raises_immediately(self, tmp_path) -> None:
        """Authentication errors raise immediately without retry."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        config = _make_config(provider="openai", model="gpt-4o")

        mock_openai_mod = MagicMock()
        mock_client = MagicMock()

        auth_exc = type("AuthenticationError", (Exception,), {
            "status_code": 401,
        })("invalid key")
        mock_client.chat.completions.create.side_effect = auth_exc
        mock_openai_mod.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_mod}):
            from confluence_exporter.providers.openai_describer import (
                OpenAIImageDescriber,
            )

            describer = OpenAIImageDescriber.__new__(OpenAIImageDescriber)
            describer._config = config
            describer._client = mock_client

            with pytest.raises(ImageDescriptionError, match="OpenAI API error"):
                describer.describe(
                    str(img_file), ImageContext(is_gliffy=False)
                )

        assert mock_client.chat.completions.create.call_count == 1


# ---------------------------------------------------------------------------
# Tests: --no-ai flag (describe_batch with empty list)
# ---------------------------------------------------------------------------


class TestNoAiFlag:
    """Test that --no-ai flag skips description generation."""

    def test_describe_batch_empty_list_returns_empty_dict(self) -> None:
        """describe_batch with empty list returns empty dict (--no-ai)."""
        config = _make_config()
        describer = _FakeDescriber(config)

        results = describer.describe_batch([])

        assert results == {}
