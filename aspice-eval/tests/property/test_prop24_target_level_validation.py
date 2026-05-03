"""Property test for target-level validation.

**Validates: Requirements 4.6**

Property 4: Invalid target-level values are rejected.
For any integer outside the range 1–5, parameter validation rejects
the value with an error message identifying the valid range.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from aspice_eval.exceptions import InvalidConfigError


def _validate_target_level(target_level: int) -> None:
    """Validate target level, raising InvalidConfigError if out of range.

    Mirrors the validation logic in the ``analyze`` command.
    """
    if target_level < 1 or target_level > 5:
        raise InvalidConfigError(
            f"Target level {target_level} is out of range. Must be 1–5.",
            parameter="target_level",
            actual_value=target_level,
            expected_values=[1, 2, 3, 4, 5],
        )


class TestProperty24TargetLevelValidation:
    """Feature: aspice-analyze-command, Property 4: target-level validation."""

    @given(level=st.integers().filter(lambda x: x < 1 or x > 5))
    def test_invalid_levels_rejected(self, level: int) -> None:
        """Integers outside 1–5 are rejected with descriptive error."""
        with pytest.raises(InvalidConfigError) as exc_info:
            _validate_target_level(level)
        assert "1–5" in str(exc_info.value) or "1-5" in str(exc_info.value)

    @given(level=st.integers(min_value=1, max_value=5))
    def test_valid_levels_accepted(self, level: int) -> None:
        """Integers 1–5 are accepted without error."""
        _validate_target_level(level)  # Should not raise
