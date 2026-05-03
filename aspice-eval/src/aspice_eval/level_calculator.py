"""Capability level calculator for ASPICE process attribute ratings.

Aggregates per-criteria ratings into per-process-attribute ratings using
a worst-case approach, then determines the highest achieved capability
level per process group following ASPICE cumulative achievement rules.

Requirements: 5.1, 5.2, 5.3
"""

from __future__ import annotations

from aspice_eval.models import (
    VALID_RATINGS,
    CapabilityLevelResult,
    CriteriaRating,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Rating ordering from best (index 0) to worst (index 3).
_RATING_ORDER: list[str] = [
    "Fully achieved",
    "Largely achieved",
    "Partially achieved",
    "Not achieved",
]

# Process attributes required at each capability level (1–5).
# Level 0 has no PAs (Incomplete).
LEVEL_ATTRIBUTES: dict[int, list[str]] = {
    1: ["PA 1.1"],
    2: ["PA 2.1", "PA 2.2"],
    3: ["PA 3.1", "PA 3.2"],
    4: ["PA 4.1", "PA 4.2"],
    5: ["PA 5.1", "PA 5.2"],
}

# Ratings that count as "achieved" for a process attribute.
_ACHIEVED_RATINGS: frozenset[str] = frozenset({"Fully achieved", "Largely achieved"})


def _worst_rating(ratings: list[str]) -> str:
    """Return the worst (lowest) rating from a list of rating strings.

    Uses ``_RATING_ORDER`` so that a higher index means a worse rating.
    If the list is empty, returns ``"Not achieved"`` as the conservative
    default.
    """
    if not ratings:
        return "Not achieved"

    worst_idx = 0
    for r in ratings:
        idx = _RATING_ORDER.index(r) if r in _RATING_ORDER else len(_RATING_ORDER) - 1
        if idx > worst_idx:
            worst_idx = idx
    return _RATING_ORDER[worst_idx]


class CapabilityLevelCalculator:
    """Computes capability levels from process attribute ratings.

    Applies ASPICE cumulative achievement rules:

    - A level *N* is achieved when **all** process attributes at level *N*
      are rated "Largely achieved" or "Fully achieved".
    - All lower levels must also be achieved (cumulative).
    - ``blocking_attributes`` lists exactly those PAs at
      ``achieved_level + 1`` that are "Partially achieved" or
      "Not achieved".
    """

    def __init__(self, target_level: int = 3) -> None:
        self._target_level = target_level

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate(
        self,
        ratings: list[CriteriaRating],
        process_groups: list[str],
    ) -> dict[str, CapabilityLevelResult]:
        """Calculate the highest achieved capability level per process group.

        Parameters
        ----------
        ratings:
            Per-criteria ratings from the evaluator.
        process_groups:
            Process groups to calculate for.

        Returns
        -------
        dict[str, CapabilityLevelResult]
            Mapping of process group code to its capability level result.
        """
        results: dict[str, CapabilityLevelResult] = {}

        for group in process_groups:
            group_ratings = [r for r in ratings if r.process_group == group]
            attribute_ratings = self._aggregate_attribute_ratings(group_ratings)
            achieved_level = self._determine_achieved_level(attribute_ratings)
            blocking = self._find_blocking_attributes(
                attribute_ratings, achieved_level,
            )

            results[group] = CapabilityLevelResult(
                process_group=group,
                achieved_level=achieved_level,
                target_level=self._target_level,
                attribute_ratings=attribute_ratings,
                blocking_attributes=blocking,
            )

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate_attribute_ratings(
        ratings: list[CriteriaRating],
    ) -> dict[str, str]:
        """Aggregate per-criteria ratings into per-PA ratings (worst case).

        Groups all criteria ratings by ``process_attribute`` and takes the
        worst rating in each group as the aggregate PA rating.

        Parameters
        ----------
        ratings:
            Criteria ratings for a single process group.

        Returns
        -------
        dict[str, str]
            Mapping of PA identifier (e.g. ``"PA 2.1"``) to its aggregate
            rating string.
        """
        pa_ratings: dict[str, list[str]] = {}
        for r in ratings:
            pa_ratings.setdefault(r.process_attribute, []).append(r.rating)

        return {pa: _worst_rating(vals) for pa, vals in pa_ratings.items()}

    @staticmethod
    def _determine_achieved_level(
        attribute_ratings: dict[str, str],
    ) -> int:
        """Determine the highest achieved capability level.

        Iterates from level 1 upward. A level is achieved only when
        **all** PAs at that level are in ``_ACHIEVED_RATINGS`` and all
        lower levels are also achieved (cumulative rule).

        If no ratings exist for any PA at a given level, that level is
        considered not achieved (conservative).

        Parameters
        ----------
        attribute_ratings:
            Aggregated PA → rating mapping.

        Returns
        -------
        int
            The highest achieved level (0–5).
        """
        achieved = 0

        for level in range(1, 6):
            pas_at_level = LEVEL_ATTRIBUTES[level]
            all_achieved = True

            for pa in pas_at_level:
                rating = attribute_ratings.get(pa)
                if rating is None or rating not in _ACHIEVED_RATINGS:
                    all_achieved = False
                    break

            if all_achieved:
                achieved = level
            else:
                # Cumulative rule: stop at first unachieved level
                break

        return achieved

    @staticmethod
    def _find_blocking_attributes(
        attribute_ratings: dict[str, str],
        achieved_level: int,
    ) -> list[str]:
        """Find PAs at the next level that block advancement.

        Returns exactly those PAs at ``achieved_level + 1`` whose rating
        is "Partially achieved" or "Not achieved" (i.e. not in
        ``_ACHIEVED_RATINGS``).

        If ``achieved_level`` is already 5 (maximum), returns an empty
        list since there is no next level.

        Parameters
        ----------
        attribute_ratings:
            Aggregated PA → rating mapping.
        achieved_level:
            The current highest achieved level.

        Returns
        -------
        list[str]
            PA identifiers that block the next level.
        """
        next_level = achieved_level + 1
        if next_level > 5:
            return []

        blocking: list[str] = []
        for pa in LEVEL_ATTRIBUTES[next_level]:
            rating = attribute_ratings.get(pa)
            # If no rating exists for this PA, it's blocking (not achieved)
            if rating is None or rating not in _ACHIEVED_RATINGS:
                blocking.append(pa)

        return blocking
