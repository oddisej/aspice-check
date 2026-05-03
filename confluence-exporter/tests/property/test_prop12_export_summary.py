"""Property 12: Export summary contains all required information.

*For any* ``ExportResult`` with a markdown path, image count, description
count, and warning list, the formatted summary string SHALL contain the
markdown file path, the image count, the description count, and every
warning message.

**Validates: Requirements 7.4**

Feature: confluence-exporter, Property 12: Export summary contains all required information
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_exporter.cli import format_summary
from confluence_exporter.models import ExportResult

# Strategy for generating plausible file paths (non-empty, printable)
_path_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=200,
).filter(lambda s: s.strip())

# Strategy for warning messages (non-empty, printable)
_warning_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
    min_size=1,
    max_size=300,
).filter(lambda s: s.strip())


class TestProperty12ExportSummary:
    """Property 12: Export summary contains all required fields."""

    @given(
        markdown_path=_path_strategy,
        images_downloaded=st.integers(min_value=0, max_value=10000),
        descriptions_generated=st.integers(min_value=0, max_value=10000),
        warnings=st.lists(_warning_strategy, min_size=0, max_size=10),
    )
    @settings(max_examples=100)
    def test_summary_contains_all_fields(
        self,
        markdown_path: str,
        images_downloaded: int,
        descriptions_generated: int,
        warnings: list[str],
    ) -> None:
        """Formatted summary contains markdown path, counts, and all warnings.

        **Validates: Requirements 7.4**
        """
        result = ExportResult(
            markdown_path=markdown_path,
            images_downloaded=images_downloaded,
            descriptions_generated=descriptions_generated,
            warnings=warnings,
        )

        summary = format_summary(result)

        # Summary must contain the markdown file path
        assert markdown_path in summary, (
            f"Summary missing markdown path {markdown_path!r}. "
            f"Summary was: {summary!r}"
        )

        # Summary must contain the image count
        assert str(images_downloaded) in summary, (
            f"Summary missing image count {images_downloaded}. "
            f"Summary was: {summary!r}"
        )

        # Summary must contain the description count
        assert str(descriptions_generated) in summary, (
            f"Summary missing description count {descriptions_generated}. "
            f"Summary was: {summary!r}"
        )

        # Summary must contain every warning message
        for warning in warnings:
            assert warning in summary, (
                f"Summary missing warning {warning!r}. "
                f"Summary was: {summary!r}"
            )
