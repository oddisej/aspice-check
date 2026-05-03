"""Property 2: Schema validation accepts complete entries and rejects incomplete entries.

Generate random criteria dicts with varying field presence; verify schema
validation accepts complete entries and rejects incomplete ones.

**Validates: Requirements 1.2, 2.2**
"""

from __future__ import annotations

import pathlib
from typing import Any

from hypothesis import given, assume, strategies as st

from aspice_eval.exceptions import KBValidationError
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
# Strategies — building blocks
# ---------------------------------------------------------------------------

# Process group codes: 2-4 uppercase letters
_group_codes = st.from_regex(r"^[A-Z]{2,4}$", fullmatch=True)

_group_names = st.text(
    alphabet=st.characters(categories=("L", "Zs")),
    min_size=3,
    max_size=30,
).filter(lambda s: s.strip())

# Process IDs like "SWE.1", "TST.3"
_process_ids = st.builds(
    lambda code, num: f"{code}.{num}",
    _group_codes,
    st.integers(min_value=1, max_value=9),
)

_short_text = st.text(
    alphabet=st.characters(categories=("L", "N", "Zs")),
    min_size=3,
    max_size=60,
).filter(lambda s: s.strip())

_bp_ids = st.builds(lambda n: f"BP{n}", st.integers(min_value=1, max_value=20))


def _outcome_st() -> st.SearchStrategy[dict[str, Any]]:
    """Strategy for a single process outcome."""
    return st.fixed_dictionaries(
        {
            "id": st.integers(min_value=1, max_value=10),
            "description": _short_text,
        }
    )


def _bp_st() -> st.SearchStrategy[dict[str, Any]]:
    """Strategy for a single base practice."""
    return st.fixed_dictionaries(
        {
            "bp_id": _bp_ids,
            "title": _short_text,
            "description": _short_text,
        }
    )


def _info_item_st() -> st.SearchStrategy[dict[str, Any]]:
    """Strategy for a single output information item."""
    return st.fixed_dictionaries(
        {
            "item_id": st.builds(
                lambda a, b: f"{a:02d}-{b:02d}",
                st.integers(min_value=1, max_value=99),
                st.integers(min_value=1, max_value=99),
            ),
            "name": _short_text,
        }
    )


def _process_st() -> st.SearchStrategy[dict[str, Any]]:
    """Strategy for a complete, valid process entry."""
    return st.fixed_dictionaries(
        {
            "process_id": _process_ids,
            "process_name": _short_text,
            "process_purpose": _short_text,
            "process_outcomes": st.lists(_outcome_st(), min_size=1, max_size=3),
            "base_practices": st.lists(_bp_st(), min_size=1, max_size=3),
            "output_information_items": st.lists(
                _info_item_st(), min_size=1, max_size=3
            ),
        }
    )


def _valid_criteria_file_st() -> st.SearchStrategy[dict[str, Any]]:
    """Strategy for a complete, valid criteria file (process_group + processes)."""
    return st.fixed_dictionaries(
        {
            "process_group": st.fixed_dictionaries(
                {
                    "code": _group_codes,
                    "name": _group_names,
                }
            ),
            "processes": st.lists(_process_st(), min_size=1, max_size=3),
        }
    )


# Required fields at the process level in the schema
_REQUIRED_PROCESS_FIELDS = [
    "process_id",
    "process_name",
    "process_purpose",
    "process_outcomes",
    "base_practices",
    "output_information_items",
]

