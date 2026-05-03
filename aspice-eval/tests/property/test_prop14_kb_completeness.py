"""Property 14: KB completeness validator identifies all missing criteria tuples.

Generate random criteria sets with deliberate gaps; verify validator reports
exactly the missing (group, level, PA) tuples.

**Validates: Requirements 8.1, 8.2**
"""

from __future__ import annotations

import pathlib
from typing import Any

from hypothesis import given, assume, strategies as st

from aspice_eval.kb_validator import KBValidator

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SCHEMA_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "knowledge_base"
    / "schema"
    / "criteria_schema.json"
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROCESS_GROUPS = ["SWE", "SYS", "MAN", "SUP"]

# All generic PA keys with their (PA id, capability level)
_PA_MAP: dict[str, tuple[str, int]] = {
    "PA_2_1": ("PA 2.1", 2),
    "PA_2_2": ("PA 2.2", 2),
    "PA_3_1": ("PA 3.1", 3),
    "PA_3_2": ("PA 3.2", 3),
    "PA_4_1": ("PA 4.1", 4),
    "PA_4_2": ("PA 4.2", 4),
    "PA_5_1": ("PA 5.1", 5),
    "PA_5_2": ("PA 5.2", 5),
}

ALL_PA_KEYS = list(_PA_MAP.keys())

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_process(proc_id: str) -> dict[str, Any]:
    """Return a minimal valid process with base practices."""
    return {
        "process_id": proc_id,
        "process_name": f"Process {proc_id}",
        "process_purpose": f"Purpose of {proc_id}.",
        "process_outcomes": [
            {"id": 1, "description": f"Outcome for {proc_id}."},
        ],
        "base_practices": [
            {
                "bp_id": "BP1",
                "title": "Practice 1",
                "description": f"Base practice for {proc_id}.",
                "maps_to_outcomes": [1],
            },
        ],
        "output_information_items": [
            {"item_id": "99-01", "name": "Test item", "maps_to_outcomes": [1]},
        ],
    }


def _make_generic_practice(pa_key: str) -> dict[str, Any]:
    """Return a minimal valid generic practice section for the given PA key."""
    pa_id, cl = _PA_MAP[pa_key]
    return {
        "process_attribute_id": pa_id,
        "process_attribute_name": f"Attribute {pa_id}",
        "capability_level": cl,
        "practices": [
            {
                "gp_id": f"GP {pa_id.replace('PA ', '')}.1",
                "title": f"Practice for {pa_id}",
                "description": f"Generic practice for {pa_id}.",
            },
        ],
    }


def _build_criteria_file(
    group_code: str,
    included_processes: list[str],
    included_pa_keys: list[str],
) -> dict[str, Any]:
    """Build a criteria file dict with specified processes and PA keys."""
    doc: dict[str, Any] = {
        "process_group": {"code": group_code, "name": f"Group {group_code}"},
        "processes": [_make_process(pid) for pid in included_processes],
    }
    if included_pa_keys:
        doc["generic_practices"] = {
            key: _make_generic_practice(key) for key in included_pa_keys
        }
    return doc


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate 1-3 process groups, each with 1-4 process IDs
_group_config_st = st.fixed_dictionaries(
    {
        "code": st.sampled_from(PROCESS_GROUPS),
        "process_count": st.integers(min_value=1, max_value=4),
    }
)


