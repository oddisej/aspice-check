"""Property test for credential resolution precedence.

**Validates: Requirements 2.5, 12.1, 12.2, 12.3, 12.4, 12.5**

Property 3: CLI option takes precedence over environment variable.
For any credential parameter where both CLI and env var are provided,
the resolved value equals the CLI value. When only the env var is set,
the resolved value equals the env var value.
"""

from __future__ import annotations

import os

import click
import pytest
from hypothesis import given
from hypothesis import strategies as st

from aspice_eval.analyze import _resolve_ai_config, _resolve_credentials

# Non-empty strings for credential values
_credential = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())


class TestProperty22CredentialResolution:
    """Feature: aspice-analyze-command, Property 3: credential resolution."""

    @given(cli_email=_credential, env_email=_credential)
    def test_cli_email_takes_precedence(
        self, cli_email: str, env_email: str,
    ) -> None:
        """CLI --email takes precedence over CONFLUENCE_EMAIL env var."""
        env = os.environ.copy()
        try:
            os.environ["CONFLUENCE_EMAIL"] = env_email
            os.environ["CONFLUENCE_API_TOKEN"] = "dummy-token"
            resolved_email, _ = _resolve_credentials(cli_email, "dummy-token")
            assert resolved_email == cli_email
        finally:
            os.environ.clear()
            os.environ.update(env)

    @given(env_email=_credential)
    def test_env_email_used_when_cli_absent(self, env_email: str) -> None:
        """CONFLUENCE_EMAIL env var is used when --email is not provided."""
        env = os.environ.copy()
        try:
            os.environ["CONFLUENCE_EMAIL"] = env_email
            os.environ["CONFLUENCE_API_TOKEN"] = "dummy-token"
            resolved_email, _ = _resolve_credentials(None, "dummy-token")
            assert resolved_email == env_email
        finally:
            os.environ.clear()
            os.environ.update(env)

    @given(cli_token=_credential, env_token=_credential)
    def test_cli_token_takes_precedence(
        self, cli_token: str, env_token: str,
    ) -> None:
        """CLI --api-token takes precedence over CONFLUENCE_API_TOKEN env var."""
        env = os.environ.copy()
        try:
            os.environ["CONFLUENCE_EMAIL"] = "user@example.com"
            os.environ["CONFLUENCE_API_TOKEN"] = env_token
            _, resolved_token = _resolve_credentials("user@example.com", cli_token)
            assert resolved_token == cli_token
        finally:
            os.environ.clear()
            os.environ.update(env)

    @given(env_token=_credential)
    def test_env_token_used_when_cli_absent(self, env_token: str) -> None:
        """CONFLUENCE_API_TOKEN env var is used when --api-token is not provided."""
        env = os.environ.copy()
        try:
            os.environ["CONFLUENCE_EMAIL"] = "user@example.com"
            os.environ["CONFLUENCE_API_TOKEN"] = env_token
            _, resolved_token = _resolve_credentials("user@example.com", None)
            assert resolved_token == env_token
        finally:
            os.environ.clear()
            os.environ.update(env)

    def test_missing_email_raises_usage_error(self) -> None:
        """Missing email from both CLI and env raises UsageError."""
        env = os.environ.copy()
        try:
            os.environ.pop("CONFLUENCE_EMAIL", None)
            with pytest.raises(click.UsageError, match="email"):
                _resolve_credentials(None, "token")
        finally:
            os.environ.clear()
            os.environ.update(env)

    def test_missing_token_raises_usage_error(self) -> None:
        """Missing API token from both CLI and env raises UsageError."""
        env = os.environ.copy()
        try:
            os.environ.pop("CONFLUENCE_API_TOKEN", None)
            with pytest.raises(click.UsageError, match="API token"):
                _resolve_credentials("user@example.com", None)
        finally:
            os.environ.clear()
            os.environ.update(env)

    @given(cli_provider=st.sampled_from(["bedrock", "openai", "anthropic"]))
    def test_cli_provider_takes_precedence(self, cli_provider: str) -> None:
        """CLI --provider takes precedence over ASPICE_EVAL_PROVIDER env var."""
        env = os.environ.copy()
        try:
            os.environ["ASPICE_EVAL_PROVIDER"] = "openai"
            os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
            resolved_provider, _, _ = _resolve_ai_config(cli_provider, None, "us-east-1")
            assert resolved_provider == cli_provider
        finally:
            os.environ.clear()
            os.environ.update(env)

    @given(env_provider=st.sampled_from(["bedrock", "openai", "anthropic"]))
    def test_env_provider_used_when_cli_absent(self, env_provider: str) -> None:
        """ASPICE_EVAL_PROVIDER env var is used when --provider is not provided."""
        env = os.environ.copy()
        try:
            os.environ["ASPICE_EVAL_PROVIDER"] = env_provider
            os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
            resolved_provider, _, _ = _resolve_ai_config(None, None, "us-east-1")
            assert resolved_provider == env_provider
        finally:
            os.environ.clear()
            os.environ.update(env)
