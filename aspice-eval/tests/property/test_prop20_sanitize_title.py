"""Property test for title sanitization in the analyze pipeline.

**Validates: Requirements 1.3**

Property 1: Output directory path is correctly derived from page title.
For any page title string (including spaces, special characters, unicode,
empty strings), ``_sanitize_title()`` produces a string containing only
alphanumeric characters, underscores, and hyphens.
"""

from __future__ import annotations

import re

from hypothesis import given
from hypothesis import strategies as st

from aspice_eval.analyze import _sanitize_title

# Pattern matching only valid characters in sanitized output
_VALID_CHARS_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


class TestProperty20SanitizeTitle:
    """Feature: aspice-analyze-command, Property 1: title sanitization."""

    @given(title=st.text(min_size=0, max_size=200))
    def test_sanitized_contains_only_valid_chars(self, title: str) -> None:
        """Sanitized title contains only alphanumeric, underscores, hyphens."""
        result = _sanitize_title(title)
        assert _VALID_CHARS_RE.match(result), (
            f"Sanitized title {result!r} contains invalid characters"
        )

    @given(title=st.text(min_size=0, max_size=200))
    def test_sanitized_is_never_empty(self, title: str) -> None:
        """Sanitized title is never empty (falls back to 'untitled')."""
        result = _sanitize_title(title)
        assert len(result) > 0

    @given(title=st.from_regex(r"[a-zA-Z0-9]+", fullmatch=True))
    def test_ascii_alphanumeric_titles_preserved(self, title: str) -> None:
        """Purely ASCII alphanumeric titles are preserved as-is."""
        result = _sanitize_title(title)
        assert result == title

    @given(title=st.text(
        alphabet=st.characters(exclude_categories=("L", "N")),
        min_size=1,
        max_size=50,
    ))
    def test_all_special_chars_returns_untitled(self, title: str) -> None:
        """Titles with only special characters (no alphanumeric, no spaces,
        no hyphens, no underscores) return 'untitled'."""
        # Filter out titles that contain underscores or hyphens since those
        # are valid in the output
        if "_" in title or "-" in title:
            return
        result = _sanitize_title(title)
        # Result should be 'untitled' or contain only chars from spaces
        # that were converted to underscores
        if " " in title:
            # Spaces become underscores, which are valid
            assert _VALID_CHARS_RE.match(result)
        else:
            assert result == "untitled"

    def test_spaces_become_underscores(self) -> None:
        """Spaces in titles are replaced with underscores."""
        assert _sanitize_title("Hello World") == "Hello_World"

    def test_empty_string_returns_untitled(self) -> None:
        """Empty string returns 'untitled'."""
        assert _sanitize_title("") == "untitled"