@st.composite
def _kb_with_gaps(draw: st.DrawFn):
    """Generate a KB configuration with deliberate gaps.

    Returns (metadata, criteria_files, expected_missing_tuples) where
    expected_missing_tuples is a set of (group_code, capability_level, pa_id)
    or (group_code, capability_level, pa_id, process_id) for CL1 gaps.
    """
    # Pick 1-3 unique groups
    num_groups = draw(st.integers(min_value=1, max_value=3))
    group_codes = draw(
        st.lists(
            st.sampled_from(PROCESS_GROUPS),
            min_size=num_groups,
            max_size=num_groups,
            unique=True,
        )
    )

    metadata_groups = []
    criteria_files = []
    expected_missing: set[tuple[str, ...]] = set()

    for code in group_codes:
        # Define expected processes for this group
        num_procs = draw(st.integers(min_value=1, max_value=3))
        all_proc_ids = [f"{code}.{i}" for i in range(1, num_procs + 1)]

        metadata_groups.append(
            {"code": code, "name": f"Group {code}", "processes": all_proc_ids}
        )

        # Decide which processes to include (some may be missing = CL1 gaps)
        include_mask = draw(
            st.lists(
                st.booleans(),
                min_size=num_procs,
                max_size=num_procs,
            )
        )
        included_procs = [
            pid for pid, inc in zip(all_proc_ids, include_mask) if inc
        ]

        # Track CL1 gaps: processes not included
        for pid, inc in zip(all_proc_ids, include_mask):
            if not inc:
                expected_missing.add((code, 1, "PA 1.1", pid))

        # Decide which generic PAs to include (some may be missing = CL2-5 gaps)
        pa_include_mask = draw(
            st.lists(
                st.booleans(),
                min_size=len(ALL_PA_KEYS),
                max_size=len(ALL_PA_KEYS),
            )
        )
        included_pa_keys = [
            key for key, inc in zip(ALL_PA_KEYS, pa_include_mask) if inc
        ]

        # Track CL2-5 gaps: PAs not included
        for key, inc in zip(ALL_PA_KEYS, pa_include_mask):
            if not inc:
                pa_id, cl = _PA_MAP[key]
                expected_missing.add((code, cl, pa_id))

        # Build the criteria file
        criteria_files.append(
            _build_criteria_file(code, included_procs, included_pa_keys)
        )

    metadata = {"process_groups": metadata_groups}
    return metadata, criteria_files, expected_missing


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestProperty14KBCompleteness:
    """Property 14: KB completeness validator identifies all missing criteria tuples."""

    @given(data=_kb_with_gaps())
    def test_validator_identifies_exactly_missing_tuples(
        self,
        data: tuple[
            dict[str, Any],
            list[dict[str, Any]],
            set[tuple[str, ...]],
        ],
    ) -> None:
        """validate_completeness reports exactly the missing (group, level, PA)
        tuples — no false positives, no false negatives."""
        metadata, criteria_files, expected_missing = data

        validator = KBValidator(_SCHEMA_PATH)
        report = validator.validate_completeness(
            criteria_files, metadata=metadata
        )

        # Extract actual missing tuples from the report
        actual_missing: set[tuple[str, ...]] = set()
        for gap in report.missing_entries:
            group = gap["process_group"]
            cl = gap["capability_level"]
            pa = gap["process_attribute"]
            if "process_id" in gap:
                actual_missing.add((group, cl, pa, gap["process_id"]))
            else:
                actual_missing.add((group, cl, pa))

        assert actual_missing == expected_missing, (
            f"Missing tuples mismatch.\n"
            f"Expected missing: {sorted(expected_missing)}\n"
            f"Actual missing:   {sorted(actual_missing)}"
        )

    @given(data=_kb_with_gaps())
    def test_is_complete_flag_matches_missing_entries(
        self,
        data: tuple[
            dict[str, Any],
            list[dict[str, Any]],
            set[tuple[str, ...]],
        ],
    ) -> None:
        """is_complete is True iff there are no missing entries."""
        metadata, criteria_files, expected_missing = data

        validator = KBValidator(_SCHEMA_PATH)
        report = validator.validate_completeness(
            criteria_files, metadata=metadata
        )

        if expected_missing:
            assert report.is_complete is False
        else:
            assert report.is_complete is True

    @given(data=_kb_with_gaps())
    def test_total_counts_are_consistent(
        self,
        data: tuple[
            dict[str, Any],
            list[dict[str, Any]],
            set[tuple[str, ...]],
        ],
    ) -> None:
        """total_expected == total_found + len(missing_entries)."""
        metadata, criteria_files, _ = data

        validator = KBValidator(_SCHEMA_PATH)
        report = validator.validate_completeness(
            criteria_files, metadata=metadata
        )

        assert report.total_expected == report.total_found + len(
            report.missing_entries
        ), (
            f"Count mismatch: expected={report.total_expected}, "
            f"found={report.total_found}, "
            f"missing={len(report.missing_entries)}"
        )
