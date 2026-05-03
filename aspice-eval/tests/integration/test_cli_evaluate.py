"""Integration test for the full CLI evaluate pipeline using MockEvaluator.

Verifies that ``aspice-eval evaluate --provider mock --sdp examples/sample_sdp.md``
produces a valid report through the full CLI pipeline.

Requirements: 4.1, 6.1
"""

from __future__ import annotations

from click.testing import CliRunner

from aspice_eval.cli import main


class TestCLIEvaluateIntegration:
    """End-to-end tests for the evaluate command using the mock provider."""

    def test_evaluate_mock_produces_valid_report(self) -> None:
        """Full pipeline: mock provider + sample SDP → valid Markdown report."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "evaluate",
                "--provider", "mock",
                "--sdp", "examples/sample_sdp.md",
            ],
        )

        assert result.exit_code == 0, (
            f"CLI exited with code {result.exit_code}.\n"
            f"Output: {result.output}"
        )

        report = result.output

        # Verify all required report sections are present
        assert "# ASPICE Gap Analysis Report" in report
        assert "## Metadata" in report or "## 1. Metadata" in report
        assert "Executive Summary" in report
        assert "Capability Level Summary" in report
        assert "Detailed Findings" in report
        assert "Remediation Roadmap" in report
        assert "Traceability Matrix" in report

    def test_evaluate_mock_with_target_level(self) -> None:
        """Evaluate with a specific target level."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "evaluate",
                "--provider", "mock",
                "--sdp", "examples/sample_sdp.md",
                "--target-level", "2",
            ],
        )

        assert result.exit_code == 0, (
            f"CLI exited with code {result.exit_code}.\n"
            f"Output: {result.output}"
        )
        assert "ASPICE Gap Analysis Report" in result.output

    def test_evaluate_mock_with_specific_groups(self) -> None:
        """Evaluate with a subset of process groups."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "evaluate",
                "--provider", "mock",
                "--sdp", "examples/sample_sdp.md",
                "--groups", "SWE,MAN",
            ],
        )

        assert result.exit_code == 0, (
            f"CLI exited with code {result.exit_code}.\n"
            f"Output: {result.output}"
        )
        assert "ASPICE Gap Analysis Report" in result.output

    def test_evaluate_mock_with_output_file(self, tmp_path) -> None:
        """Evaluate and write report to a file."""
        output_file = tmp_path / "report.md"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "evaluate",
                "--provider", "mock",
                "--sdp", "examples/sample_sdp.md",
                "--output", str(output_file),
            ],
        )

        assert result.exit_code == 0, (
            f"CLI exited with code {result.exit_code}.\n"
            f"Output: {result.output}"
        )
        assert output_file.exists()
        content = output_file.read_text()
        assert "ASPICE Gap Analysis Report" in content

    def test_evaluate_unknown_provider_fails(self) -> None:
        """Unknown provider name should produce a configuration error."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "evaluate",
                "--provider", "nonexistent",
                "--sdp", "examples/sample_sdp.md",
            ],
        )

        assert result.exit_code != 0

    def test_evaluate_missing_sdp_fails(self) -> None:
        """Missing SDP file should produce an error."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "evaluate",
                "--provider", "mock",
                "--sdp", "nonexistent_file.md",
            ],
        )

        assert result.exit_code != 0

    def test_evaluate_default_provider_is_mock(self) -> None:
        """Without --provider flag, default should be mock."""
        runner = CliRunner()
        # Clear any env vars that might interfere
        result = runner.invoke(
            main,
            [
                "evaluate",
                "--sdp", "examples/sample_sdp.md",
            ],
            env={"ASPICE_EVAL_PROVIDER": ""},
        )

        # Should succeed with mock provider (empty string falls through to "mock")
        # or fail gracefully — the key is it doesn't crash with ImportError
        # When ASPICE_EVAL_PROVIDER is empty string, it's falsy so falls to "mock"
        assert result.exit_code == 0, (
            f"CLI exited with code {result.exit_code}.\n"
            f"Output: {result.output}"
        )
