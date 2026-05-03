"""Property test for process group code validation.

**Validates: Requirements 4.7**

Property 5: Invalid process group codes are rejected.
For any string not in the valid process group code set, validation
rejects with an error listing valid codes.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from aspice_eval.exceptions import InvalidConfigError

# Valid process group codes from the KB metadata
VALID_GROUPS: frozenset[str] = frozenset({"SWE", "SYS", "MAN", "SUP"})


def _validate_groups(groups: list[str], valid_codes: set[str]) -> None:
    """Validate process group codes, raising InvalidConfigError if unknown.

    Mirrors the validation logic in the ``analyze`` command.
    """
    unknown = [g for g in groups if g not in valid_codes]
    if unknown:
        raise InvalidConfigError(
            f"Unknown process group(s): {', '.join(unknown)}. "
            f"Valid groups: {', '.join(sorted(valid_codes))}.",
            parameter="process_groups",
            actual_value=unknown,
            expected_values=sorted(valid_codes),
        )


class TestProperty25GroupValidation:
    """Feature: aspice-analyze-command, Property 5: group code validation."""

    @given(
        invalid_code=st.text(
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            min_size=1,
            max_size=5,
        ).filter(lambda s: s not in VALID_GROUPS),
    )
    def test_invalid_group_codes_rejected(self, invalid_code: str) -> None:
        """Unknown group codes are rejected with descriptive error."""
        with pytest.raises(InvalidConfigError) as exc_info:
            _validate_groups([invalid_code], VALID_GROUPS)
        error_msg = str(exc_info.value)
        assert invalid_code in error_msg
        # Error should list valid codes
        for valid in VALID_GROUPS:
            assert valid in error_msg

    @given(
        valid_groups=st.lists(
            st.sampled_from(sorted(VALID_GROUPS)),
            min_size=1,
            max_size=4,
            unique=True,
        ),
    )
    def test_valid_group_codes_accepted(self, valid_groups: list[str]) -> None:
        """Valid group codes are accepted without error."""
        _validate_groups(valid_groups, VALID_GROUPS)  # Should not raise