# Required fields at the top level
_REQUIRED_TOP_FIELDS = ["process_group", "processes"]


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestProperty02SchemaValidation:
    """Property 2: Schema validation accepts complete entries and rejects
    incomplete entries."""

    @given(doc=_valid_criteria_file_st())
    def test_complete_entries_are_accepted(self, doc: dict[str, Any]) -> None:
        """A criteria file with all required fields passes schema validation."""
        validator = KBValidator(_SCHEMA_PATH)
        # Should not raise
        errors = validator.validate_schema(doc)
        assert errors == []

    @given(
        doc=_valid_criteria_file_st(),
        field_to_remove=st.sampled_from(_REQUIRED_TOP_FIELDS),
    )
    def test_missing_top_level_field_is_rejected(
        self,
        doc: dict[str, Any],
        field_to_remove: str,
    ) -> None:
        """Removing a required top-level field causes schema validation to fail."""
        doc = dict(doc)  # shallow copy
        del doc[field_to_remove]

        validator = KBValidator(_SCHEMA_PATH)
        try:
            validator.validate_schema(doc)
            # If it didn't raise, that's a failure
            assert False, (
                f"Expected KBValidationError when '{field_to_remove}' is missing"
            )
        except KBValidationError:
            pass  # expected

    @given(
        doc=_valid_criteria_file_st(),
        field_to_remove=st.sampled_from(_REQUIRED_PROCESS_FIELDS),
    )
    def test_missing_process_field_is_rejected(
        self,
        doc: dict[str, Any],
        field_to_remove: str,
    ) -> None:
        """Removing a required field from a process entry causes validation to fail."""
        assume(len(doc["processes"]) > 0)

        # Deep copy the first process and remove the field
        import copy

        doc = copy.deepcopy(doc)
        del doc["processes"][0][field_to_remove]

        validator = KBValidator(_SCHEMA_PATH)
        try:
            validator.validate_schema(doc)
            assert False, (
                f"Expected KBValidationError when process field "
                f"'{field_to_remove}' is missing"
            )
        except KBValidationError:
            pass  # expected

    @given(doc=_valid_criteria_file_st())
    def test_empty_base_practices_is_rejected(
        self, doc: dict[str, Any]
    ) -> None:
        """A process with an empty base_practices array fails validation."""
        import copy

        doc = copy.deepcopy(doc)
        doc["processes"][0]["base_practices"] = []

        validator = KBValidator(_SCHEMA_PATH)
        try:
            validator.validate_schema(doc)
            assert False, "Expected KBValidationError for empty base_practices"
        except KBValidationError:
            pass  # expected

    @given(doc=_valid_criteria_file_st())
    def test_empty_process_outcomes_is_rejected(
        self, doc: dict[str, Any]
    ) -> None:
        """A process with an empty process_outcomes array fails validation."""
        import copy

        doc = copy.deepcopy(doc)
        doc["processes"][0]["process_outcomes"] = []

        validator = KBValidator(_SCHEMA_PATH)
        try:
            validator.validate_schema(doc)
            assert False, "Expected KBValidationError for empty process_outcomes"
        except KBValidationError:
            pass  # expected

    @given(doc=_valid_criteria_file_st())
    def test_empty_output_information_items_is_rejected(
        self, doc: dict[str, Any]
    ) -> None:
        """A process with an empty output_information_items array fails validation."""
        import copy

        doc = copy.deepcopy(doc)
        doc["processes"][0]["output_information_items"] = []

        validator = KBValidator(_SCHEMA_PATH)
        try:
            validator.validate_schema(doc)
            assert False, (
                "Expected KBValidationError for empty output_information_items"
            )
        except KBValidationError:
            pass  # expected

    @given(
        code=_group_codes,
        name=_group_names,
    )
    def test_any_valid_group_code_is_accepted(
        self, code: str, name: str
    ) -> None:
        """Schema accepts any 2-4 uppercase letter group code, supporting
        extensibility to new standards."""
        doc = {
            "process_group": {"code": code, "name": name},
            "processes": [
                {
                    "process_id": f"{code}.1",
                    "process_name": "Test Process",
                    "process_purpose": "Test purpose.",
                    "process_outcomes": [
                        {"id": 1, "description": "Test outcome."},
                    ],
                    "base_practices": [
                        {
                            "bp_id": "BP1",
                            "title": "Test practice",
                            "description": "Test description.",
                        },
                    ],
                    "output_information_items": [
                        {"item_id": "01-01", "name": "Test item"},
                    ],
                }
            ],
        }
        validator = KBValidator(_SCHEMA_PATH)
        errors = validator.validate_schema(doc)
        assert errors == []
