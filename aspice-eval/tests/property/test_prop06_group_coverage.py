"""Property 6: Evaluation produces ratings for exactly the requested process groups.

Generate random group subsets and mock evaluation results; verify ratings
cover every requested group and no unrequested groups.

**Validates: Requirements 4.4**
"""

from __future__ import annotations

import json
from typing import Any

from hypothesis import given, strategies as st

from aspice_eval.evaluator import GapAnalysisEvaluator
from aspice_eval.models import (
    VALID_RATINGS,
    CriteriaEntry,
    CriteriaRating,
    EvaluationConfig,
    EvaluationResult,
    ModelConfig,
    SDPDocument,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALL_GROUPS = ["SWE", "SYS", "MAN", "SUP"]

_PROCESS_ATTRIBUTES = [f"PA {lvl}.{sub}" for lvl in range(1, 6) for sub in (1, 2)]

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Non-empty subset of process groups (deduplicated)
_requested_groups_st = (
    st.lists(st.sampled_from(ALL_GROUPS), min_size=1, max_size=4)
    .map(lambda xs: list(dict.fromkeys(xs)))
    .filter(lambda xs: len(xs) >= 1)
)

_valid_ratings_st = st.sampled_from(sorted(VALID_RATINGS))
_capability_levels_st = st.integers(min_value=1, max_value=5)
_process_attributes_st = st.sampled_from(_PROCESS_ATTRIBUTES)


def _criteria_entry_st(group: str) -> st.SearchStrategy[CriteriaEntry]:
    """Strategy for a CriteriaEntry belonging to a specific group."""
    return st.builds(
        CriteriaEntry,
        process_group=st.just(group),
        process_id=st.just(group).flatmap(
            lambda g: st.integers(min_value=1, max_value=6).map(
                lambda n: f"{g}.{n}"
            )
        ),
        process_name=st.just(f"Process for {group}"),
        capability_level=_capability_levels_st,
        process_attribute=_process_attributes_st,
        process_attribute_name=st.just("Attribute name"),
        criteria_id=st.uuids().map(lambda u: f"{group}-{u.hex[:8]}"),
        description=st.just("Test criterion description."),
        expected_evidence=st.just([{"type": "document", "description": "Test evidence"}]),
        evaluation_guidance=st.just("Test evaluation guidance."),
    )


def _criteria_for_groups_st(
    groups: list[str],
) -> st.SearchStrategy[list[CriteriaEntry]]:
    """Strategy that generates 1-3 criteria per group for the given groups."""
    per_group = [
        st.lists(_criteria_entry_st(g), min_size=1, max_size=3)
        for g in groups
    ]
    # Flatten the per-group lists into a single list
    return st.tuples(*per_group).map(
        lambda parts: [entry for part in parts for entry in part]
    )


# ---------------------------------------------------------------------------
# Custom evaluator that returns pre-built ratings
# ---------------------------------------------------------------------------


class _FixedResponseEvaluator(GapAnalysisEvaluator):
    """Evaluator that returns a fixed JSON response for testing.

    The response is built from the criteria passed to ``evaluate``,
    ensuring every criterion gets a rating with the correct group.
    """

    def __init__(self, rating: str = "Fully achieved") -> None:
        super().__init__(ModelConfig())
        self._rating = rating

    def _call_model(self, prompt: str) -> str:
        """Parse criteria from the prompt and return a rating for each."""
        ratings: list[dict[str, Any]] = []
        try:
            json_start = prompt.index("```json\n") + len("```json\n")
            json_end = prompt.index("\n```\n\n## SDP Document")
            criteria_data = json.loads(prompt[json_start:json_end])

            for entry in criteria_data:
                gaps: list[str] = []
                recommendations: list[str] = []
                if self._rating in ("Partially achieved", "Not achieved"):
                    gaps = [f"Gap for {entry['criteria_id']}"]
                    recommendations = [f"Fix {entry['criteria_id']}"]

                ratings.append(
                    {
                        "criteria_id": entry["criteria_id"],
                        "rating": self._rating,
                        "evidence_found": ["Section 1"],
                        "gaps": gaps,
                        "recommendations": recommendations,
                        "sdp_sections_assessed": ["Overview"],
                    }
                )
        except (ValueError, json.JSONDecodeError, KeyError):
            pass

        return json.dumps(ratings)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestProperty06GroupCoverage:
    """Property 6: Evaluation produces ratings for exactly the requested process groups."""

    @given(
        requested_groups=_requested_groups_st,
        rating=_valid_ratings_st,
        data=st.data(),
    )
    def test_ratings_cover_every_requested_group(
        self,
        requested_groups: list[str],
        rating: str,
        data: st.DataObject,
    ) -> None:
        """Every requested group appears in the evaluation result ratings."""
        criteria = data.draw(_criteria_for_groups_st(requested_groups))

        evaluator = _FixedResponseEvaluator(rating=rating)
        config = EvaluationConfig(
            sdp_path="test.md",
            process_groups=requested_groups,
        )
        sdp = SDPDocument(content="# Test SDP\nSample content.", file_path="test.md")

        result = evaluator.evaluate(sdp, criteria, config)

        rated_groups = {r.process_group for r in result.ratings}
        for group in requested_groups:
            assert group in rated_groups, (
                f"Group {group!r} was requested but has no ratings. "
                f"Rated groups: {rated_groups}"
            )

    @given(
        requested_groups=_requested_groups_st.filter(lambda gs: len(gs) < 4),
        rating=_valid_ratings_st,
        data=st.data(),
    )
    def test_no_ratings_for_unrequested_groups(
        self,
        requested_groups: list[str],
        rating: str,
        data: st.DataObject,
    ) -> None:
        """No unrequested group appears in the evaluation result ratings."""
        # Build criteria only for the requested groups
        criteria = data.draw(_criteria_for_groups_st(requested_groups))

        evaluator = _FixedResponseEvaluator(rating=rating)
        config = EvaluationConfig(
            sdp_path="test.md",
            process_groups=requested_groups,
        )
        sdp = SDPDocument(content="# Test SDP\nSample content.", file_path="test.md")

        result = evaluator.evaluate(sdp, criteria, config)

        unrequested = set(ALL_GROUPS) - set(requested_groups)
        rated_groups = {r.process_group for r in result.ratings}
        for group in unrequested:
            assert group not in rated_groups, (
                f"Group {group!r} was NOT requested but has ratings. "
                f"Requested: {requested_groups}, Rated: {rated_groups}"
            )

    @given(
        requested_groups=_requested_groups_st,
        data=st.data(),
    )
    def test_result_ratings_count_matches_criteria_count(
        self,
        requested_groups: list[str],
        data: st.DataObject,
    ) -> None:
        """The number of ratings equals the number of input criteria."""
        criteria = data.draw(_criteria_for_groups_st(requested_groups))

        evaluator = _FixedResponseEvaluator(rating="Fully achieved")
        config = EvaluationConfig(
            sdp_path="test.md",
            process_groups=requested_groups,
        )
        sdp = SDPDocument(content="# Test SDP\nSample content.", file_path="test.md")

        result = evaluator.evaluate(sdp, criteria, config)

        assert len(result.ratings) == len(criteria), (
            f"Expected {len(criteria)} ratings, got {len(result.ratings)}"
        )
