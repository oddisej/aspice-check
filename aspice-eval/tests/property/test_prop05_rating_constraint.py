"""Property 5: Rating values are constrained to the ASPICE rating scale.

Generate random ``CriteriaRating`` objects; verify ``rating`` field is one of
"Fully achieved", "Largely achieved", "Partially achieved", "Not achieved".

**Validates: Requirements 4.2**
"""

import pytest
from hypothesis import given, strategies as st

from aspice_eval.models import CriteriaRating, VALID_RATINGS

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Realistic process group codes used in the project
_process_groups = st.sampled_from(["SWE", "SYS", "MAN", "SUP"])

# Process attribute identifiers (PA x.y where x in 1-5, y in 1-2)
_process_attributes = st.sampled_from(
    [f"PA {level}.{sub}" for level in range(1, 6) for sub in (1, 2)]
)

# Capability levels 1-5
_capability_levels = st.integers(min_value=1, max_value=5)

# Criteria IDs like "SWE.1-PA1.1-001"
_criteria_ids = st.builds(
    lambda grp, num, pa, seq: f"{grp}.{num}-{pa.replace(' ', '')}-{seq:03d}",
    _process_groups,
    st.integers(min_value=1, max_value=6),
    _process_attributes,
    st.integers(min_value=1, max_value=99),
)

# Strategy for a valid rating value
_valid_ratings = st.sampled_from(sorted(VALID_RATINGS))

# Strategy for arbitrary strings that are NOT valid ratings.
# We use text() and filter out the four valid values.
_invalid_ratings = (
    st.text(min_size=1, max_size=80)
    .filter(lambda s: s not in VALID_RATINGS)
)


class TestProperty05RatingConstraint:
    """Property 5: Rating values are constrained to the ASPICE rating scale."""

    @given(
        criteria_id=_criteria_ids,
        process_group=_process_groups,
        process_attribute=_process_attributes,
        capability_level=_capability_levels,
        rating=_valid_ratings,
    )
    def test_valid_ratings_are_accepted(
        self,
        criteria_id: str,
        process_group: str,
        process_attribute: str,
        capability_level: int,
        rating: str,
    ) -> None:
        """CriteriaRating accepts any of the four ASPICE rating values."""
        cr = CriteriaRating(
            criteria_id=criteria_id,
            process_group=process_group,
            process_attribute=process_attribute,
            capability_level=capability_level,
            rating=rating,
        )
        assert cr.rating in VALID_RATINGS

    @given(
        criteria_id=_criteria_ids,
        process_group=_process_groups,
        process_attribute=_process_attributes,
        capability_level=_capability_levels,
        rating=_invalid_ratings,
    )
    def test_invalid_ratings_are_rejected(
        self,
        criteria_id: str,
        process_group: str,
        process_attribute: str,
        capability_level: int,
        rating: str,
    ) -> None:
        """CriteriaRating rejects any string not in the ASPICE rating scale."""
        with pytest.raises(ValueError, match="Invalid rating"):
            CriteriaRating(
                criteria_id=criteria_id,
                process_group=process_group,
                process_attribute=process_attribute,
                capability_level=capability_level,
                rating=rating,
            )
