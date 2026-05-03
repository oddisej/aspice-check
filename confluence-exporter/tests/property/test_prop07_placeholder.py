"""Property 7: Failed asset downloads produce placeholder text in rendered Markdown.

*For any* ``ImageNode`` or ``GliffyNode`` with ``local_path`` equal to ``None``
(indicating a failed download), the rendered Markdown SHALL contain a placeholder
indicating the missing image or diagram, and SHALL NOT contain a Markdown image
reference.

**Validates: Requirements 4.5, 5.5**

Feature: confluence-exporter, Property 7: Failed asset downloads produce placeholder text
"""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_exporter.models import GliffyNode, ImageNode, PageMetadata
from confluence_exporter.renderer import MarkdownRenderer

_filename_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_."),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

_url_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=":/.-_"),
    min_size=5,
    max_size=100,
).filter(lambda s: s.strip())

_diagram_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_ "),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

_DUMMY_METADATA = PageMetadata(
    source_url="https://test.atlassian.net/wiki/spaces/X/pages/1",
    page_id="1",
    page_title="Test",
    export_timestamp="2024-01-01T00:00:00Z",
    exporter_version="0.1.0",
)

# Regex for Markdown image reference
_IMAGE_REF_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


class TestProperty07Placeholder:
    """Property 7: Failed downloads produce placeholder text, no image reference."""

    @given(filename=_filename_strategy)
    @settings(max_examples=100)
    def test_image_node_no_local_path_has_placeholder(
        self,
        filename: str,
    ) -> None:
        """ImageNode with local_path=None renders placeholder, not image ref.

        **Validates: Requirements 4.5**
        """
        node = ImageNode(
            source_type="attachment",
            filename=filename,
            local_path=None,
        )
        renderer = MarkdownRenderer()
        full_md = renderer.render([node], _DUMMY_METADATA)

        # Should NOT contain a Markdown image reference
        assert not _IMAGE_REF_RE.search(full_md), (
            f"Found unexpected image reference in output for failed download. "
            f"Output: {full_md!r}"
        )

        # Should contain placeholder text indicating the missing image
        assert "not available" in full_md.lower() or "unavailable" in full_md.lower(), (
            f"No placeholder text found for failed image download. Output: {full_md!r}"
        )

    @given(name=_diagram_name_strategy)
    @settings(max_examples=100)
    def test_gliffy_node_no_local_path_has_placeholder(
        self,
        name: str,
    ) -> None:
        """GliffyNode with local_path=None renders placeholder, not image ref.

        **Validates: Requirements 5.5**
        """
        node = GliffyNode(
            name=name,
            local_path=None,
        )
        renderer = MarkdownRenderer()
        full_md = renderer.render([node], _DUMMY_METADATA)

        # Should NOT contain a Markdown image reference
        assert not _IMAGE_REF_RE.search(full_md), (
            f"Found unexpected image reference for failed Gliffy download. "
            f"Output: {full_md!r}"
        )

        # Should contain placeholder text
        assert "not available" in full_md.lower() or "unavailable" in full_md.lower(), (
            f"No placeholder text found for failed Gliffy download. Output: {full_md!r}"
        )
