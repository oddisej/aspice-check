"""Feature: confluence-calendar-export, Property 2: Macro extraction returns all comma-separated IDs from every calendar macro."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.calendar_client import _extract_parent_ids_from_body


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Calendar IDs: alphanumeric with dashes (typical Confluence GUID-like IDs)
_calendar_id_st = st.text(
    min_size=1,
    max_size=30,
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
)

# Filler markup that does NOT contain `ac:name="calendar"` to avoid false matches
_safe_filler_st = st.sampled_from([
    "<p>Some text</p>",
    "<div class='content'>hello</div>",
    "<ac:structured-macro ac:name=\"toc\"><ac:parameter ac:name=\"style\">flat</ac:parameter></ac:structured-macro>",
    "",
    "<h1>Title</h1>",
    "<table><tr><td>data</td></tr></table>",
])


def _build_calendar_macro(ids: list[str]) -> str:
    """Build a calendar macro XHTML element with comma-separated IDs."""
    csv_ids = ",".join(ids)
    return (
        '<ac:structured-macro ac:name="calendar">'
        f'<ac:parameter ac:name="id">{csv_ids}</ac:parameter>'
        '</ac:structured-macro>'
    )


@st.composite
def st_calendar_macro_body(draw: st.DrawFn) -> tuple[str, list[str]]:
    """Generate a synthetic XHTML body with N calendar macros.

    Returns (body_string, expected_deduplicated_ids_in_order).
    """
    num_macros = draw(st.integers(min_value=0, max_value=5))

    body_parts: list[str] = []
    all_ids_in_order: list[str] = []

    for _ in range(num_macros):
        # Add some filler before the macro
        body_parts.append(draw(_safe_filler_st))

        # Generate 1-4 IDs per macro (comma-separated)
        num_ids = draw(st.integers(min_value=1, max_value=4))
        ids = [draw(_calendar_id_st) for _ in range(num_ids)]
        body_parts.append(_build_calendar_macro(ids))
        all_ids_in_order.extend(ids)

    # Add trailing filler
    body_parts.append(draw(_safe_filler_st))

    body = "\n".join(body_parts)

    # Compute expected: deduplicated, preserving order, skipping empty
    seen: set[str] = set()
    expected: list[str] = []
    for cal_id in all_ids_in_order:
        stripped = cal_id.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            expected.append(stripped)

    return body, expected


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty02MacroExtraction:
    """Property 2: Macro extraction returns all comma-separated IDs from every calendar macro."""

    @given(data=st_calendar_macro_body())
    @settings(max_examples=100)
    def test_extraction_returns_expected_ids(self, data: tuple[str, list[str]]) -> None:
        """Extracted IDs equal the in-order, deduplicated concatenation of all macro IDs.

        **Validates: Requirements 1.1, 1.4**
        """
        body, expected_ids = data
        result = _extract_parent_ids_from_body(body)
        assert result == expected_ids

    @given(data=st_calendar_macro_body())
    @settings(max_examples=100)
    def test_extraction_has_no_duplicates(self, data: tuple[str, list[str]]) -> None:
        """Returned list contains no duplicate IDs.

        **Validates: Requirements 1.1, 1.4**
        """
        body, _ = data
        result = _extract_parent_ids_from_body(body)
        assert len(result) == len(set(result))

    @given(data=st_calendar_macro_body())
    @settings(max_examples=100)
    def test_extraction_preserves_order(self, data: tuple[str, list[str]]) -> None:
        """IDs appear in the same order as they appear in the body (first occurrence).

        **Validates: Requirements 1.1, 1.4**
        """
        body, expected_ids = data
        result = _extract_parent_ids_from_body(body)
        # Each ID in result should appear in expected_ids at the same position
        assert result == expected_ids

    @given(filler=st.lists(_safe_filler_st, min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_no_macros_returns_empty(self, filler: list[str]) -> None:
        """A body with no calendar macros returns an empty list.

        **Validates: Requirements 1.1, 1.4**
        """
        body = "\n".join(filler)
        result = _extract_parent_ids_from_body(body)
        assert result == []
