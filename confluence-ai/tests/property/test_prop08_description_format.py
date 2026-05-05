"""Property 8: Image descriptions are embedded directly after the image reference.

*For any* image node with a non-empty description string, the rendered Markdown
SHALL contain the description text directly following the image reference.

**Validates: Requirements 6.3**

Feature: confluence-ai, Property 8: Image descriptions are embedded after image references
"""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.models import GliffyNode, ImageNode, PageMetadata
from confluence_ai.renderer import MarkdownRenderer

_filename_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip()).map(lambda s: f"{s}.png")

_description_strategy = st.text(
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

# Regex for Markdown image reference
_IMAGE_REF_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


class TestProperty08DescriptionFormat:
    """Property 8: Image descriptions appear after image references."""

    @given(
        filename=_filename_strategy,
        description=_description_strategy,
    )
    @settings(max_examples=100)
    def test_image_description_appears_after_image(
        self,
        filename: str,
        description: str,
    ) -> None:
        """ImageNode with description renders description text after image ref.

        **Validates: Requirements 6.3**
        """
        local_path = f"images/{filename}"
        node = ImageNode(
            source_type="attachment",
            filename=filename,
            local_path=local_path,
        )
        renderer = MarkdownRenderer()
        descriptions = {local_path: description}
        full_md = renderer.render([node], _DUMMY_METADATA, descriptions)

        # Must contain the image reference
        assert _IMAGE_REF_RE.search(full_md), (
            f"No image reference found. Output: {full_md!r}"
        )

        # Must contain the description text
        assert description in full_md, (
            f"Description text {description!r} not found in output. "
            f"Output: {full_md!r}"
        )

    @given(
        name=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_ "),
            min_size=1,
            max_size=30,
        ).filter(lambda s: s.strip()),
        filename=_filename_strategy,
        description=_description_strategy,
    )
    @settings(max_examples=100)
    def test_gliffy_description_appears_after_image(
        self,
        name: str,
        filename: str,
        description: str,
    ) -> None:
        """GliffyNode with description renders description text after image ref.

        **Validates: Requirements 6.3**
        """
        local_path = f"images/{filename}"
        node = GliffyNode(
            name=name,
            local_path=local_path,
        )
        renderer = MarkdownRenderer()
        descriptions = {local_path: description}
        full_md = renderer.render([node], _DUMMY_METADATA, descriptions)

        assert _IMAGE_REF_RE.search(full_md), (
            f"No image reference found. Output: {full_md!r}"
        )
        assert description in full_md, (
            f"Description text {description!r} not found in output. "
            f"Output: {full_md!r}"
        )
