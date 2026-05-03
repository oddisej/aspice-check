"""Property 9: Generated report contains all required sections.

Generate random evaluation results; verify report contains headers for
"Executive Summary", "Capability Level Summary", "Detailed Findings",
"Remediation Roadmap", "Traceability Matrix".

**Validates: Requirements 6.1, 6.2**
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from aspice_eval.level_calculator import LEVEL_ATTRIBUTES, CapabilityLevelCalculator
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

REQUIRED_SECTIONS = [
    "## Executive Summary",
    "## Capability Level Summary",
    "## Detailed Findings",
    "## Remediation Roadmap",
    "## Traceability Matrix",
]

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_valid_ratings_st = st.sampled_from(sorted(VALID_RATINGS))
_process_groups_st = st.lists(
    st.sampled_from(ALL_GROUPS), min_size=1, max_size=4, unique=True,
)
_target_level_st = st.integers(min_value=1, max_value=5)


@st.composite
def _evaluation_result_st(draw: st.DrawFn) -> tuple[
    EvaluationResult,
    dict[str, CapabilityLevelResult],
    EvaluationConfig,
    KBMetadata,
]:
    """Generate a random but consistent evaluation result with levels, config, and metadata."""
    groups = draw(_process_groups_st)
    target_level = draw(_target_level_st)

    config = EvaluationConfig(
        sdp_path=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=("L", "N", "Z"),
        ))),
        target_capability_level=target_level,
        process_groups=groups,
    )

    # Generate ratings for each group
    ratings: list[CriteriaRating] = []
    for group in groups:
        # Generate 1-3 ratings per group
        num_ratings = draw(st.integers(min_value=1, max_value=3))
        for i in range(num_ratings):
            pa = draw(st.sampled_from(_PROCESS_ATTRIBUTES))
            level = int(pa.split()[1].split(".")[0])
            rating_val = draw(_valid_ratings_st)

            gaps: list[str] = []
            recommendations: list[str] = []
            if rating_val in ("Partially achieved", "Not achieved"):
                gaps = [f"Gap for {group}-{pa}-{i}"]
                recommendations = [f"Recommendation for {group}-{pa}-{i}"]

            ratings.append(
                CriteriaRating(
                    criteria_id=f"{group}.1-{pa.replace(' ', '')}-{i + 1:03d}",
                    process_group=group,
                    process_attribute=pa,
                    capability_level=level,
                    rating=rating_val,
                    evidence_found=[f"Section {i + 1}"] if rating_val != "Not achieved" else [],
                    gaps=gaps,
                    recommendations=recommendations,
                    sdp_sections_assessed=[f"Section {i + 1}"],
                )
            )

    evaluation = EvaluationResult(
        ratings=ratings,
        sdp_metadata={"file_path": config.sdp_path},
        evaluation_timestamp="2025-01-15T00:00:00Z",
        config=config,
    )

    # Calculate levels
    calc = CapabilityLevelCalculator(target_level=target_level)
    levels = calc.calculate(ratings, groups)

    kb_metadata = KBMetadata(
        standard_name="Automotive SPICE",
        short_name="ASPICE",
        version="4.0",
        release_date="2023-12",
        source_references=[],
        license_note="Test",
        kb_version=draw(st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)),
        last_updated="2025-01-15",
        process_groups=[],
        capability_levels=[],
        rating_scale=[],
    )

    return evaluation, levels, config, kb_metadata


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestProperty09ReportSections:
    """Property 9: Generated report contains all required sections."""

    @given(data=_evaluation_result_st())
    def test_report_contains_all_required_sections(
        self,
        data: tuple[
            EvaluationResult,
            dict[str, CapabilityLevelResult],
            EvaluationConfig,
            KBMetadata,
        ],
    ) -> None:
        """For any valid evaluation result, the generated report SHALL
        contain Markdown headers for all five required sections."""
        evaluation, levels, config, kb_metadata = data

        generator = ReportGenerator()
        report = generator.generate(evaluation, levels, config, kb_metadata)

        for section_header in REQUIRED_SECTIONS:
            assert section_header in report, (
                f"Required section {section_header!r} not found in report. "
                f"Report headers found: "
                f"{[line for line in report.splitlines() if line.startswith('## ')]}"
            )

    @given(data=_evaluation_result_st())
    def test_report_contains_title(
        self,
        data: tuple[
            EvaluationResult,
            dict[str, CapabilityLevelResult],
            EvaluationConfig,
            KBMetadata,
        ],
    ) -> None:
        """The report always starts with a top-level title."""
        evaluation, levels, config, kb_metadata = data

        generator = ReportGenerator()
        report = generator.generate(evaluation, levels, config, kb_metadata)

        assert report.startswith("# ASPICE Gap Analysis Report"), (
            f"Report does not start with expected title. "
            f"First line: {report.splitlines()[0]!r}"
        )

    @given(data=_evaluation_result_st())
    def test_sections_appear_in_correct_order(
        self,
        data: tuple[
            EvaluationResult,
            dict[str, CapabilityLevelResult],
            EvaluationConfig,
            KBMetadata,
        ],
    ) -> None:
        """Required sections appear in the canonical order."""
        evaluation, levels, config, kb_metadata = data

        generator = ReportGenerator()
        report = generator.generate(evaluation, levels, config, kb_metadata)

        positions = [report.index(section) for section in REQUIRED_SECTIONS]
        assert positions == sorted(positions), (
            f"Sections are not in the expected order. "
            f"Positions: {list(zip(REQUIRED_SECTIONS, positions))}"
        )
