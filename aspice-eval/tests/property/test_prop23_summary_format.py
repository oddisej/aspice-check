"""Property test for pipeline summary format completeness.

**Validates: Requirements 1.5, 13.4**

Property 2: Pipeline summary contains all required fields.
For any combination of page URL, capability levels, gap counts,
output directory, and token usage, the formatted summary contains
all required fields.
"""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import given
from hypothesis import strategies as st

from aspice_eval.analyze import TokenTracker, _format_summary

# Strategies
_url = st.from_regex(r"https://[a-z]+\.atlassian\.net/wiki/spaces/[A-Z]+/pages/[0-9]+", fullmatch=True)
_group_code = st.sampled_from(["SWE", "SYS", "MAN", "SUP"])
_level = st.integers(min_value=0, max_value=5)
_gap_count = st.integers(min_value=0, max_value=1000)
_dir_path = st.from_regex(r"\./aspice-output/[a-zA-Z0-9_]+", fullmatch=True)
_token_count = st.integers(min_value=0, max_value=10_000_000)
_provider = st.sampled_from(["bedrock", "openai", "anthropic"])
_model = st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz0123456789.-")
_region = st.sampled_from(["us-east-1", "eu-west-1", "ap-southeast-1", ""])


@dataclass
class _FakeCapabilityResult:
    """Minimal stand-in for CapabilityLevelResult."""

    achieved_level: int
    target_level: int


class TestProperty23SummaryFormat:
    """Feature: aspice-analyze-command, Property 2: summary format completeness."""

    @given(
        page_url=_url,
        groups=st.lists(_group_code, min_size=1, max_size=4, unique=True),
        achieved_levels=st.lists(_level, min_size=1, max_size=4),
        target_level=_level,
        total_gaps=_gap_count,
        output_dir=_dir_path,
        export_in=_token_count,
        export_out=_token_count,
        export_calls=st.integers(min_value=0, max_value=100),
        eval_in=_token_count,
        eval_out=_token_count,
        eval_calls=st.integers(min_value=0, max_value=100),
        provider=_provider,
        model=_model,
        region=_region,
    )
    def test_summary_contains_all_required_fields(
        self,
        page_url: str,
        groups: list[str],
        achieved_levels: list[int],
        target_level: int,
        total_gaps: int,
        output_dir: str,
        export_in: int,
        export_out: int,
        export_calls: int,
        eval_in: int,
        eval_out: int,
        eval_calls: int,
        provider: str,
        model: str,
        region: str,
    ) -> None:
        """Summary contains page URL, group levels, gaps, dir, and tokens."""
        # Build levels dict matching the number of groups
        levels = {}
        for i, group in enumerate(groups):
            achieved = achieved_levels[i % len(achieved_levels)]
            levels[group] = _FakeCapabilityResult(
                achieved_level=achieved,
                target_level=target_level,
            )

        tracker = TokenTracker(
            export_input_tokens=export_in,
            export_output_tokens=export_out,
            export_calls=export_calls,
            eval_input_tokens=eval_in,
            eval_output_tokens=eval_out,
            eval_calls=eval_calls,
        )

        summary = _format_summary(
            page_url=page_url,
            levels=levels,
            total_gaps=total_gaps,
            output_dir=output_dir,
            token_tracker=tracker,
            provider=provider,
            model=model,
            region=region,
        )

        # Verify all required fields are present
        assert page_url in summary, "Page URL missing from summary"
        for group in groups:
            assert group in summary, f"Group {group} missing from summary"
        assert str(total_gaps) in summary, "Gap count missing from summary"
        assert output_dir in summary, "Output directory missing from summary"
        assert str(tracker.total_tokens) in summary or f"{tracker.total_tokens:,}" in summary, \
            "Total token usage missing from summary"

    @given(
        groups=st.lists(_group_code, min_size=1, max_size=4, unique=True),
        target_level=_level,
        total_gaps=_gap_count,
        output_dir=_dir_path,
    )
    def test_summary_without_page_url(
        self,
        groups: list[str],
        target_level: int,
        total_gaps: int,
        output_dir: str,
    ) -> None:
        """Summary works when page_url is None (--no-publish)."""
        levels = {
            g: _FakeCapabilityResult(achieved_level=2, target_level=target_level)
            for g in groups
        }
        tracker = TokenTracker()

        summary = _format_summary(
            page_url=None,
            levels=levels,
            total_gaps=total_gaps,
            output_dir=output_dir,
            token_tracker=tracker,
            provider="bedrock",
            model="test-model",
            region="us-east-1",
        )

        assert "Published page:" not in summary
        assert str(total_gaps) in summary
        assert output_dir in summary
