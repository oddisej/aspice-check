"""Property 10: Ratings with gaps always have non-empty recommendations.

Generate random ``CriteriaRating`` objects with non-empty ``gaps``; verify
``recommendations`` is also non-empty. Every identified gap must have at
least one associated remediation recommendation.

**Validates: Requirements 6.3**
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
    ModelConfig,
    SDPDocument,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALL_GROUPS = ["SWE", "SYS", "MAN", "SUP"]

_PROCESS_ATTRIBUTES = [f"PA {lvl}.{sub}" for lvl in range(1, 6) for sub in (1, 2)]

# Ratings that typically accompany gaps
_GAP_RATINGS = ["Partially achieved", "Not achieved"]

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_process_groups_st = st.sampled_from(ALL_GROUPS)
_process_attributes_st = st.sampled_from(_PROCESS_ATTRIBUTES)
_capability_levels_st = st.integers(min_value=1, max_value=5)
_valid_ratings_st = st.sampled_from(sorted(VALID_RATINGS))
_gap_ratings_st = st.sampled_from(_GAP_RATINGS)

# Non-empty list of gap descriptions
_non_empty_gaps_st = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
        min_size=1,
        max_size=100,
    ),
    min_size=1,
    max_size=5,
)

# Non-empty list of recommendation descriptions
_non_empty_recommendations_st = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
        min_size=1,
        max_size=100,
    ),
    min_size=1,
    max_size=5,
)

# Criteria IDs
_criteria_ids_st = st.builds(
    lambda grp, num, pa, seq: f"{grp}.{num}-{pa.replace(' ', '')}-{seq:03d}",
    _process_groups_st,
    st.integers(min_value=1, max_value=6),
    _process_attributes_st,
    st.integers(min_value=1, max_value=99),
)


# ---------------------------------------------------------------------------
# Custom evaluator that returns ratings with gaps but no recommendations
# ---------------------------------------------------------------------------


class _GapOnlyEvaluator(GapAnalysisEvaluator):
    """Evaluator that returns ratings with gaps but omits recommendations.

    This tests that the evaluator's ``_parse_single_rating`` method
    enforces the gap-recommendation invariant by auto-generating
    recommendations when the AI model fails to provide them.
    """

    def __init__(self, gaps: list[str], rating: str = "Partially achieved") -> None:
        super().__init__(ModelConfig())
        self._gaps = gaps
        self._rating = rating

    def _call_model(self, prompt: str) -> str:
        """Return ratings with gaps but deliberately empty recommendations."""
        ratings: list[dict[str, Any]] = []
        try:
            json_start = prompt.index("```json\n") + len("```json\n")
            json_end = prompt.index("\n```\n\n## SDP Document")
            criteria_data = json.loads(prompt[json_start:json_end])

            for entry in criteria_data:
                ratings.append(
                    {
                        "criteria_id": entry["criteria_id"],
                        "rating": self._rating,
                        "evidence_found": [],
                        "gaps": self._gaps,
                        "recommendations": [],  # deliberately empty
                        "sdp_sections_assessed": [],
                    }
                )
        except (ValueError, json.JSONDecodeError, KeyError):
            pass

        return json.dumps(ratings)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestProperty10GapRecommendation:
    """Property 10: Ratings with gaps always have non-empty recommendations."""

    @given(
        criteria_id=_criteria_ids_st,
        process_group=_process_groups_st,
        process_attribute=_process_attributes_st,
        capability_level=_capability_levels_st,
        rating=_gap_ratings_st,
        gaps=_non_empty_gaps_st,
        recommendations=_non_empty_recommendations_st,
    )
    def test_rating_with_gaps_and_recommendations_is_valid(
        self,
        criteria_id: str,
        process_group: str,
        process_attribute: str,
        capability_level: int,
        rating: str,
        gaps: list[str],
        recommendations: list[str],
    ) -> None:
        """A CriteriaRating with non-empty gaps and non-empty recommendations
        is well-formed — the invariant holds when both are provided."""
        cr = CriteriaRating(
            criteria_id=criteria_id,
            process_group=process_group,
            process_attribute=process_attribute,
            capability_level=capability_level,
            rating=rating,
            gaps=gaps,
            recommendations=recommendations,
        )
        assert len(cr.gaps) > 0
        assert len(cr.recommendations) > 0

    @given(
        gaps=_non_empty_gaps_st,
        data=st.data(),
    )
    def test_evaluator_enforces_recommendations_when_gaps_present(
        self,
        gaps: list[str],
        data: st.DataObject,
    ) -> None:
        """When the AI model returns gaps without recommendations, the
        evaluator auto-generates recommendations to maintain the invariant."""
        group = data.draw(_process_groups_st)
        rating = data.draw(_gap_ratings_st)

        criteria = [
            CriteriaEntry(
                process_group=group,
                process_id=f"{group}.1",
                process_name=f"Process {group}.1",
                capability_level=1,
                process_attribute="PA 1.1",
                process_attribute_name="Process performance",
                criteria_id=f"{group}.1-PA1.1-001",
                description="Test criterion.",
                expected_evidence=[{"type": "document", "description": "Evidence"}],
                evaluation_guidance="Test guidance.",
            ),
        ]

        evaluator = _GapOnlyEvaluator(gaps=gaps, rating=rating)
        config = EvaluationConfig(
            sdp_path="test.md",
            process_groups=[group],
        )
        sdp = SDPDocument(content="# Test SDP\nContent.", file_path="test.md")

        result = evaluator.evaluate(sdp, criteria, config)

        for cr in result.ratings:
            if cr.gaps:
                assert len(cr.recommendations) > 0, (
                    f"Rating {cr.criteria_id} has gaps {cr.gaps} "
                    f"but empty recommendations"
                )

    @given(
        criteria_id=_criteria_ids_st,
        process_group=_process_groups_st,
        process_attribute=_process_attributes_st,
        capability_level=_capability_levels_st,
        rating=_valid_ratings_st,
    )
    def test_rating_without_gaps_allows_empty_recommendations(
        self,
        criteria_id: str,
        process_group: str,
        process_attribute: str,
        capability_level: int,
        rating: str,
    ) -> None:
        """A CriteriaRating with empty gaps is allowed to have empty
        recommendations — the invariant only applies when gaps exist."""
        cr = CriteriaRating(
            criteria_id=criteria_id,
            process_group=process_group,
            process_attribute=process_attribute,
            capability_level=capability_level,
            rating=rating,
            gaps=[],
            recommendations=[],
        )
        # No assertion failure — empty gaps with empty recommendations is fine
        assert cr.gaps == []
        assert cr.recommendations == []
