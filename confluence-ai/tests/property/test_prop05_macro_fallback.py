"""Property 5: Unknown macros render as plain text with identifying comment.

*For any* ``MacroNode`` with a non-empty name and body text, the rendered
Markdown SHALL contain the body text as plain text and an HTML comment
containing the macro name.

**Validates: Requirements 3.4**

Feature: confluence-ai, Property 5: Unknown macros render as plain text with identifying comment
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.models import MacroNode, PageMetadata
from confluence_ai.renderer import MarkdownRenderer

# Strategy for macro names: alphanumeric with hyphens
_macro_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

# Strategy for macro body text: printable, non-empty
_macro_body_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z"),
        blacklist_characters="\n\r",
    ),
    min_size=1,
    max_size=200,
).filter(lambda s: s.strip())

_DUMMY_METADATA = PageMetadata(
    source_url="https://test.atlassian.net/wiki/spaces/X/pages/1",
    page_id="1",
    page_title="Test",
    export_timestamp="2024-01-01T00:00:00Z",
    exporter_version="0.1.0",
)


class TestProperty05MacroFallback:
    """Property 5: Unknown macros render with body text and HTML comment."""

    @given(
        name=_macro_name_strategy,
        body=_macro_body_strategy,
    )
    @settings(max_examples=100)
    def test_macro_contains_body_and_comment(
        self,
        name: str,
        body: str,
    ) -> None:
        """Rendered macro output contains body text and HTML comment with name.

        **Validates: Requirements 3.4**
        """
        node = MacroNode(name=name, parameters={}, body=body)
        renderer = MarkdownRenderer()
        full_md = renderer.render([node], _DUMMY_METADATA)

        # Body text must appear in the output
        assert body in full_md, (
            f"Macro body {body!r} not found in rendered output. "
            f"Output was: {full_md!r}"
        )

        # HTML comment with macro name must appear
        expected_comment = f"<!-- confluence macro: {name} -->"
        assert expected_comment in full_md, (
            f"Expected HTML comment {expected_comment!r} not found in output. "
            f"Output was: {full_md!r}"
        )
