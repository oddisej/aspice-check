"""Property 13: Report contains sections only for specified process groups.

Generate random group subsets; verify Detailed Findings contains subsections
only for the specified groups and not for omitted groups.

**Validates: Requirements 7.2**
"""

from __future__ import annotations

from hypothesis import given, assume, strategies as st

from aspice_eval.level_calculator import CapabilityLevelCalculator
from aspice_eval.models import (
    VALID_RATINGS,
    CapabilityLevelResult,
    CriteriaRating,
    EvaluationConfig,
    EvaluationResult,
    KBMetadata,
)
from aspice_eval.report_generator import ReportGenerator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALL_GROUPS = ["SWE", "SYS", "MAN", "SUP"]

_PROCESS_ATTRIBUTES = [f"PA {lvl}.{sub}" for lvl in range(1, 6) for sub in (1, 2)]

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_valid_ratings_st = st.sampled_from(sorted(VALID_RATINGS))
_target_level_st = st.integers(min_value=1, max_value=5)

# Generate a strict subset of groups so there are always omitted groups
_process_groups_st = st.lists(
    st.sampled_from(ALL_GROUPS), min_size=1, max_size=4, unique=True,
)


@st.composite
def _scoping_scenario_st(draw: st.DrawFn) -> tuple[
    EvaluationResult,
    dict[str, CapabilityLevelResult],
    EvaluationConfig,
    KBMetadata,
    list[str],
    list[str],
]:
    """Generate a scenario with specified groups and return both included and omitted groups."""
    included_groups = draw(_process_groups_st)
    omitted_groups = [g for g in ALL_GROUPS if g not in included_groups]
    target_level = draw(_target_level_st)

    config = EvaluationConfig(
        sdp_path="test.md",
        target_capability_level=target_level,
        process_groups=included_groups,
    )

    # Generate ratings only for included groups
    ratings: list[CriteriaRating] = []
    for group in included_groups:
        num_ratings = draw(st.integers(min_value=1, max_value=3))
        for i in range(num_ratings):
            pa = draw(st.sampled_from(_PROCESS_ATTRIBUTES))
            level = int(pa.split()[1].split(".")[0])
            rating_val = draw(_valid_ratings_st)

            gaps: list[str] = []
            recommendations: list[str] = []
            if rating_val in ("Partially achieved", "Not achieved"):
                gaps = [f"Gap {group}-{i}"]
                recommendations = [f"Fix {group}-{i}"]

            ratings.append(
                CriteriaRating(
                    criteria_id=f"{group}.1-{pa.replace(' ', '')}-{i + 1:03d}",
                    process_group=group,
                    process_attribute=pa,
                    capability_level=level,
                    rating=rating_val,
                    gaps=gaps,
                    recommendations=recommendations,
                )
            )

    evaluation = EvaluationResult(
        ratings=ratings,
        sdp_metadata={},
        evaluation_timestamp="2025-01-15T00:00:00Z",
        config=config,
    )

    calc = CapabilityLevelCalculator(target_level=target_level)
    levels = calc.calculate(ratings, included_groups)

    kb_metadata = KBMetadata(
        standard_name="Automotive SPICE",
        short_name="ASPICE",
        version="4.0",
        release_date="2023-12",
        source_references=[],
        license_note="Test",
        kb_version="1.0.0",
        last_updated="2025-01-15",
        process_groups=[],
        capability_levels=[],
        rating_scale=[],
    )

    return evaluation, levels, config, kb_metadata, included_groups, omitted_groups


def _extract_detailed_findings(report: str) -> str:
    """Extract the Detailed Findings section from the report."""
    start = report.index("## Detailed Findings")
    # Find the next ## section after Detailed Findings
    rest = report[start + len("## Detailed Findings"):]
    next_section = rest.find("\n## ")
    if next_section == -1:
        return report[start:]
    return report[start : start + len("## Detailed Findings") + next_section]


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestProperty13ReportScoping:
    """Property 13: Report contains sections only for specified process groups."""

    @given(data=_scoping_scenario_st())
    def test_detailed_findings_contains_specified_groups(
        self,
        data: tuple[
            EvaluationResult,
            dict[str, CapabilityLevelResult],
            EvaluationConfig,
            KBMetadata,
            list[str],
            list[str],
        ],
    ) -> None:
        """Detailed Findings SHALL contain subsections for all specified groups."""
        evaluation, levels, config, kb_metadata, included_groups, _ = data

        generator = ReportGenerator()
        report = generator.generate(evaluation, levels, config, kb_metadata)

        detailed = _extract_detailed_findings(report)

        for group in included_groups:
            assert f"### {group}" in detailed, (
                f"Specified group {group!r} not found in Detailed Findings. "
                f"Included groups: {included_groups}"
            )

    @given(data=_scoping_scenario_st())
    def test_detailed_findings_excludes_omitted_groups(
        self,
        data: tuple[
            EvaluationResult,
            dict[str, CapabilityLevelResult],
            EvaluationConfig,
            KBMetadata,
            list[str],
            list[str],
        ],
    ) -> None:
        """Detailed Findings SHALL NOT contain subsections for omitted groups."""
        evaluation, levels, config, kb_metadata, _, omitted_groups = data

        # Only meaningful when there are omitted groups
        assume(len(omitted_groups) > 0)

        generator = ReportGenerator()
        report = generator.generate(evaluation, levels, config, kb_metadata)

        detailed = _extract_detailed_findings(report)

        for group in omitted_groups:
            assert f"### {group}" not in detailed, (
                f"Omitted group {group!r} found in Detailed Findings. "
                f"Omitted groups: {omitted_groups}"
            )

    @given(data=_scoping_scenario_st())
    def test_h3_headers_in_findings_match_specified_groups(
        self,
        data: tuple[
            EvaluationResult,
            dict[str, CapabilityLevelResult],
            EvaluationConfig,
            KBMetadata,
            list[str],
            list[str],
        ],
    ) -> None:
        """The set of ### headers in Detailed Findings matches exactly
        the specified process groups."""
        evaluation, levels, config, kb_metadata, included_groups, _ = data

        generator = ReportGenerator()
        report = generator.generate(evaluation, levels, config, kb_metadata)

        detailed = _extract_detailed_findings(report)

        # Extract all ### headers from the detailed findings section
        h3_headers = [
            line.replace("### ", "").strip()
            for line in detailed.splitlines()
            if line.startswith("### ")
        ]

        assert set(h3_headers) == set(included_groups), (
            f"H3 headers {h3_headers} do not match specified groups {included_groups}"
        )
