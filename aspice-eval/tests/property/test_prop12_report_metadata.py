"""Property 12: Report metadata contains all required identification fields.

Generate random configs and metadata; verify report metadata includes
SDP path, target level, KB version, and timestamp.

**Validates: Requirements 6.5**
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

# SDP paths: printable strings without pipe characters (which would break
# Markdown table parsing) and without newlines.
_sdp_path_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Z", "P"),
        blacklist_characters="|\n\r",
    ),
    min_size=1,
    max_size=80,
)

_target_level_st = st.integers(min_value=1, max_value=5)

_process_groups_st = st.lists(
    st.sampled_from(ALL_GROUPS), min_size=1, max_size=4, unique=True,
)

_kb_version_st = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)

_timestamp_st = st.from_regex(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
    fullmatch=True,
)


@st.composite
def _metadata_scenario_st(draw: st.DrawFn) -> tuple[
    EvaluationResult,
    dict[str, CapabilityLevelResult],
    EvaluationConfig,
    KBMetadata,
    str,
    int,
    str,
    str,
]:
    """Generate a random scenario and return the expected metadata values."""
    sdp_path = draw(_sdp_path_st)
    target_level = draw(_target_level_st)
    groups = draw(_process_groups_st)
    kb_version = draw(_kb_version_st)
    timestamp = draw(_timestamp_st)

    config = EvaluationConfig(
        sdp_path=sdp_path,
        target_capability_level=target_level,
        process_groups=groups,
    )

    # Generate at least one rating per group
    ratings: list[CriteriaRating] = []
    for group in groups:
        pa = draw(st.sampled_from(_PROCESS_ATTRIBUTES))
        level = int(pa.split()[1].split(".")[0])
        ratings.append(
            CriteriaRating(
                criteria_id=f"{group}.1-{pa.replace(' ', '')}-001",
                process_group=group,
                process_attribute=pa,
                capability_level=level,
                rating=draw(_valid_ratings_st),
            )
        )

    evaluation = EvaluationResult(
        ratings=ratings,
        sdp_metadata={},
        evaluation_timestamp=timestamp,
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
        kb_version=kb_version,
        last_updated="2025-01-15",
        process_groups=[],
        capability_levels=[],
        rating_scale=[],
    )

    return evaluation, levels, config, kb_metadata, sdp_path, target_level, kb_version, timestamp


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestProperty12ReportMetadata:
    """Property 12: Report metadata contains all required identification fields."""

    @given(data=_metadata_scenario_st())
    def test_metadata_contains_sdp_path(
        self,
        data: tuple[
            EvaluationResult,
            dict[str, CapabilityLevelResult],
            EvaluationConfig,
            KBMetadata,
            str,
            int,
            str,
            str,
        ],
    ) -> None:
        """The report metadata section SHALL include the SDP document path."""
        evaluation, levels, config, kb_metadata, sdp_path, _, _, _ = data

        generator = ReportGenerator()
        report = generator.generate(evaluation, levels, config, kb_metadata)

        # Extract metadata section (between ## Metadata and next ##)
        meta_start = report.index("## Metadata")
        meta_end = report.index("## Executive Summary")
        metadata_section = report[meta_start:meta_end]

        assert sdp_path in metadata_section, (
            f"SDP path {sdp_path!r} not found in Metadata section."
        )

    @given(data=_metadata_scenario_st())
    def test_metadata_contains_target_level(
        self,
        data: tuple[
            EvaluationResult,
            dict[str, CapabilityLevelResult],
            EvaluationConfig,
            KBMetadata,
            str,
            int,
            str,
            str,
        ],
    ) -> None:
        """The report metadata section SHALL include the target capability level."""
        evaluation, levels, config, kb_metadata, _, target_level, _, _ = data

        generator = ReportGenerator()
        report = generator.generate(evaluation, levels, config, kb_metadata)

        meta_start = report.index("## Metadata")
        meta_end = report.index("## Executive Summary")
        metadata_section = report[meta_start:meta_end]

        assert str(target_level) in metadata_section, (
            f"Target level {target_level} not found in Metadata section."
        )

    @given(data=_metadata_scenario_st())
    def test_metadata_contains_kb_version(
        self,
        data: tuple[
            EvaluationResult,
            dict[str, CapabilityLevelResult],
            EvaluationConfig,
            KBMetadata,
            str,
            int,
            str,
            str,
        ],
    ) -> None:
        """The report metadata section SHALL include the KB version."""
        evaluation, levels, config, kb_metadata, _, _, kb_version, _ = data

        generator = ReportGenerator()
        report = generator.generate(evaluation, levels, config, kb_metadata)

        meta_start = report.index("## Metadata")
        meta_end = report.index("## Executive Summary")
        metadata_section = report[meta_start:meta_end]

        assert kb_version in metadata_section, (
            f"KB version {kb_version!r} not found in Metadata section."
        )

    @given(data=_metadata_scenario_st())
    def test_metadata_contains_timestamp(
        self,
        data: tuple[
            EvaluationResult,
            dict[str, CapabilityLevelResult],
            EvaluationConfig,
            KBMetadata,
            str,
            int,
            str,
            str,
        ],
    ) -> None:
        """The report metadata section SHALL include the evaluation timestamp."""
        evaluation, levels, config, kb_metadata, _, _, _, timestamp = data

        generator = ReportGenerator()
        report = generator.generate(evaluation, levels, config, kb_metadata)

        meta_start = report.index("## Metadata")
        meta_end = report.index("## Executive Summary")
        metadata_section = report[meta_start:meta_end]

        assert timestamp in metadata_section, (
            f"Timestamp {timestamp!r} not found in Metadata section."
        )
