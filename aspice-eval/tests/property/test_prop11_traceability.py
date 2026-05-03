"""Property 11: Traceability section references all evaluated criteria.

Generate random evaluation results; verify every ``criteria_id`` appears
in the traceability section of the generated report.

**Validates: Requirements 6.4**
"""

from __future__ import annotations

from hypothesis import given, strategies as st

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
_process_groups_st = st.lists(
    st.sampled_from(ALL_GROUPS), min_size=1, max_size=4, unique=True,
)
_target_level_st = st.integers(min_value=1, max_value=5)


@st.composite
def _evaluation_with_criteria_ids_st(draw: st.DrawFn) -> tuple[
    EvaluationResult,
    dict[str, CapabilityLevelResult],
    EvaluationConfig,
    KBMetadata,
    list[str],
]:
    """Generate a random evaluation result and return the list of criteria_ids."""
    groups = draw(_process_groups_st)
    target_level = draw(_target_level_st)

    config = EvaluationConfig(
        sdp_path="test_sdp.md",
        target_capability_level=target_level,
        process_groups=groups,
    )

    ratings: list[CriteriaRating] = []
    criteria_ids: list[str] = []

    for group in groups:
        num_ratings = draw(st.integers(min_value=1, max_value=5))
        for i in range(num_ratings):
            pa = draw(st.sampled_from(_PROCESS_ATTRIBUTES))
            level = int(pa.split()[1].split(".")[0])
            rating_val = draw(_valid_ratings_st)

            # Generate a unique criteria_id
            cid = f"{group}.{draw(st.integers(min_value=1, max_value=6))}-{pa.replace(' ', '')}-{i + 1:03d}"

            gaps: list[str] = []
            recommendations: list[str] = []
            if rating_val in ("Partially achieved", "Not achieved"):
                gaps = [f"Gap {cid}"]
                recommendations = [f"Fix {cid}"]

            ratings.append(
                CriteriaRating(
                    criteria_id=cid,
                    process_group=group,
                    process_attribute=pa,
                    capability_level=level,
                    rating=rating_val,
                    evidence_found=[],
                    gaps=gaps,
                    recommendations=recommendations,
                    sdp_sections_assessed=[f"Section {i}"],
                )
            )
            criteria_ids.append(cid)

    evaluation = EvaluationResult(
        ratings=ratings,
        sdp_metadata={},
        evaluation_timestamp="2025-01-15T12:00:00Z",
        config=config,
    )

    calc = CapabilityLevelCalculator(target_level=target_level)
    levels = calc.calculate(ratings, groups)

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

    return evaluation, levels, config, kb_metadata, criteria_ids


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestProperty11Traceability:
    """Property 11: Traceability section references all evaluated criteria."""

    @given(data=_evaluation_with_criteria_ids_st())
    def test_every_criteria_id_appears_in_traceability(
        self,
        data: tuple[
            EvaluationResult,
            dict[str, CapabilityLevelResult],
            EvaluationConfig,
            KBMetadata,
            list[str],
        ],
    ) -> None:
        """For any evaluation result, every criteria_id SHALL appear in
        the Traceability Matrix section of the report."""
        evaluation, levels, config, kb_metadata, criteria_ids = data

        generator = ReportGenerator()
        report = generator.generate(evaluation, levels, config, kb_metadata)

        # Extract the traceability section
        trace_start = report.index("## Traceability Matrix")
        traceability_section = report[trace_start:]

        for cid in criteria_ids:
            assert cid in traceability_section, (
                f"Criteria ID {cid!r} not found in Traceability Matrix section. "
                f"All criteria IDs: {criteria_ids}"
            )

    @given(data=_evaluation_with_criteria_ids_st())
    def test_traceability_row_count_matches_ratings(
        self,
        data: tuple[
            EvaluationResult,
            dict[str, CapabilityLevelResult],
            EvaluationConfig,
            KBMetadata,
            list[str],
        ],
    ) -> None:
        """The traceability table has exactly one row per rating."""
        evaluation, levels, config, kb_metadata, criteria_ids = data

        generator = ReportGenerator()
        report = generator.generate(evaluation, levels, config, kb_metadata)

        trace_start = report.index("## Traceability Matrix")
        traceability_section = report[trace_start:]

        # Count data rows (skip header row and separator row)
        table_lines = [
            line
            for line in traceability_section.splitlines()
            if line.startswith("|") and not line.startswith("| Criteria ID") and not line.startswith("|---")
        ]

        assert len(table_lines) == len(evaluation.ratings), (
            f"Expected {len(evaluation.ratings)} traceability rows, "
            f"got {len(table_lines)}"
        )
