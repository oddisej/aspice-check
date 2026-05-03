"""Property 1: Criteria filtering returns exactly matching entries.

Generate random criteria sets and filters (process groups, max level); verify
``get_criteria`` returns exactly entries matching both conditions — no more,
no less.

**Validates: Requirements 1.1, 4.1**
"""

from __future__ import annotations

import pathlib
from typing import Any

import yaml
from hypothesis import given, settings, strategies as st

from aspice_eval.knowledge_base import KnowledgeBase

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROCESS_GROUPS = ["SWE", "SYS", "MAN", "SUP"]

# PA keys in generic_practices, mapped to (PA id, capability level)
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

# ---------------------------------------------------------------------------
# Helpers — build synthetic KB YAML files on disk
# ---------------------------------------------------------------------------


def _make_process(proc_id: str, num_bps: int = 1) -> dict[str, Any]:
    """Return a minimal valid process dict."""
    return {
        "process_id": proc_id,
        "process_name": f"Process {proc_id}",
        "process_purpose": f"Purpose of {proc_id}.",
        "process_outcomes": [
            {"id": 1, "description": f"Outcome for {proc_id}."},
        ],
        "base_practices": [
            {
                "bp_id": f"BP{i}",
                "title": f"Practice {i}",
                "description": f"Base practice {i} for {proc_id}.",
                "maps_to_outcomes": [1],
            }
            for i in range(1, num_bps + 1)
        ],
        "output_information_items": [
            {"item_id": "99-01", "name": "Test item", "maps_to_outcomes": [1]},
        ],
    }


def _make_generic_practice(pa_key: str, pa_id: str, cl: int) -> dict[str, Any]:
    """Return a minimal valid generic practice section."""
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
    process_ids: list[str],
    include_pa_keys: list[str],
    num_bps: int = 1,
) -> dict[str, Any]:
    """Build a synthetic criteria file dict for one process group."""
    doc: dict[str, Any] = {
        "process_group": {"code": group_code, "name": f"Group {group_code}"},
        "processes": [_make_process(pid, num_bps) for pid in process_ids],
    }
    if include_pa_keys:
        doc["generic_practices"] = {
            key: _make_generic_practice(key, pa_id, cl)
            for key in include_pa_keys
            if (pa_id := _PA_MAP[key][0]) and (cl := _PA_MAP[key][1])
        }
    return doc


def _write_kb(
    tmp_path: pathlib.Path,
    groups: dict[str, dict[str, Any]],
) -> pathlib.Path:
    """Write a synthetic KB directory structure and return the kb_path.

    Parameters
    ----------
    tmp_path:
        pytest ``tmp_path`` fixture.
    groups:
        Mapping of group_code -> {"processes": [...], "max_level": int}
        describing what to generate.

    Returns the path to the KB root (containing ``schema/`` and ``aspice/``).
    """
    kb_root = tmp_path / "knowledge_base"
    schema_dir = kb_root / "schema"
    aspice_dir = kb_root / "aspice"
    schema_dir.mkdir(parents=True)
    aspice_dir.mkdir(parents=True)

    # Copy the real schema file
    import json

    real_schema = (
        pathlib.Path(__file__).resolve().parents[2]
        / "knowledge_base"
        / "schema"
        / "criteria_schema.json"
    )
    import shutil

    shutil.copy(real_schema, schema_dir / "criteria_schema.json")

    # Build and write each group file
    for code, info in groups.items():
        process_ids = info["processes"]
        max_level = info["max_level"]

        # Determine which PA keys to include based on max_level
        pa_keys = [
            key for key, (_, cl) in _PA_MAP.items() if cl <= max_level
        ]

        doc = _build_criteria_file(
            group_code=code,
            process_ids=process_ids,
            include_pa_keys=pa_keys,
            num_bps=info.get("num_bps", 1),
        )
        with open(aspice_dir / f"{code.lower()}.yaml", "w") as fh:
            yaml.dump(doc, fh, default_flow_style=False)

    return kb_root


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate a random set of process groups (1-4 groups, each with 1-3 processes)
_group_code_st = st.sampled_from(PROCESS_GROUPS)

_group_info_st = st.fixed_dictionaries(
    {
        "processes": st.lists(
            st.integers(min_value=1, max_value=6),
            min_size=1,
            max_size=3,
        ).map(lambda nums: list(dict.fromkeys(nums))),  # deduplicate
        "max_level": st.integers(min_value=1, max_value=5),
        "num_bps": st.integers(min_value=1, max_value=3),
    }
)


