"""Property 6: Image and Gliffy nodes with local paths render as Markdown image references.

*For any* ``ImageNode`` or ``GliffyNode`` with a non-null ``local_path``, the
rendered Markdown SHALL contain a Markdown image reference ``![alt](images/filename)``
where the path is relative under ``images/``. For ``GliffyNode``, the alt-text
SHALL equal the diagram name.

**Validates: Requirements 4.3, 5.3, 5.4**

Feature: confluence-ai, Property 6: Image and Gliffy nodes with local paths render as Markdown image references with correct alt-text
"""

from __future__ import annotations

import os
import re

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.models import GliffyNode, ImageNode, PageMetadata
from confluence_ai.renderer import MarkdownRenderer

# Strategy for filenames: alphanumeric with extension
_filename_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip()).map(lambda s: f"{s}.png")

_alt_text_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\n\r[]!()",
    ),
    min_size=0,
    max_size=50,
)

_diagram_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters="-_ ",
    ),
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


class TestProperty06ImageRendering:
    """Property 6: Image/Gliffy nodes with local paths render as Markdown image refs."""

    @given(
        filename=_filename_strategy,
        alt_text=_alt_text_strategy,
    )
    @settings(max_examples=100)
    def test_image_node_renders_markdown_reference(
        self,
        filename: str,
        alt_text: str,
    ) -> None:
        """ImageNode with local_path renders as ![alt](images/filename).

        **Validates: Requirements 4.3**
        """
        local_path = f"images/{filename}"
        node = ImageNode(
            source_type="attachment",
            filename=filename,
            alt_text=alt_text,
            local_path=local_path,
        )
        renderer = MarkdownRenderer()
        full_md = renderer.render([node], _DUMMY_METADATA)

        matches = _IMAGE_REF_RE.findall(full_md)
        assert len(matches) >= 1, (
            f"No Markdown image reference found for ImageNode. Output: {full_md!r}"
        )

        # Verify the path is under images/
        _, ref_path = matches[0]
        assert ref_path.startswith("images/"), (
            f"Image path should start with 'images/', got {ref_path!r}"
        )

    @given(
        name=_diagram_name_strategy,
        filename=_filename_strategy,
    )
    @settings(max_examples=100)
    def test_gliffy_node_renders_with_diagram_name_as_alt(
        self,
        name: str,
        filename: str,
    ) -> None:
        """GliffyNode with local_path uses diagram name as alt-text.

        **Validates: Requirements 5.3, 5.4**
        """
        local_path = f"images/{filename}"
        node = GliffyNode(
            name=name,
            local_path=local_path,
        )
        renderer = MarkdownRenderer()
        full_md = renderer.render([node], _DUMMY_METADATA)

        matches = _IMAGE_REF_RE.findall(full_md)
        assert len(matches) >= 1, (
            f"No Markdown image reference found for GliffyNode. Output: {full_md!r}"
        )

        ref_alt, ref_path = matches[0]
        assert ref_alt == name, (
            f"GliffyNode alt-text should be diagram name {name!r}, got {ref_alt!r}"
        )
        assert ref_path.startswith("images/"), (
            f"Image path should start with 'images/', got {ref_path!r}"
        )
