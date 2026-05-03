"""Unit tests for the CLI entry point.

Tests required argument validation, flag behavior, exit codes,
and environment variable fallback for credentials and AI config.

Requirements: 7.1, 7.2, 7.5, 7.6, 9.4
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from confluence_exporter.cli import main, sanitize_title
from confluence_exporter.exceptions import (
    AuthenticationError,
    ConfluenceConnectionError,
    InvalidURLError,
    PageNotFoundError,
    ParseError,
)
from confluence_exporter.models import AttachmentData, PageData


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_VALID_URL = "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456/My+Page"
_OUTPUT_DIR = "/tmp/test_export_output"


def _make_page_data() -> PageData:
    return PageData(
        page_id="123456",
        title="My Page",
        storage_format="<p>Hello world</p>",
        version=1,
        labels=["label1"],
        space_key="ENG",
    )


def _make_runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


class TestArgumentValidation:
    """Test required argument validation and usage messages."""

    def test_missing_all_args_shows_usage(self) -> None:
        """Missing arguments produce a usage message and non-zero exit."""
        runner = _make_runner()
        result = runner.invoke(main, [])
        assert result.exit_code != 0
        # Click outputs usage/error info to output
        assert "Usage" in result.output or "Missing" in result.output or "Error" in result.output

    def test_missing_output_dir_shows_usage(self) -> None:
        """Missing output_dir produces a usage message and non-zero exit."""
        runner = _make_runner()
        result = runner.invoke(main, [_VALID_URL])
        assert result.exit_code != 0

    def test_missing_email_shows_error(self) -> None:
        """Missing email credential produces an error."""
        runner = _make_runner()
        result = runner.invoke(main, [_VALID_URL, _OUTPUT_DIR])
        assert result.exit_code != 0
        assert "email" in result.output.lower()


# ---------------------------------------------------------------------------
# --no-ai flag
# ---------------------------------------------------------------------------


class TestNoAiFlag:
    """Test that --no-ai skips AI description generation."""

    @patch("confluence_exporter.cli.ConfluenceClient")
    @patch("confluence_exporter.cli.create_describer")
    def test_no_ai_skips_description(
        self,
        mock_create_describer: MagicMock,
        mock_client_cls: MagicMock,
    ) -> None:
        """With --no-ai, the describer factory is never called."""
        # Set up mocks
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_page.return_value = _make_page_data()
        mock_client.get_attachments.return_value = []

        runner = _make_runner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                main,
                [
                    _VALID_URL,
                    "output",
                    "--email",
                    "user@example.com",
                    "--api-token",
                    "token123",
                    "--no-ai",
                ],
            )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        mock_create_describer.assert_not_called()


# ---------------------------------------------------------------------------
# --verbose flag
# ---------------------------------------------------------------------------


class TestVerboseFlag:
    """Test that --verbose sets DEBUG logging."""

    @patch("confluence_exporter.cli.ConfluenceClient")
    def test_verbose_sets_debug_logging(
        self,
        mock_client_cls: MagicMock,
    ) -> None:
        """With --verbose, the package logger is set to DEBUG."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_page.return_value = _make_page_data()
        mock_client.get_attachments.return_value = []

        runner = _make_runner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                main,
                [
                    _VALID_URL,
                    "output",
                    "--email",
                    "user@example.com",
                    "--api-token",
                    "token123",
                    "--no-ai",
                    "--verbose",
                ],
            )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        pkg_logger = logging.getLogger("confluence_exporter")
        assert pkg_logger.level == logging.DEBUG


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


