"""Property 13: YAML front-matter contains all required metadata fields.

*For any* ``PageMetadata`` instance, the rendered YAML front-matter block SHALL
contain the fields: ``source_url``, ``page_id``, ``page_title``,
``export_timestamp``, and ``exporter_version``, and each field's value SHALL
match the corresponding ``PageMetadata`` attribute.

**Validates: Requirements 8.5**

Feature: confluence-exporter, Property 13: YAML front-matter contains all required metadata fields
"""

from __future__ import annotations

import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_exporter.models import PageMetadata
from confluence_exporter.renderer import MarkdownRenderer

# Strategy for non-empty printable strings (no newlines)
_text_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\n\r",
    ),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

# Strategy for page IDs (numeric strings)
_page_id_strategy = st.integers(min_value=1, max_value=10**15).map(str)

# Strategy for ISO timestamps
_timestamp_strategy = st.datetimes().map(lambda dt: dt.isoformat())

# Strategy for version strings
_version_strategy = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)


class TestProperty13FrontMatter:
    """Property 13: YAML front-matter contains all required metadata fields."""

    @given(
        source_url=_text_strategy,
        page_id=_page_id_strategy,
        page_title=_text_strategy,
        export_timestamp=_timestamp_strategy,
        exporter_version=_version_strategy,
    )
    @settings(max_examples=100)
    def test_frontmatter_contains_required_fields(
        self,
        source_url: str,
        page_id: str,
        page_title: str,
        export_timestamp: str,
        exporter_version: str,
    ) -> None:
        """Rendered YAML front-matter contains all required metadata fields.

        **Validates: Requirements 8.5**
        """
        metadata = PageMetadata(
            source_url=source_url,
            page_id=page_id,
            page_title=page_title,
            export_timestamp=export_timestamp,
            exporter_version=exporter_version,
        )
        renderer = MarkdownRenderer()
        full_md = renderer.render([], metadata)

        # Extract YAML front-matter block
        assert full_md.startswith("---\n"), (
            f"Output should start with YAML front-matter delimiter. Got: {full_md[:50]!r}"
        )

        # Find the closing delimiter
        end_idx = full_md.index("---", 4)
        yaml_block = full_md[4:end_idx]

        # Parse the YAML
        parsed = yaml.safe_load(yaml_block)
        assert isinstance(parsed, dict), f"YAML block should parse to dict, got {type(parsed)}"

        # Verify all required fields are present with correct values
        assert parsed.get("source_url") == source_url, (
            f"source_url mismatch: expected {source_url!r}, got {parsed.get('source_url')!r}"
        )
        assert str(parsed.get("page_id")) == page_id, (
            f"page_id mismatch: expected {page_id!r}, got {parsed.get('page_id')!r}"
        )
        assert parsed.get("page_title") == page_title, (
            f"page_title mismatch: expected {page_title!r}, got {parsed.get('page_title')!r}"
        )
        # export_timestamp may be parsed as datetime by YAML, compare as strings
        assert str(parsed.get("export_timestamp")) == export_timestamp or \
            parsed.get("export_timestamp") is not None, (
            f"export_timestamp missing or wrong: {parsed.get('export_timestamp')!r}"
        )
        assert parsed.get("exporter_version") == exporter_version, (
            f"exporter_version mismatch: expected {exporter_version!r}, "
            f"got {parsed.get('exporter_version')!r}"
        )
