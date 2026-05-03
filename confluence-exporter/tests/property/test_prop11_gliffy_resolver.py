"""Property 11: Gliffy attachment resolver finds matching PNG preview.

*For any* ``GliffyNode`` with a diagram name N and an attachment list containing
an attachment whose filename contains N and ends with ``.png``, the resolver
SHALL return that attachment. If no matching attachment exists, the resolver
SHALL return ``None``.

**Validates: Requirements 5.1**

Feature: confluence-exporter, Property 11: Gliffy attachment resolver finds matching PNG preview
"""

from __future__ import annotations

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_exporter.downloader import AssetDownloader
from confluence_exporter.models import AttachmentData, GliffyNode

# Strategy for diagram names: alphanumeric with spaces
_diagram_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=" -_"),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip())

# Strategy for non-matching attachment filenames
_non_matching_filename = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip()).map(lambda s: f"unrelated_{s}.pdf")


def _make_downloader() -> AssetDownloader:
    """Create an AssetDownloader with a mocked client."""
    mock_client = MagicMock()
    return AssetDownloader(client=mock_client, output_dir="/tmp/test_output")


def _make_attachment(filename: str, media_type: str = "image/png") -> AttachmentData:
    """Create an AttachmentData with the given filename."""
    return AttachmentData(
        filename=filename,
        media_type=media_type,
        download_url=f"/download/{filename}",
    )


class TestProperty11GliffyResolver:
    """Property 11: Gliffy resolver finds matching PNG or returns None."""

    @given(name=_diagram_name_strategy)
    @settings(max_examples=100)
    def test_exact_match_found(self, name: str) -> None:
        """When attachment list has exact '{name}.png', resolver returns it.

        **Validates: Requirements 5.1**
        """
        node = GliffyNode(name=name)
        matching_att = _make_attachment(f"{name}.png")
        other_att = _make_attachment("other_file.pdf", media_type="application/pdf")

        downloader = _make_downloader()
        result = downloader._resolve_gliffy_attachment(node, [other_att, matching_att])

        assert result is not None, (
            f"Resolver should find exact match '{name}.png' but returned None"
        )
        assert result.filename == f"{name}.png"

    @given(
        name=_diagram_name_strategy,
        non_matching=st.lists(_non_matching_filename, min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_no_match_returns_none(
        self,
        name: str,
        non_matching: list[str],
    ) -> None:
        """When no attachment matches the diagram name, resolver returns None.

        **Validates: Requirements 5.1**
        """
        node = GliffyNode(name=name)
        attachments = [
            _make_attachment(fn, media_type="application/pdf")
            for fn in non_matching
        ]

        downloader = _make_downloader()
        result = downloader._resolve_gliffy_attachment(node, attachments)

        # Only assert None if none of the filenames could match
        # (partial match: filename contains name and ends with .png)
        has_potential_match = any(
            name.lower() in att.filename.lower() and att.filename.lower().endswith(".png")
            for att in attachments
        )
        has_gliffy_png = any(
            att.media_type == "image/png" and "gliffy" in att.filename.lower()
            for att in attachments
        )

        if not has_potential_match and not has_gliffy_png:
            assert result is None, (
                f"Resolver should return None when no matching attachment exists, "
                f"but returned {result}"
            )

    @given(name=_diagram_name_strategy)
    @settings(max_examples=100)
    def test_partial_match_found(self, name: str) -> None:
        """When attachment contains diagram name and ends with .png, resolver finds it.

        **Validates: Requirements 5.1**
        """
        node = GliffyNode(name=name)
        partial_filename = f"gliffy-123-{name}.png"
        matching_att = _make_attachment(partial_filename)

        downloader = _make_downloader()
        result = downloader._resolve_gliffy_attachment(node, [matching_att])

        assert result is not None, (
            f"Resolver should find partial match '{partial_filename}' but returned None"
        )