class TestExitCodes:
    """Test exit code 0 on success and non-zero on failure."""

    @patch("confluence_exporter.cli.ConfluenceClient")
    def test_exit_code_0_on_success(
        self,
        mock_client_cls: MagicMock,
    ) -> None:
        """Successful export returns exit code 0."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_page.return_value = _make_page_data()
        mock_client.get_attachments.return_value = []

        runner = _make_runner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                main,
                [
                    _VALID_URL,
                    "output",
                    "--email",
                    "user@example.com",
                    "--api-token",
                    "token123",
                    "--no-ai",
                ],
            )

        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

    @patch("confluence_exporter.cli.URLParser")
    def test_exit_code_nonzero_on_invalid_url(
        self,
        mock_parser_cls: MagicMock,
    ) -> None:
        """Invalid URL produces non-zero exit code."""
        mock_parser_cls.return_value.parse.side_effect = InvalidURLError("bad-url")

        runner = _make_runner()
        result = runner.invoke(
            main,
            [
                "bad-url",
                "output",
                "--email",
                "user@example.com",
                "--api-token",
                "token123",
            ],
        )
        assert result.exit_code != 0

    @patch("confluence_exporter.cli.ConfluenceClient")
    def test_exit_code_nonzero_on_auth_error(
        self,
        mock_client_cls: MagicMock,
    ) -> None:
        """Authentication failure produces non-zero exit code."""
        mock_client_cls.side_effect = AuthenticationError(
            base_url="https://acme.atlassian.net/wiki",
            status_code=401,
        )

        runner = _make_runner()
        result = runner.invoke(
            main,
            [
                _VALID_URL,
                "output",
                "--email",
                "user@example.com",
                "--api-token",
                "bad-token",
            ],
        )
        assert result.exit_code != 0

    @patch("confluence_exporter.cli.ConfluenceClient")
    def test_exit_code_nonzero_on_page_not_found(
        self,
        mock_client_cls: MagicMock,
    ) -> None:
        """Page not found produces non-zero exit code."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_page.side_effect = PageNotFoundError(
            page_id="123456", status_code=404
        )

        runner = _make_runner()
        result = runner.invoke(
            main,
            [
                _VALID_URL,
                "output",
                "--email",
                "user@example.com",
                "--api-token",
                "token123",
            ],
        )
        assert result.exit_code != 0

    @patch("confluence_exporter.cli.ConfluenceClient")
    def test_exit_code_nonzero_on_connection_error(
        self,
        mock_client_cls: MagicMock,
    ) -> None:
        """Connection error produces non-zero exit code."""
        mock_client_cls.side_effect = ConfluenceConnectionError(
            base_url="https://acme.atlassian.net/wiki"
        )

        runner = _make_runner()
        result = runner.invoke(
            main,
            [
                _VALID_URL,
                "output",
                "--email",
                "user@example.com",
                "--api-token",
                "token123",
            ],
        )
        assert result.exit_code != 0

    @patch("confluence_exporter.cli.ConfluenceClient")
    def test_exit_code_nonzero_on_parse_error(
        self,
        mock_client_cls: MagicMock,
    ) -> None:
        """Parse error produces non-zero exit code."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_page.return_value = PageData(
            page_id="123456",
            title="Bad Page",
            storage_format="<<<not xml>>>",
            version=1,
        )
        mock_client.get_attachments.return_value = []

        runner = _make_runner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                main,
                [
                    _VALID_URL,
                    "output",
                    "--email",
                    "user@example.com",
                    "--api-token",
                    "token123",
                    "--no-ai",
                ],
            )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Environment variable fallback
# ---------------------------------------------------------------------------


class TestEnvVarFallback:
    """Test environment variable fallback for credentials and AI config."""

    @patch("confluence_exporter.cli.ConfluenceClient")
    def test_email_from_env(
        self,
        mock_client_cls: MagicMock,
    ) -> None:
        """Email is read from CONFLUENCE_EMAIL env var."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_page.return_value = _make_page_data()
        mock_client.get_attachments.return_value = []

        runner = _make_runner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                main,
                [
                    _VALID_URL,
                    "output",
                    "--api-token",
                    "token123",
                    "--no-ai",
                ],
                env={"CONFLUENCE_EMAIL": "env@example.com"},
            )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        # Verify the client was constructed with the env email
        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args
        assert call_kwargs[1].get("email") == "env@example.com" or (
            len(call_kwargs[0]) > 1 and call_kwargs[0][1] == "env@example.com"
        )

    @patch("confluence_exporter.cli.ConfluenceClient")
    def test_api_token_from_env(
        self,
        mock_client_cls: MagicMock,
    ) -> None:
        """API token is read from CONFLUENCE_API_TOKEN env var."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_page.return_value = _make_page_data()
        mock_client.get_attachments.return_value = []

        runner = _make_runner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                main,
                [
                    _VALID_URL,
                    "output",
                    "--email",
                    "user@example.com",
                    "--no-ai",
                ],
                env={"CONFLUENCE_API_TOKEN": "env_token_123"},
            )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args
        assert call_kwargs[1].get("api_token") == "env_token_123" or (
            len(call_kwargs[0]) > 2 and call_kwargs[0][2] == "env_token_123"
        )

    @patch("confluence_exporter.cli.ConfluenceClient")
    @patch("confluence_exporter.cli.create_describer")
    def test_ai_provider_from_env(
        self,
        mock_create_describer: MagicMock,
        mock_client_cls: MagicMock,
    ) -> None:
        """AI provider is read from CONFLUENCE_EXPORT_AI_PROVIDER env var."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_page.return_value = _make_page_data()
        mock_client.get_attachments.return_value = []

        mock_describer = MagicMock()
        mock_describer.describe_batch.return_value = {}
        mock_create_describer.return_value = mock_describer

        runner = _make_runner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                main,
                [
                    _VALID_URL,
                    "output",
                    "--email",
                    "user@example.com",
                    "--api-token",
                    "token123",
                ],
                env={
                    "CONFLUENCE_EXPORT_AI_PROVIDER": "anthropic",
                    "ANTHROPIC_API_KEY": "test-key",
                },
            )

        assert result.exit_code == 0, f"CLI failed: {result.output}"


# ---------------------------------------------------------------------------
# sanitize_title
# ---------------------------------------------------------------------------


class TestSanitizeTitle:
    """Test the title sanitization helper."""

    def test_spaces_to_underscores(self) -> None:
        assert sanitize_title("My Page Title") == "My_Page_Title"

    def test_special_chars_removed(self) -> None:
        assert sanitize_title("Page (v2.0) — Final!") == "Page_v20__Final"

    def test_empty_title_fallback(self) -> None:
        assert sanitize_title("") == "untitled"

    def test_only_special_chars_fallback(self) -> None:
        assert sanitize_title("@#$%") == "untitled"

    def test_preserves_hyphens(self) -> None:
        assert sanitize_title("my-page") == "my-page"

    def test_preserves_underscores(self) -> None:
        assert sanitize_title("my_page") == "my_page"
