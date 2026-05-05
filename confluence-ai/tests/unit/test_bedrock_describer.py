"""Unit tests for the Bedrock image describer provider.

Tests cover:
- Successful image description via Converse API
- Error mapping: ThrottlingException, AccessDeniedException, ModelNotFoundError
- Missing boto3 raises ImageDescriptionError
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from confluence_ai.exceptions import ImageDescriptionError
from confluence_ai.models import ImageContext, ImageDescriberConfig


def _make_config(**overrides) -> ImageDescriberConfig:
    defaults = {
        "provider": "bedrock",
        "model": "anthropic.claude-sonnet-4-20250514-v1:0",
        "region": "us-east-1",
    }
    defaults.update(overrides)
    return ImageDescriberConfig(**defaults)


class TestBedrockImageDescriber:
    """Tests for BedrockImageDescriber."""

    def test_successful_description(self, tmp_path) -> None:
        """Successful Converse API call returns description text."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "A process flow diagram"}]
                }
            }
        }

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            from confluence_ai.providers.bedrock_describer import (
                BedrockImageDescriber,
            )

            config = _make_config()
            describer = BedrockImageDescriber(config)
            result = describer.describe(
                str(img_file), ImageContext(is_gliffy=False)
            )

        assert result == "A process flow diagram"
        mock_client.converse.assert_called_once()

    def test_throttling_raises_error(self, tmp_path) -> None:
        """ThrottlingException maps to ImageDescriptionError."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        exc = Exception("rate limited")
        exc.response = {"Error": {"Code": "ThrottlingException"}}
        mock_client.converse.side_effect = exc

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            from confluence_ai.providers.bedrock_describer import (
                BedrockImageDescriber,
            )

            config = _make_config()
            describer = BedrockImageDescriber(config)

            with pytest.raises(ImageDescriptionError, match="rate limit"):
                describer.describe(
                    str(img_file), ImageContext(is_gliffy=False)
                )

    def test_access_denied_raises_error(self, tmp_path) -> None:
        """AccessDeniedException maps to ImageDescriptionError."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        exc = Exception("access denied")
        exc.response = {"Error": {"Code": "AccessDeniedException"}}
        mock_client.converse.side_effect = exc

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            from confluence_ai.providers.bedrock_describer import (
                BedrockImageDescriber,
            )

            config = _make_config()
            describer = BedrockImageDescriber(config)

            with pytest.raises(ImageDescriptionError, match="Access denied"):
                describer.describe(
                    str(img_file), ImageContext(is_gliffy=False)
                )

    def test_model_not_found_raises_error(self, tmp_path) -> None:
        """ModelNotFoundError maps to ImageDescriptionError."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        exc = Exception("model not found")
        exc.response = {"Error": {"Code": "ModelNotFoundError"}}
        mock_client.converse.side_effect = exc

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            from confluence_ai.providers.bedrock_describer import (
                BedrockImageDescriber,
            )

            config = _make_config()
            describer = BedrockImageDescriber(config)

            with pytest.raises(ImageDescriptionError, match="not found"):
                describer.describe(
                    str(img_file), ImageContext(is_gliffy=False)
                )

    def test_generic_error_raises_error(self, tmp_path) -> None:
        """Unknown errors map to generic Bedrock API error."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.converse.side_effect = RuntimeError("Network error")

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            from confluence_ai.providers.bedrock_describer import (
                BedrockImageDescriber,
            )

            config = _make_config()
            describer = BedrockImageDescriber(config)

            with pytest.raises(ImageDescriptionError, match="Bedrock API error"):
                describer.describe(
                    str(img_file), ImageContext(is_gliffy=False)
                )

    def test_gliffy_context_uses_gliffy_prompt(self, tmp_path) -> None:
        """Gliffy context triggers the process flow prompt."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "A swimlane diagram"}]
                }
            }
        }

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            from confluence_ai.providers.bedrock_describer import (
                BedrockImageDescriber,
            )

            config = _make_config()
            describer = BedrockImageDescriber(config)
            describer.describe(
                str(img_file), ImageContext(is_gliffy=True)
            )

        # Verify the prompt sent to Converse contains Gliffy keywords
        call_args = mock_client.converse.call_args
        messages = call_args[1]["messages"]
        text_content = messages[0]["content"][1]["text"]
        assert "swimlanes" in text_content or "decision points" in text_content


class TestBedrockProviderFactory:
    """Test that the provider factory resolves Bedrock."""

    def test_factory_resolves_bedrock(self) -> None:
        """create_describer returns BedrockImageDescriber for 'bedrock'."""
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = MagicMock()

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            from confluence_ai.providers import create_describer
            from confluence_ai.providers.bedrock_describer import (
                BedrockImageDescriber,
            )

            config = _make_config()
            describer = create_describer(config)
            assert isinstance(describer, BedrockImageDescriber)
