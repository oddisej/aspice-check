"""Property 8: Blocking attributes are exactly the underachieving PAs at the next level.

Generate random below-target results; verify ``blocking_attributes`` contains
exactly the PAs at ``achieved_level + 1`` rated P or N.

**Validates: Requirements 5.3**
"""

from __future__ import annotations

from hypothesis import given, assume, strategies as st

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

ALL_PAS: list[str] = [
    pa for level in range(1, 6) for pa in LEVEL_ATTRIBUTES[level]
]

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_valid_ratings_st = st.sampled_from(sorted(VALID_RATINGS))
_process_group_st = st.sampled_from(ALL_GROUPS)
_target_level_st = st.integers(min_value=1, max_value=5)


def _attribute_rating_map_st() -> st.SearchStrategy[dict[str, str]]:
    """Generate a random mapping of all PA identifiers to ASPICE ratings."""
    return st.fixed_dictionaries(
        {pa: _valid_ratings_st for pa in ALL_PAS}
    )


def _below_target_attribute_map_st(
    target_level: int,
) -> st.SearchStrategy[dict[str, str]]:
    """Generate an attribute map that guarantees achieved_level < target_level.

    Ensures all PAs at levels below target_level's first level are achieved,
    but at least one PA at some level <= target_level is not achieved,
    so the result is below target.

    The simplest approach: make PA 1.1 "Not achieved" when target >= 1,
    guaranteeing achieved_level = 0 < target_level.
    But that's too narrow. Instead, we pick a random "break level" in
    [1, target_level] and ensure at least one PA at that level is P/N,
    while all PAs below that level are L/F.
    """
    break_level_st = st.integers(min_value=1, max_value=target_level)

    @st.composite
    def build(draw: st.DrawFn) -> dict[str, str]:
        break_level = draw(break_level_st)
        attr_map: dict[str, str] = {}

        for level in range(1, 6):
            pas = LEVEL_ATTRIBUTES[level]
            if level < break_level:
                # All PAs below break level must be achieved
                for pa in pas:
                    attr_map[pa] = draw(
                        st.sampled_from(["Fully achieved", "Largely achieved"])
                    )
            elif level == break_level:
                # At least one PA at break level must be P/N
                # Pick which PAs are blocking
                blocking_count = draw(st.integers(min_value=1, max_value=len(pas)))
                blocking_indices = draw(
                    st.lists(
                        st.integers(min_value=0, max_value=len(pas) - 1),
                        min_size=blocking_count,
                        max_size=blocking_count,
                        unique=True,
                    )
                )
                for i, pa in enumerate(pas):
                    if i in blocking_indices:
                        attr_map[pa] = draw(
                            st.sampled_from(["Partially achieved", "Not achieved"])
                        )
                    else:
                        attr_map[pa] = draw(_valid_ratings_st)
            else:
                # Levels above break level: any rating
                for pa in pas:
                    attr_map[pa] = draw(_valid_ratings_st)

        return attr_map

    return build()


def _ratings_from_attribute_map(
    attr_map: dict[str, str],
    group: str,
) -> list[CriteriaRating]:
    """Convert an attribute rating map into CriteriaRating objects."""
    ratings: list[CriteriaRating] = []
    for pa, rating in attr_map.items():
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


class TestProperty08BlockingAttributes:
    """Property 8: Blocking attributes are exactly the underachieving PAs at the next level."""

    @given(
        attr_map=_attribute_rating_map_st(),
        group=_process_group_st,
        target_level=_target_level_st,
    )
    def test_blocking_attributes_match_unachieved_pas_at_next_level(
        self,
        attr_map: dict[str, str],
        group: str,
        target_level: int,
    ) -> None:
        """blocking_attributes contains exactly the PAs at achieved_level+1 rated P/N."""
        ratings = _ratings_from_attribute_map(attr_map, group)
        calc = CapabilityLevelCalculator(target_level=target_level)
        results = calc.calculate(ratings, [group])
        result = results[group]

        if result.achieved_level >= 5:
            # At max level, no blocking attributes
            assert result.blocking_attributes == [], (
                f"Achieved level 5 should have no blocking attributes, "
                f"got {result.blocking_attributes}"
            )
            return

        next_level = result.achieved_level + 1
        next_pas = LEVEL_ATTRIBUTES[next_level]

        # Expected blocking: PAs at next level that are NOT L/F
        expected_blocking = set()
        for pa in next_pas:
            pa_rating = result.attribute_ratings.get(pa)
            if pa_rating is None or pa_rating not in _ACHIEVED_RATINGS:
                expected_blocking.add(pa)

        actual_blocking = set(result.blocking_attributes)

        assert actual_blocking == expected_blocking, (
            f"Blocking attributes mismatch at level {next_level}. "
            f"Expected: {expected_blocking}, Got: {actual_blocking}. "
            f"Next level PAs and ratings: "
            f"{[(pa, result.attribute_ratings.get(pa)) for pa in next_pas]}"
        )

    @given(
        group=_process_group_st,
        target_level=_target_level_st,
        data=st.data(),
    )
    def test_below_target_has_blocking_attributes(
        self,
        group: str,
        target_level: int,
        data: st.DataObject,
    ) -> None:
        """When achieved_level < target_level, blocking_attributes is non-empty."""
        attr_map = data.draw(_below_target_attribute_map_st(target_level))
        ratings = _ratings_from_attribute_map(attr_map, group)
        calc = CapabilityLevelCalculator(target_level=target_level)
        results = calc.calculate(ratings, [group])
        result = results[group]

        # The constructed map guarantees achieved < target
        assume(result.achieved_level < result.target_level)

        assert len(result.blocking_attributes) > 0, (
            f"Achieved level {result.achieved_level} < target {result.target_level} "
            f"but blocking_attributes is empty. "
            f"Attribute ratings: {result.attribute_ratings}"
        )

    @given(
        attr_map=_attribute_rating_map_st(),
        group=_process_group_st,
        target_level=_target_level_st,
    )
    def test_blocking_attributes_are_valid_pa_identifiers(
        self,
        attr_map: dict[str, str],
        group: str,
        target_level: int,
    ) -> None:
        """Every entry in blocking_attributes is a valid PA identifier."""
        ratings = _ratings_from_attribute_map(attr_map, group)
        calc = CapabilityLevelCalculator(target_level=target_level)
        results = calc.calculate(ratings, [group])
        result = results[group]

        all_valid_pas = set(ALL_PAS)
        for pa in result.blocking_attributes:
            assert pa in all_valid_pas, (
                f"Blocking attribute {pa!r} is not a valid PA identifier. "
                f"Valid PAs: {all_valid_pas}"
            )

    @given(
        group=_process_group_st,
        target_level=_target_level_st,
    )
    def test_all_achieved_has_no_blocking_at_level_5(
        self,
        group: str,
        target_level: int,
    ) -> None:
        """When all PAs are Fully achieved (level 5), blocking_attributes is empty."""
        attr_map = {pa: "Fully achieved" for pa in ALL_PAS}
        ratings = _ratings_from_attribute_map(attr_map, group)
        calc = CapabilityLevelCalculator(target_level=target_level)
        results = calc.calculate(ratings, [group])
        result = results[group]

        assert result.blocking_attributes == [], (
            f"All PAs are Fully achieved but blocking_attributes is "
            f"{result.blocking_attributes}"
        )
