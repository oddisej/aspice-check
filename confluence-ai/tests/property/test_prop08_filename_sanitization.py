"""Feature: confluence-calendar-export, Property 8: Calendar filename sanitization produces filesystem-safe names."""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.calendar_export import _sanitize_calendar_name


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate arbitrary strings including Unicode, control chars, whitespace
_arbitrary_str_st = st.text(min_size=0, max_size=100)

# Generate strings that include spaces and special characters
_mixed_str_st = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z", "C"),
    ),
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

_SAFE_PATTERN = re.compile(r"[A-Za-z0-9_\-]+")


class TestProperty08FilenameSanitization:
    """Property 8: Calendar filename sanitization produces filesystem-safe names."""

    @given(name=_arbitrary_str_st)
    @settings(max_examples=100)
    def test_result_matches_safe_pattern_or_fallback(self, name: str) -> None:
        """Result matches [A-Za-z0-9_\\-]+ or equals 'calendar' fallback.

        **Validates: Requirements 5.5**
        """
        result = _sanitize_calendar_name(name)
        assert _SAFE_PATTERN.fullmatch(result) or result == "calendar", (
            f"Result {result!r} does not match safe pattern (input: {name!r})"
        )

    @given(name=_arbitrary_str_st)
    @settings(max_examples=100)
    def test_no_whitespace_in_result(self, name: str) -> None:
        """Result contains no whitespace characters.

        **Validates: Requirements 5.5**
        """
        result = _sanitize_calendar_name(name)
        assert not any(c.isspace() for c in result), (
            f"Result {result!r} contains whitespace (input: {name!r})"
        )

    @given(name=_mixed_str_st)
    @settings(max_examples=100)
    def test_empty_sanitization_falls_back_to_calendar(self, name: str) -> None:
        """When all characters are stripped, result is 'calendar'.

        **Validates: Requirements 5.5**
        """
        result = _sanitize_calendar_name(name)
        # If the input has no safe characters and no spaces, result should be "calendar"
        safe_chars = re.sub(r"[^A-Za-z0-9_\-]", "", name.replace(" ", "_"))
        if not safe_chars:
            assert result == "calendar"
        else:
            assert len(result) > 0

    @given(
        name=st.text(
            min_size=1,
            max_size=30,
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=" _-"),
        ).filter(lambda s: s.strip() != "")
    )
    @settings(max_examples=100)
    def test_spaces_become_underscores(self, name: str) -> None:
        """Spaces in input become underscores in output.

        **Validates: Requirements 5.5**
        """
        result = _sanitize_calendar_name(name)
        # After replacing spaces with _, all original safe chars should be preserved
        expected = name.replace(" ", "_")
        # Remove any chars that aren't in the safe set
        expected_clean = re.sub(r"[^A-Za-z0-9_\-]", "", expected)
        if expected_clean:
            assert result == expected_clean
        else:
            assert result == "calendar"
