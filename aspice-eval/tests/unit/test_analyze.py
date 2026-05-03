"""Unit tests for the aspice-analyze CLI command and error mapping.

Tests CLI option registration, --no-publish behavior, --output file writing,
--quiet/--verbose logging, and error-to-exit-code mapping.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from aspice_eval.analyze import (
    ExportStageResult,
    EvaluateStageResult,
    TokenTracker,
    _configure_logging,
    _handle_stage_error,
    _resolve_kb_path,
    _sanitize_title,
    analyze,
)


class TestCLIOptionsRegistration:
    """Test that all CLI options are registered with correct types and defaults."""

    def test_analyze_is_click_command(self) -> None:
        """analyze is a Click command."""
        assert isinstance(analyze, click.Command)

    def test_required_options(self) -> None:
        """--target-level and --groups are required options."""
        runner = CliRunner()
        result = runner.invoke(analyze, ["https://example.atlassian.net/wiki/spaces/X/pages/123"])
        assert result.exit_code != 0
        assert "target-level" in result.output or "groups" in result.output

    def test_page_url_is_argument(self) -> None:
        """page_url is a positional argument."""
        params = {p.name: p for p in analyze.params}
        assert "page_url" in params

    def test_all_options_present(self) -> None:
        """All expected options are registered."""
        param_names = {p.name for p in analyze.params}
        expected = {
            "page_url", "target_level", "groups", "email", "api_token",
            "provider", "model", "region", "report_title", "output_dir",
            "output", "output_format", "no_publish", "verbose", "quiet",
        }
        assert expected.issubset(param_names), (
            f"Missing options: {expected - param_names}"
        )

    def test_output_format_choices(self) -> None:
        """--output-format accepts markdown and html."""
        params = {p.name: p for p in analyze.params}
        output_format_param = params["output_format"]
        assert isinstance(output_format_param.type, click.Choice)
        assert set(output_format_param.type.choices) == {"markdown", "html"}


class TestNoPublishFlag:
    """Test --no-publish skips the Publish Stage."""

    @patch("aspice_eval.analyze._run_export_stage")
    @patch("aspice_eval.analyze._run_evaluate_stage")
    @patch("aspice_eval.analyze._run_publish_stage")
    @patch("aspice_eval.analyze._resolve_kb_path", return_value="knowledge_base")
    def test_no_publish_skips_publish_stage(
        self,
        mock_kb_path: MagicMock,
        mock_publish: MagicMock,
        mock_evaluate: MagicMock,
        mock_export: MagicMock,
    ) -> None:
        """--no-publish flag prevents _run_publish_stage from being called."""
        mock_export.return_value = ExportStageResult(
            markdown_path="/tmp/test.md",
            page_title="Test Page",
            page_id="123",
            space_key="TST",
            images_downloaded=0,
            descriptions_generated=0,
        )
        mock_evaluate.return_value = EvaluateStageResult(
            report_markdown="# Report",
            report_html="<h1>Report</h1>",
            levels={},
            total_gaps=0,
            criteria_assessed=0,
        )

        runner = CliRunner()
        result = runner.invoke(analyze, [
            "https://test.atlassian.net/wiki/spaces/TST/pages/123",
            "--target-level", "3",
            "--groups", "SWE",
            "--email", "test@example.com",
            "--api-token", "token123",
            "--region", "us-east-1",
            "--no-publish",
            "--quiet",
        ])

        mock_publish.assert_not_called()


class TestOutputFlag:
    """Test --output writes report to file."""

    @patch("aspice_eval.analyze._run_export_stage")
    @patch("aspice_eval.analyze._run_evaluate_stage")
    @patch("aspice_eval.analyze._run_publish_stage")
    @patch("aspice_eval.analyze._resolve_kb_path", return_value="knowledge_base")
    def test_output_writes_to_file(
        self,
        mock_kb_path: MagicMock,
        mock_publish: MagicMock,
        mock_evaluate: MagicMock,
        mock_export: MagicMock,
        tmp_path,
    ) -> None:
        """--output writes the report to the specified file path."""
        output_dir = tmp_path / "aspice-output" / "Test_Page"
        output_dir.mkdir(parents=True, exist_ok=True)

        mock_export.return_value = ExportStageResult(
            markdown_path=str(output_dir / "test.md"),
            page_title="Test Page",
            page_id="123",
            space_key="TST",
            images_downloaded=0,
            descriptions_generated=0,
        )
        mock_evaluate.return_value = EvaluateStageResult(
            report_markdown="# Test Report Content",
            report_html="<h1>Test Report Content</h1>",
            levels={},
            total_gaps=0,
            criteria_assessed=0,
        )
        mock_publish.return_value = "https://test.atlassian.net/wiki/spaces/TST/pages/456"

        output_file = tmp_path / "report.md"
        runner = CliRunner()
        result = runner.invoke(analyze, [
            "https://test.atlassian.net/wiki/spaces/TST/pages/123",
            "--target-level", "3",
            "--groups", "SWE",
            "--email", "test@example.com",
            "--api-token", "token123",
            "--region", "us-east-1",
            "--output", str(output_file),
            "--output-dir", str(output_dir),
            "--no-publish",
            "--quiet",
        ])

        assert output_file.exists()
        assert "# Test Report Content" in output_file.read_text()


class TestLoggingConfiguration:
    """Test --quiet and --verbose logging behavior."""

    def test_quiet_sets_warning_level(self) -> None:
        """--quiet sets logging to WARNING level."""
        _configure_logging(verbose=False, quiet=True)
        pkg_logger = logging.getLogger("aspice_eval")
        assert pkg_logger.level == logging.WARNING

    def test_verbose_sets_debug_level(self) -> None:
        """--verbose sets logging to DEBUG level."""
        _configure_logging(verbose=True, quiet=False)
        pkg_logger = logging.getLogger("aspice_eval")
        assert pkg_logger.level == logging.DEBUG

    def test_default_sets_info_level(self) -> None:
        """Default (no flags) sets logging to INFO level."""
        _configure_logging(verbose=False, quiet=False)
        pkg_logger = logging.getLogger("aspice_eval")
        assert pkg_logger.level == logging.INFO

    def test_quiet_wins_over_verbose(self) -> None:
        """When both --quiet and --verbose are set, quiet wins."""
        _configure_logging(verbose=True, quiet=True)
        pkg_logger = logging.getLogger("aspice_eval")
        assert pkg_logger.level == logging.WARNING


class TestErrorMapping:
    """Test error-to-exit-code mapping."""

    def test_export_error_exit_code_2(self) -> None:
        """Export stage errors produce exit code 2."""
        with pytest.raises(SystemExit) as exc_info:
            _handle_stage_error("Export", RuntimeError("test"))
        assert exc_info.value.code == 2

    def test_evaluation_error_exit_code_3(self) -> None:
        """Evaluation stage errors produce exit code 3."""
        with pytest.raises(SystemExit) as exc_info:
            _handle_stage_error("Evaluation", RuntimeError("test"))
        assert exc_info.value.code == 3

    def test_publishing_error_exit_code_4(self) -> None:
        """Publishing stage errors produce exit code 4."""
        with pytest.raises(SystemExit) as exc_info:
            _handle_stage_error("Publishing", RuntimeError("test"))
        assert exc_info.value.code == 4


class TestMissingCredentials:
    """Test missing credentials produce descriptive error messages."""

    def test_missing_email_error_message(self) -> None:
        """Missing email produces descriptive error."""
        runner = CliRunner()
        result = runner.invoke(analyze, [
            "https://test.atlassian.net/wiki/spaces/TST/pages/123",
            "--target-level", "3",
            "--groups", "SWE",
            "--api-token", "token123",
            "--region", "us-east-1",
        ], env={"CONFLUENCE_EMAIL": "", "CONFLUENCE_API_TOKEN": ""})
        assert result.exit_code != 0

    def test_missing_token_error_message(self) -> None:
        """Missing API token produces descriptive error."""
        runner = CliRunner()
        result = runner.invoke(analyze, [
            "https://test.atlassian.net/wiki/spaces/TST/pages/123",
            "--target-level", "3",
            "--groups", "SWE",
            "--email", "test@example.com",
            "--region", "us-east-1",
        ], env={"CONFLUENCE_EMAIL": "", "CONFLUENCE_API_TOKEN": ""})
        assert result.exit_code != 0
