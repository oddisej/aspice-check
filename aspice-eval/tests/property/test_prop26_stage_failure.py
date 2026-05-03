"""Property test for stage failure identification in error messages.

**Validates: Requirements 10.5, 1.6**

Property 6: Stage failure identification in error messages.
For any pipeline stage that raises an exception, the error output
identifies which stage failed, and the command exits with a non-zero
exit code.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from aspice_eval.analyze import _handle_stage_error

# Stage names and their expected exit codes
_STAGE_EXIT_CODES = {
    "Export": 2,
    "Evaluation": 3,
    "Publishing": 4,
}


class TestProperty26StageFailure:
    """Feature: aspice-analyze-command, Property 6: stage failure identification."""

    @given(
        stage=st.sampled_from(list(_STAGE_EXIT_CODES.keys())),
        error_msg=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    )
    def test_nonzero_exit_code_per_stage(
        self, stage: str, error_msg: str,
    ) -> None:
        """Command exits with the correct non-zero exit code per stage."""
        exc = RuntimeError(error_msg)
        with pytest.raises(SystemExit) as exit_info:
            _handle_stage_error(stage, exc)

        expected_code = _STAGE_EXIT_CODES[stage]
        assert exit_info.value.code == expected_code, (
            f"Expected exit code {expected_code} for {stage}, "
            f"got {exit_info.value.code}"
        )

    def test_export_stage_name_in_error(self) -> None:
        """Export stage name appears in error output."""
        import click
        from click.testing import CliRunner

        @click.command()
        def _cmd() -> None:
            _handle_stage_error("Export", RuntimeError("test"))

        runner = CliRunner()
        result = runner.invoke(_cmd)
        assert "Export" in result.output

    def test_evaluation_stage_name_in_error(self) -> None:
        """Evaluation stage name appears in error output."""
        import click
        from click.testing import CliRunner

        @click.command()
        def _cmd() -> None:
            _handle_stage_error("Evaluation", RuntimeError("test"))

        runner = CliRunner()
        result = runner.invoke(_cmd)
        assert "Evaluation" in result.output

    def test_publishing_stage_name_in_error(self) -> None:
        """Publishing stage name appears in error output."""
        import click
        from click.testing import CliRunner

        @click.command()
        def _cmd() -> None:
            _handle_stage_error("Publishing", RuntimeError("test"))

        runner = CliRunner()
        result = runner.invoke(_cmd)
        assert "Publishing" in result.output

    def test_error_message_included(self) -> None:
        """Error output includes the original exception message."""
        import click
        from click.testing import CliRunner

        @click.command()
        def _cmd() -> None:
            _handle_stage_error("Export", RuntimeError("specific error detail"))

        runner = CliRunner()
        result = runner.invoke(_cmd)
        assert "specific error detail" in result.output
