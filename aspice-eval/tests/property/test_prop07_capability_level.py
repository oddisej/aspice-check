"""Property 7: Capability level calculation follows ASPICE cumulative achievement rules.

Generate random attribute rating maps; verify calculated level satisfies:
all PAs at achieved level and below are L/F, and if below target, at least
one PA at next level is P/N.

**Validates: Requirements 5.1, 5.2**
"""

from __future__ import annotations

from hypothesis import given, strategies as st

from aspice_eval.level_calculator import (
    LEVEL_ATTRIBUTES,
    CapabilityLevelCalculator,
    _ACHIEVED_RATINGS,
)
from aspice_eval.models import CriteriaRating, VALID_RATINGS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALL_GROUPS = ["SWE", "SYS", "MAN", "SUP"]

# All process attributes across levels 1–5
ALL_PAS: list[str] = [
    pa for level in range(1, 6) for pa in LEVEL_ATTRIBUTES[level]
]

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_valid_ratings_st = st.sampled_from(sorted(VALID_RATINGS))
_achieved_ratings_st = st.sampled_from(["Fully achieved", "Largely achieved"])
_not_achieved_ratings_st = st.sampled_from(["Partially achieved", "Not achieved"])
_process_group_st = st.sampled_from(ALL_GROUPS)
_target_level_st = st.integers(min_value=1, max_value=5)


def _attribute_rating_map_st() -> st.SearchStrategy[dict[str, str]]:
    """Generate a random mapping of PA identifiers to ASPICE ratings.

    Generates ratings for all 9 PAs (PA 1.1 through PA 5.2) to ensure
    the calculator has complete data to work with.
    """
    return st.fixed_dictionaries(
        {pa: _valid_ratings_st for pa in ALL_PAS}
    )


def _ratings_from_attribute_map(
    attr_map: dict[str, str],
    group: str,
) -> list[CriteriaRating]:
    """Convert an attribute rating map into CriteriaRating objects.

    Creates one CriteriaRating per PA, simulating the simplest case
    where each PA has exactly one criteria entry.
    """
    ratings: list[CriteriaRating] = []
    for pa, rating in attr_map.items():
        # Derive capability level from the PA identifier (e.g. "PA 2.1" → 2)
        level = int(pa.split()[1].split(".")[0])
        ratings.append(
            CriteriaRating(
                criteria_id=f"{group}-{pa.replace(' ', '')}-001",
                process_group=group,
                process_attribute=pa,
                capability_level=level,
                rating=rating,
            )
        )
    return ratings


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestProperty07CapabilityLevel:
    """Property 7: Capability level calculation follows ASPICE cumulative achievement rules."""

    @given(
        attr_map=_attribute_rating_map_st(),
        group=_process_group_st,
        target_level=_target_level_st,
    )
    def test_all_pas_at_achieved_level_and_below_are_achieved(
        self,
        attr_map: dict[str, str],
        group: str,
        target_level: int,
    ) -> None:
        """For every level L where 1 <= L <= achieved_level, ALL PAs at L are L/F."""
        ratings = _ratings_from_attribute_map(attr_map, group)
        calc = CapabilityLevelCalculator(target_level=target_level)
        results = calc.calculate(ratings, [group])
        result = results[group]

        for level in range(1, result.achieved_level + 1):
            for pa in LEVEL_ATTRIBUTES[level]:
                pa_rating = result.attribute_ratings.get(pa)
                assert pa_rating in _ACHIEVED_RATINGS, (
                    f"PA {pa} at level {level} (≤ achieved_level={result.achieved_level}) "
                    f"has rating {pa_rating!r}, expected Largely/Fully achieved. "
                    f"Full attribute map: {result.attribute_ratings}"
                )

    @given(
        attr_map=_attribute_rating_map_st(),
        group=_process_group_st,
        target_level=_target_level_st,
    )
    def test_next_level_has_at_least_one_unachieved_pa_when_below_max(
        self,
        attr_map: dict[str, str],
        group: str,
        target_level: int,
    ) -> None:
        """If achieved_level < 5, at least one PA at achieved_level+1 is P/N."""
        ratings = _ratings_from_attribute_map(attr_map, group)
        calc = CapabilityLevelCalculator(target_level=target_level)
        results = calc.calculate(ratings, [group])
        result = results[group]

        if result.achieved_level < 5:
            next_level = result.achieved_level + 1
            next_pas = LEVEL_ATTRIBUTES[next_level]
            next_ratings = [
                result.attribute_ratings.get(pa, "Not achieved")
                for pa in next_pas
            ]
            has_unachieved = any(
                r not in _ACHIEVED_RATINGS for r in next_ratings
            )
            assert has_unachieved, (
                f"Achieved level is {result.achieved_level} (< 5) but all PAs "
                f"at level {next_level} are achieved: {dict(zip(next_pas, next_ratings))}. "
                f"The achieved level should have been {next_level}."
            )

    @given(
        attr_map=_attribute_rating_map_st(),
        group=_process_group_st,
        target_level=_target_level_st,
    )
    def test_achieved_level_is_in_valid_range(
        self,
        attr_map: dict[str, str],
        group: str,
        target_level: int,
    ) -> None:
        """The achieved level is always between 0 and 5 inclusive."""
        ratings = _ratings_from_attribute_map(attr_map, group)
        calc = CapabilityLevelCalculator(target_level=target_level)
        results = calc.calculate(ratings, [group])
        result = results[group]

        assert 0 <= result.achieved_level <= 5, (
            f"Achieved level {result.achieved_level} is outside valid range [0, 5]"
        )

    @given(
        group=_process_group_st,
        target_level=_target_level_st,
    )
    def test_all_fully_achieved_gives_level_5(
        self,
        group: str,
        target_level: int,
    ) -> None:
        """When all PAs are Fully achieved, the achieved level is 5."""
        attr_map = {pa: "Fully achieved" for pa in ALL_PAS}
        ratings = _ratings_from_attribute_map(attr_map, group)
        calc = CapabilityLevelCalculator(target_level=target_level)
        results = calc.calculate(ratings, [group])
        result = results[group]

        assert result.achieved_level == 5, (
            f"All PAs are Fully achieved but achieved level is "
            f"{result.achieved_level}, expected 5"
        )

    @given(
        group=_process_group_st,
        target_level=_target_level_st,
    )
    def test_pa11_not_achieved_gives_level_0(
        self,
        group: str,
        target_level: int,
    ) -> None:
        """When PA 1.1 is Not achieved, the achieved level is 0."""
        attr_map = {pa: "Fully achieved" for pa in ALL_PAS}
        attr_map["PA 1.1"] = "Not achieved"
        ratings = _ratings_from_attribute_map(attr_map, group)
        calc = CapabilityLevelCalculator(target_level=target_level)
        results = calc.calculate(ratings, [group])
        result = results[group]

        assert result.achieved_level == 0, (
            f"PA 1.1 is Not achieved but achieved level is "
            f"{result.achieved_level}, expected 0"
        )
