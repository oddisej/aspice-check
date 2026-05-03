"""Property test for TokenTracker accumulation correctness.

**Validates: Requirements 13.1, 13.3**

Property 7: Token tracker accumulation is correct.
For any combination of export-stage and evaluate-stage token counts,
``TokenTracker`` reports correct totals.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from aspice_eval.analyze import TokenTracker

# Non-negative integers for token counts
_token_count = st.integers(min_value=0, max_value=10_000_000)


class TestProperty21TokenTracker:
    """Feature: aspice-analyze-command, Property 7: token tracker accumulation."""

    @given(
        export_in=_token_count,
        export_out=_token_count,
        export_calls=_token_count,
        eval_in=_token_count,
        eval_out=_token_count,
        eval_calls=_token_count,
    )
    def test_total_input_tokens(
        self,
        export_in: int,
        export_out: int,
        export_calls: int,
        eval_in: int,
        eval_out: int,
        eval_calls: int,
    ) -> None:
        """total_input_tokens == export_input + eval_input."""
        tracker = TokenTracker(
            export_input_tokens=export_in,
            export_output_tokens=export_out,
            export_calls=export_calls,
            eval_input_tokens=eval_in,
            eval_output_tokens=eval_out,
            eval_calls=eval_calls,
        )
        assert tracker.total_input_tokens == export_in + eval_in

    @given(
        export_in=_token_count,
        export_out=_token_count,
        export_calls=_token_count,
        eval_in=_token_count,
        eval_out=_token_count,
        eval_calls=_token_count,
    )
    def test_total_output_tokens(
        self,
        export_in: int,
        export_out: int,
        export_calls: int,
        eval_in: int,
        eval_out: int,
        eval_calls: int,
    ) -> None:
        """total_output_tokens == export_output + eval_output."""
        tracker = TokenTracker(
            export_input_tokens=export_in,
            export_output_tokens=export_out,
            export_calls=export_calls,
            eval_input_tokens=eval_in,
            eval_output_tokens=eval_out,
            eval_calls=eval_calls,
        )
        assert tracker.total_output_tokens == export_out + eval_out

    @given(
        export_in=_token_count,
        export_out=_token_count,
        export_calls=_token_count,
        eval_in=_token_count,
        eval_out=_token_count,
        eval_calls=_token_count,
    )
    def test_total_tokens(
        self,
        export_in: int,
        export_out: int,
        export_calls: int,
        eval_in: int,
        eval_out: int,
        eval_calls: int,
    ) -> None:
        """total_tokens == total_input + total_output."""
        tracker = TokenTracker(
            export_input_tokens=export_in,
            export_output_tokens=export_out,
            export_calls=export_calls,
            eval_input_tokens=eval_in,
            eval_output_tokens=eval_out,
            eval_calls=eval_calls,
        )
        expected = export_in + export_out + eval_in + eval_out
        assert tracker.total_tokens == expected

    @given(
        export_in=_token_count,
        export_out=_token_count,
        export_calls=_token_count,
        eval_in=_token_count,
        eval_out=_token_count,
        eval_calls=_token_count,
    )
    def test_total_calls(
        self,
        export_in: int,
        export_out: int,
        export_calls: int,
        eval_in: int,
        eval_out: int,
        eval_calls: int,
    ) -> None:
        """total_calls == export_calls + eval_calls."""
        tracker = TokenTracker(
            export_input_tokens=export_in,
            export_output_tokens=export_out,
            export_calls=export_calls,
            eval_input_tokens=eval_in,
            eval_output_tokens=eval_out,
            eval_calls=eval_calls,
        )
        assert tracker.total_calls == export_calls + eval_calls
