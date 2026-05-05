"""Property 4: Rendered headings are compatible with SDPIngester header extraction.

*For any* ``HeadingNode`` with level L (1–6) and non-empty text T, the rendered
Markdown line SHALL match the regex ``^(#{1,6})[ \\t]+(\\S.*)$`` as used by the
``aspice-eval`` ``SDPIngester``, where the number of ``#`` characters equals L
and the captured text equals T.

**Validates: Requirements 3.3**

Feature: confluence-ai, Property 4: Rendered headings are compatible with SDPIngester header extraction
"""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.models import HeadingNode, PageMetadata
from confluence_ai.renderer import MarkdownRenderer

# Regex used by SDPIngester for header extraction
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(\S.*)$", re.MULTILINE)

# Strategy for heading text: printable, non-empty, starts with non-whitespace
_heading_text_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\n\r",
    ),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip() and not s[0].isspace())


class TestProperty04HeadingCompat:
    """Property 4: Rendered headings match SDPIngester header regex."""

    @given(
        level=st.integers(min_value=1, max_value=6),
        text=_heading_text_strategy,
    )
    @settings(max_examples=100)
    def test_heading_matches_sdp_ingester_regex(
        self,
        level: int,
        text: str,
    ) -> None:
        """Rendered heading line matches the SDPIngester header extraction regex.

        **Validates: Requirements 3.3**
        """
        node = HeadingNode(level=level, text=text)
        renderer = MarkdownRenderer()

        # Render just the heading node
        metadata = PageMetadata(
            source_url="https://test.atlassian.net/wiki/spaces/X/pages/1",
            page_id="1",
            page_title="Test",
            export_timestamp="2024-01-01T00:00:00Z",
            exporter_version="0.1.0",
        )
        full_md = renderer.render([node], metadata)

        # Find heading lines in the rendered output
        matches = _HEADING_RE.findall(full_md)
        assert len(matches) >= 1, (
            f"No heading match found in rendered output for level={level}, text={text!r}. "
            f"Output was: {full_md!r}"
        )

        # Verify the heading level and text
        hashes, captured_text = matches[0]
        assert len(hashes) == level, (
            f"Expected {level} '#' characters, got {len(hashes)}"
        )
        assert captured_text.strip() == text.strip(), (
            f"Expected text {text!r}, got {captured_text!r}"
        )
