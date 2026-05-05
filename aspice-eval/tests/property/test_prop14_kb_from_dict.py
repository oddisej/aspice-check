"""Property 14: KnowledgeBase.from_dict round-trip.

For any criteria dictionary conforming to the bundled criteria JSON
Schema, ``KnowledgeBase.from_dict(data)`` produces an instance whose
``get_criteria()`` exposes the same process groups and base practices
that the input data defines. Conversely, any dictionary that violates
the schema causes ``from_dict`` to raise :class:`KBValidationError`.

**Validates: Requirements 14.3, 14.4, 14.5**
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings, strategies as st

from aspice_eval.exceptions import KBValidationError
from aspice_eval.knowledge_base import KnowledgeBase


# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

GROUP_CODES = ["SWE", "SYS", "MAN", "SUP"]


def _make_valid_criteria_file(
    group_code: str,
    process_suffixes: list[int],
    base_practice_count: int = 1,
) -> dict[str, Any]:
    """Build a criteria-file dict that satisfies ``criteria_schema.json``."""
    processes = []
    for suffix in process_suffixes:
        process_id = f"{group_code}.{suffix}"
        base_practices = [
            {
                "bp_id": f"BP{i}",
                "title": f"Practice {i}",
                "description": f"Base practice {i} for {process_id}.",
                "maps_to_outcomes": [1],
            }
            for i in range(1, base_practice_count + 1)
        ]
        processes.append(
            {
                "process_id": process_id,
                "process_name": f"Process {process_id}",
                "process_purpose": f"Purpose of {process_id}.",
                "process_outcomes": [
                    {"id": 1, "description": f"Outcome for {process_id}."},
                ],
                "base_practices": base_practices,
                "output_information_items": [
                    {
                        "item_id": "17-01",
                        "name": "Sample output",
                        "maps_to_outcomes": [1],
                    },
                ],
            }
        )
    return {
        "process_group": {
            "code": group_code,
            "name": f"{group_code} group",
        },
        "processes": processes,
    }


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_group_code_st = st.sampled_from(GROUP_CODES)

# 1–3 unique process suffixes per criteria file
_process_suffixes_st = st.lists(
    st.integers(min_value=1, max_value=6),
    min_size=1,
    max_size=3,
    unique=True,
)

_base_practice_count_st = st.integers(min_value=1, max_value=3)


@st.composite
def _single_group_payload(draw: st.DrawFn) -> dict[str, Any]:
    """Build a payload with exactly one criteria file (one group)."""
    group = draw(_group_code_st)
    suffixes = draw(_process_suffixes_st)
    bp_count = draw(_base_practice_count_st)
    return {
        "criteria_files": [
            _make_valid_criteria_file(group, suffixes, bp_count),
        ],
        "metadata": None,
    }


# ---------------------------------------------------------------------------
# Unit-style sanity tests
# ---------------------------------------------------------------------------


class TestFromDictBasics:
    """Smoke tests for the happy paths of :meth:`KnowledgeBase.from_dict`."""

    def test_returns_knowledge_base_instance(self) -> None:
        data = {
            "criteria_files": [_make_valid_criteria_file("SWE", [1])],
            "metadata": None,
        }
        kb = KnowledgeBase.from_dict(data)
        assert isinstance(kb, KnowledgeBase)

    def test_get_criteria_works_without_filesystem(self) -> None:
        """``get_criteria`` must not touch the filesystem."""
        data = {
            "criteria_files": [_make_valid_criteria_file("SWE", [1, 2])],
            "metadata": None,
        }
        kb = KnowledgeBase.from_dict(data)
        entries = kb.get_criteria(["SWE"], max_capability_level=1)
        assert len(entries) == 2  # one BP per process, two processes
        assert {e.process_group for e in entries} == {"SWE"}

    def test_empty_criteria_files_returns_empty_kb(self) -> None:
        kb = KnowledgeBase.from_dict({"criteria_files": [], "metadata": None})
        assert kb.get_criteria(["SWE"], max_capability_level=5) == []

    def test_non_dict_input_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            KnowledgeBase.from_dict("not a dict")  # type: ignore[arg-type]

    def test_schema_violation_raises_kb_validation_error(self) -> None:
        bad = {
            "criteria_files": [
                {
                    # Missing required "processes" field and wrong group code
                    "process_group": {"code": "swe", "name": "bad"},
                },
            ],
            "metadata": None,
        }
        with pytest.raises(KBValidationError):
            KnowledgeBase.from_dict(bad)

    def test_standard_parameter_defaults_to_custom(self) -> None:
        kb = KnowledgeBase.from_dict(
            {"criteria_files": [_make_valid_criteria_file("SWE", [1])], "metadata": None}
        )
        assert getattr(kb, "_standard", "custom") == "custom"

    def test_standard_parameter_is_stored(self) -> None:
        kb = KnowledgeBase.from_dict(
            {"criteria_files": [_make_valid_criteria_file("SWE", [1])], "metadata": None},
            standard="iso26262",
        )
        assert getattr(kb, "_standard", None) == "iso26262"


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------


class TestProperty14FromDictRoundTrip:
    """Property 14: round-trip between input dict and ``get_criteria`` output."""

    @given(payload=_single_group_payload())
    @settings(deadline=None)
    def test_group_code_is_preserved(self, payload: dict[str, Any]) -> None:
        """Entries carry the exact group code from the input criteria file."""
        expected_group = payload["criteria_files"][0]["process_group"]["code"]

        kb = KnowledgeBase.from_dict(payload)
        entries = kb.get_criteria([expected_group], max_capability_level=1)

        assert entries, "Expected at least one CriteriaEntry"
        for entry in entries:
            assert entry.process_group == expected_group

    @given(payload=_single_group_payload())
    @settings(deadline=None)
    def test_entry_count_matches_base_practice_count(
        self, payload: dict[str, Any]
    ) -> None:
        """One CriteriaEntry is produced per (process, base_practice)."""
        group_code = payload["criteria_files"][0]["process_group"]["code"]
        processes = payload["criteria_files"][0]["processes"]
        expected_count = sum(len(p["base_practices"]) for p in processes)

        kb = KnowledgeBase.from_dict(payload)
        entries = kb.get_criteria([group_code], max_capability_level=1)

        assert len(entries) == expected_count

    @given(payload=_single_group_payload())
    @settings(deadline=None)
    def test_process_ids_are_preserved(self, payload: dict[str, Any]) -> None:
        """Every input process_id shows up on at least one criteria entry."""
        group_code = payload["criteria_files"][0]["process_group"]["code"]
        expected_ids = {
            proc["process_id"]
            for proc in payload["criteria_files"][0]["processes"]
        }

        kb = KnowledgeBase.from_dict(payload)
        entries = kb.get_criteria([group_code], max_capability_level=1)

        actual_ids = {entry.process_id for entry in entries}
        assert actual_ids == expected_ids

    @given(
        bad_field=st.sampled_from(
            [
                # Missing required "processes"
                {"process_group": {"code": "SWE", "name": "X"}},
                # Missing required "process_group"
                {"processes": []},
                # Invalid group code pattern (lowercase)
                {
                    "process_group": {"code": "swe", "name": "X"},
                    "processes": [],
                },
                # process_group missing "name"
                {
                    "process_group": {"code": "SWE"},
                    "processes": [],
                },
            ]
        )
    )
    @settings(deadline=None)
    def test_invalid_payload_raises_kb_validation_error(
        self, bad_field: dict[str, Any]
    ) -> None:
        """Any schema-violating criteria file triggers KBValidationError."""
        with pytest.raises(KBValidationError):
            KnowledgeBase.from_dict(
                {"criteria_files": [bad_field], "metadata": None}
            )
