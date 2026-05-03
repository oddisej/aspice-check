"""Unit tests for the AI provider factory and error mapping.

Tests cover:
- Factory resolves correct class for each provider name
- Factory raises InvalidConfigError for unknown providers
- Each provider maps API errors to AIModelError correctly
- Environment variable fallback for API keys and provider selection

Requirements: 4.1, 4.5
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from aspice_eval.exceptions import AIModelError, InvalidConfigError
from aspice_eval.models import ModelConfig
from aspice_eval.providers import create_evaluator


# ---------------------------------------------------------------------------
# Factory resolution tests
# ---------------------------------------------------------------------------


class TestProviderFactory:
    """Test that the factory resolves the correct evaluator class."""

    def test_factory_resolves_mock(self) -> None:
        config = ModelConfig(provider="mock")
        evaluator = create_evaluator(config)
        from aspice_eval.evaluator import MockEvaluator

        assert isinstance(evaluator, MockEvaluator)

    def test_factory_resolves_bedrock(self) -> None:
        """Bedrock evaluator requires boto3 — mock the import."""
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            config = ModelConfig(
                provider="bedrock",
                model_name="anthropic.claude-3-haiku-20240307-v1:0",
                region="us-west-2",
            )
            evaluator = create_evaluator(config)
            from aspice_eval.providers.bedrock import BedrockEvaluator

            assert isinstance(evaluator, BedrockEvaluator)

    def test_factory_resolves_openai(self) -> None:
        """OpenAI evaluator requires openai — mock the import."""
        mock_openai_mod = MagicMock()
        mock_client_cls = MagicMock()
        mock_openai_mod.OpenAI = mock_client_cls

        with patch.dict("sys.modules", {"openai": mock_openai_mod}):
            config = ModelConfig(
                provider="openai",
                model_name="gpt-4o",
                api_key="sk-test-key",
            )
            evaluator = create_evaluator(config)
            from aspice_eval.providers.openai_provider import OpenAIEvaluator

            assert isinstance(evaluator, OpenAIEvaluator)

    def test_factory_resolves_anthropic(self) -> None:
        """Anthropic evaluator requires anthropic — mock the import."""
        mock_anthropic_mod = MagicMock()
        mock_client_cls = MagicMock()
        mock_anthropic_mod.Anthropic = mock_client_cls

        with patch.dict("sys.modules", {"anthropic": mock_anthropic_mod}):
            config = ModelConfig(
                provider="anthropic",
                model_name="claude-sonnet-4-20250514",
                api_key="sk-ant-test",
            )
            evaluator = create_evaluator(config)
            from aspice_eval.providers.anthropic_provider import (
                AnthropicEvaluator,
            )

            assert isinstance(evaluator, AnthropicEvaluator)

    def test_factory_raises_for_unknown_provider(self) -> None:
        config = ModelConfig(provider="unknown-provider")
        with pytest.raises(InvalidConfigError, match="Unknown provider"):
            create_evaluator(config)

    def test_factory_raises_for_empty_provider(self) -> None:
        config = ModelConfig(provider="")
        with pytest.raises(InvalidConfigError, match="Unknown provider"):
            create_evaluator(config)


# ---------------------------------------------------------------------------
# Bedrock error mapping tests
# ---------------------------------------------------------------------------


class TestBedrockErrorMapping:
    """Test that Bedrock provider maps boto3 errors to AIModelError."""

    def _make_evaluator(self, mock_boto3: MagicMock) -> object:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            from aspice_eval.providers.bedrock import BedrockEvaluator

            config = ModelConfig(
                provider="bedrock",
                model_name="test-model",
                region="us-east-1",
            )
            evaluator = BedrockEvaluator(config)
        return evaluator, mock_client

    def test_throttling_maps_to_ai_model_error(self) -> None:
        mock_boto3 = MagicMock()
        evaluator, mock_client = self._make_evaluator(mock_boto3)

        exc = Exception("Throttled")
        exc.response = {"Error": {"Code": "ThrottlingException"}}
        mock_client.converse.side_effect = exc

        with pytest.raises(AIModelError, match="rate limit"):
            evaluator._call_model("test prompt")

    def test_access_denied_maps_to_ai_model_error(self) -> None:
        mock_boto3 = MagicMock()
        evaluator, mock_client = self._make_evaluator(mock_boto3)

        exc = Exception("Access denied")
        exc.response = {"Error": {"Code": "AccessDeniedException"}}
        mock_client.converse.side_effect = exc

        with pytest.raises(AIModelError, match="Access denied"):
            evaluator._call_model("test prompt")

    def test_model_not_found_maps_to_ai_model_error(self) -> None:
        mock_boto3 = MagicMock()
        evaluator, mock_client = self._make_evaluator(mock_boto3)

        exc = Exception("Model not found")
        exc.response = {"Error": {"Code": "ModelNotFoundError"}}
        mock_client.converse.side_effect = exc

        with pytest.raises(AIModelError, match="not found"):
            evaluator._call_model("test prompt")

    def test_generic_error_maps_to_ai_model_error(self) -> None:
        mock_boto3 = MagicMock()
        evaluator, mock_client = self._make_evaluator(mock_boto3)

        mock_client.converse.side_effect = RuntimeError("Network error")

        with pytest.raises(AIModelError, match="Bedrock API error"):
            evaluator._call_model("test prompt")


# ---------------------------------------------------------------------------
# OpenAI error mapping tests
# ---------------------------------------------------------------------------


class TestOpenAIErrorMapping:
    """Test that OpenAI provider maps openai errors to AIModelError."""

    def _make_evaluator(self) -> tuple:
        mock_openai_mod = MagicMock()
        mock_client = MagicMock()
        mock_openai_mod.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_mod}):
            from aspice_eval.providers.openai_provider import OpenAIEvaluator

            config = ModelConfig(
                provider="openai",
                model_name="gpt-4o",
                api_key="sk-test",
            )
            evaluator = OpenAIEvaluator(config)
        return evaluator, mock_client

    def test_auth_error_maps_to_ai_model_error(self) -> None:
        evaluator, mock_client = self._make_evaluator()

        # Create an exception whose type name contains "AuthenticationError"
        exc_cls = type("AuthenticationError", (Exception,), {})
        mock_client.chat.completions.create.side_effect = exc_cls("Bad key")

        with pytest.raises(AIModelError, match="authentication failed"):
            evaluator._call_model("test prompt")

    def test_rate_limit_maps_to_ai_model_error(self) -> None:
        evaluator, mock_client = self._make_evaluator()

        exc_cls = type("RateLimitError", (Exception,), {})
        mock_client.chat.completions.create.side_effect = exc_cls("Too many")

        with pytest.raises(AIModelError, match="rate limit"):
            evaluator._call_model("test prompt")

    def test_generic_error_maps_to_ai_model_error(self) -> None:
        evaluator, mock_client = self._make_evaluator()

        mock_client.chat.completions.create.side_effect = RuntimeError(
            "Connection failed"
        )

        with pytest.raises(AIModelError, match="OpenAI API error"):
            evaluator._call_model("test prompt")


# ---------------------------------------------------------------------------
# Anthropic error mapping tests
# ---------------------------------------------------------------------------


class TestAnthropicErrorMapping:
    """Test that Anthropic provider maps anthropic errors to AIModelError."""

    def _make_evaluator(self) -> tuple:
        mock_anthropic_mod = MagicMock()
        mock_client = MagicMock()
        mock_anthropic_mod.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic_mod}):
            from aspice_eval.providers.anthropic_provider import (
                AnthropicEvaluator,
            )

            config = ModelConfig(
                provider="anthropic",
                model_name="claude-sonnet-4-20250514",
                api_key="sk-ant-test",
            )
            evaluator = AnthropicEvaluator(config)
        return evaluator, mock_client

    def test_auth_error_maps_to_ai_model_error(self) -> None:
        evaluator, mock_client = self._make_evaluator()

        exc_cls = type("AuthenticationError", (Exception,), {})
        mock_client.messages.create.side_effect = exc_cls("Bad key")

        with pytest.raises(AIModelError, match="authentication failed"):
            evaluator._call_model("test prompt")

    def test_rate_limit_maps_to_ai_model_error(self) -> None:
        evaluator, mock_client = self._make_evaluator()

        exc_cls = type("RateLimitError", (Exception,), {})
        mock_client.messages.create.side_effect = exc_cls("Too many")

        with pytest.raises(AIModelError, match="rate limit"):
            evaluator._call_model("test prompt")

    def test_generic_error_maps_to_ai_model_error(self) -> None:
        evaluator, mock_client = self._make_evaluator()

        mock_client.messages.create.side_effect = RuntimeError(
            "Connection failed"
        )

        with pytest.raises(AIModelError, match="Anthropic API error"):
            evaluator._call_model("test prompt")


# ---------------------------------------------------------------------------
# Environment variable fallback tests
# ---------------------------------------------------------------------------


class TestEnvVarFallback:
    """Test environment variable fallback for API keys and provider selection."""

    def test_openai_uses_env_var_when_no_api_key(self) -> None:
        """OpenAI provider falls back to OPENAI_API_KEY env var."""
        mock_openai_mod = MagicMock()
        mock_client_cls = MagicMock()
        mock_openai_mod.OpenAI = mock_client_cls

        with (
            patch.dict("sys.modules", {"openai": mock_openai_mod}),
            patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-key"}),
        ):
            from aspice_eval.providers.openai_provider import OpenAIEvaluator

            config = ModelConfig(
                provider="openai",
                model_name="gpt-4o",
                api_key=None,
            )
            OpenAIEvaluator(config)

            # The OpenAI client should have been created with the env key
            mock_client_cls.assert_called_once_with(api_key="sk-env-key")

    def test_openai_prefers_config_api_key_over_env(self) -> None:
        """Config api_key takes precedence over env var."""
        mock_openai_mod = MagicMock()
        mock_client_cls = MagicMock()
        mock_openai_mod.OpenAI = mock_client_cls

        with (
            patch.dict("sys.modules", {"openai": mock_openai_mod}),
            patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-key"}),
        ):
            from aspice_eval.providers.openai_provider import OpenAIEvaluator

            config = ModelConfig(
                provider="openai",
                model_name="gpt-4o",
                api_key="sk-config-key",
            )
            OpenAIEvaluator(config)

            mock_client_cls.assert_called_once_with(api_key="sk-config-key")

    def test_anthropic_uses_env_var_when_no_api_key(self) -> None:
        """Anthropic provider falls back to ANTHROPIC_API_KEY env var."""
        mock_anthropic_mod = MagicMock()
        mock_client_cls = MagicMock()
        mock_anthropic_mod.Anthropic = mock_client_cls

        with (
            patch.dict("sys.modules", {"anthropic": mock_anthropic_mod}),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-env"}),
        ):
            from aspice_eval.providers.anthropic_provider import (
                AnthropicEvaluator,
            )

            config = ModelConfig(
                provider="anthropic",
                model_name="claude-sonnet-4-20250514",
                api_key=None,
            )
            AnthropicEvaluator(config)

            mock_client_cls.assert_called_once_with(api_key="sk-ant-env")

    def test_anthropic_prefers_config_api_key_over_env(self) -> None:
        """Config api_key takes precedence over env var."""
        mock_anthropic_mod = MagicMock()
        mock_client_cls = MagicMock()
        mock_anthropic_mod.Anthropic = mock_client_cls

        with (
            patch.dict("sys.modules", {"anthropic": mock_anthropic_mod}),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-env"}),
        ):
            from aspice_eval.providers.anthropic_provider import (
                AnthropicEvaluator,
            )

            config = ModelConfig(
                provider="anthropic",
                model_name="claude-sonnet-4-20250514",
                api_key="sk-ant-config",
            )
            AnthropicEvaluator(config)

            mock_client_cls.assert_called_once_with(api_key="sk-ant-config")

    def test_cli_provider_env_var_fallback(self) -> None:
        """CLI resolves provider from ASPICE_EVAL_PROVIDER env var."""
        from click.testing import CliRunner

        from aspice_eval.cli import main

        runner = CliRunner()

        # Use an invalid provider to verify the env var is being read
        env = {"ASPICE_EVAL_PROVIDER": "nonexistent"}
        result = runner.invoke(
            main,
            ["evaluate", "--sdp", "examples/sample_sdp.md"],
            env=env,
        )
        # Should fail with configuration error about unknown provider
        assert result.exit_code != 0
        assert "Configuration error" in result.output or "Unknown provider" in (
            result.output + (result.stderr if hasattr(result, "stderr") else "")
        )