def _groups_strategy():
    """Strategy that generates a dict of 1-4 process groups with their config."""
    return (
        st.lists(
            st.tuples(_group_code_st, _group_info_st),
            min_size=1,
            max_size=4,
        )
        .map(dict)
        .filter(lambda d: len(d) >= 1)
        .map(
            lambda d: {
                code: {
                    **info,
                    "processes": [f"{code}.{n}" for n in info["processes"]],
                }
                for code, info in d.items()
            }
        )
    )


# Filter parameters: which groups to query and max capability level
_filter_groups_st = st.lists(
    st.sampled_from(PROCESS_GROUPS),
    min_size=1,
    max_size=4,
).map(lambda xs: list(dict.fromkeys(xs)))

_max_level_st = st.integers(min_value=1, max_value=5)


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------


class TestProperty01CriteriaFiltering:
    """Property 1: Criteria filtering returns exactly matching entries."""

    @given(
        groups_config=_groups_strategy(),
        filter_groups=_filter_groups_st,
        max_level=_max_level_st,
    )
    def test_filtering_returns_exactly_matching_entries(
        self,
        tmp_path_factory,
        groups_config: dict[str, dict[str, Any]],
        filter_groups: list[str],
        max_level: int,
    ) -> None:
        """get_criteria returns exactly entries whose process_group is in the
        requested groups AND whose capability_level <= max_level."""
        tmp_path = tmp_path_factory.mktemp("kb")
        kb_path = _write_kb(tmp_path, groups_config)

        kb = KnowledgeBase(kb_path)
        kb.load("aspice")

        # Get all criteria (all groups, max level 5)
        all_groups = list(groups_config.keys())
        all_entries = kb.get_criteria(all_groups, max_capability_level=5)

        # Get filtered criteria
        filtered = kb.get_criteria(filter_groups, max_capability_level=max_level)

        # Compute expected set: entries from all_entries that match both conditions
        expected = [
            e
            for e in all_entries
            if e.process_group in filter_groups and e.capability_level <= max_level
        ]

        # Compare by criteria_id sets (order-independent)
        filtered_ids = sorted(e.criteria_id for e in filtered)
        expected_ids = sorted(e.criteria_id for e in expected)

        assert filtered_ids == expected_ids, (
            f"Mismatch: filter_groups={filter_groups}, max_level={max_level}, "
            f"available_groups={all_groups}\n"
            f"Expected {len(expected_ids)} entries, got {len(filtered_ids)}"
        )

    @given(
        groups_config=_groups_strategy(),
        max_level=_max_level_st,
    )
    def test_no_entries_for_unrequested_groups(
        self,
        tmp_path_factory,
        groups_config: dict[str, dict[str, Any]],
        max_level: int,
    ) -> None:
        """get_criteria never returns entries for groups not in the filter."""
        tmp_path = tmp_path_factory.mktemp("kb")
        kb_path = _write_kb(tmp_path, groups_config)

        kb = KnowledgeBase(kb_path)
        kb.load("aspice")

        available_groups = list(groups_config.keys())
        if len(available_groups) < 2:
            # Need at least 2 groups to test exclusion
            return

        # Request only the first group
        requested = [available_groups[0]]
        filtered = kb.get_criteria(requested, max_capability_level=max_level)

        for entry in filtered:
            assert entry.process_group in requested, (
                f"Entry {entry.criteria_id} has group {entry.process_group} "
                f"but only {requested} were requested"
            )

    @given(
        groups_config=_groups_strategy(),
        filter_groups=_filter_groups_st,
        max_level=_max_level_st,
    )
    def test_no_entries_above_max_level(
        self,
        tmp_path_factory,
        groups_config: dict[str, dict[str, Any]],
        filter_groups: list[str],
        max_level: int,
    ) -> None:
        """get_criteria never returns entries with capability_level > max_level."""
        tmp_path = tmp_path_factory.mktemp("kb")
        kb_path = _write_kb(tmp_path, groups_config)

        kb = KnowledgeBase(kb_path)
        kb.load("aspice")

        filtered = kb.get_criteria(filter_groups, max_capability_level=max_level)

        for entry in filtered:
            assert entry.capability_level <= max_level, (
                f"Entry {entry.criteria_id} has level {entry.capability_level} "
                f"but max_level is {max_level}"
            )
