"""Property 10: Filename sanitization preserves extensions and produces unique names.

*For any* list of filenames (possibly containing duplicates, spaces, and special
characters), the sanitizer SHALL produce filenames where: (a) each output preserves
the original file extension, (b) spaces are replaced with underscores, (c) special
characters are removed, and (d) all output filenames are unique (collisions resolved
by numeric suffix).

**Validates: Requirements 4.6, 8.1, 8.3**

Feature: confluence-ai, Property 10: Filename sanitization preserves extensions and produces unique names
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.downloader import AssetDownloader
from confluence_ai.models import AttachmentData

# Strategy for file extensions
_extension_strategy = st.sampled_from([".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf"])

# Strategy for filename stems with spaces and special chars
_stem_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters=" -_!@#$%",
    ),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip())

# Strategy for complete filenames
_filename_strategy = st.builds(
    lambda stem, ext: f"{stem}{ext}",
    stem=_stem_strategy,
    ext=_extension_strategy,
)


def _make_downloader() -> AssetDownloader:
    """Create an AssetDownloader with a mocked client for testing sanitization."""
    # We only need the _sanitize_filename method, which doesn't use the client
    # Create a minimal mock
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    return AssetDownloader(client=mock_client, output_dir="/tmp/test_output")


class TestProperty10FilenameSanitization:
    """Property 10: Filename sanitization preserves extensions and uniqueness."""

    @given(
        filenames=st.lists(
            _filename_strategy,
            min_size=1,
            max_size=20,
        ),
    )
    @settings(max_examples=100)
    def test_sanitized_filenames_are_unique(
        self,
        filenames: list[str],
    ) -> None:
        """All sanitized filenames in a batch are unique.

        **Validates: Requirements 8.3**
        """
        downloader = _make_downloader()
        sanitized = [downloader._sanitize_filename(f) for f in filenames]

        assert len(sanitized) == len(set(sanitized)), (
            f"Sanitized filenames are not unique: {sanitized}"
        )

    @given(filename=_filename_strategy)
    @settings(max_examples=100)
    def test_extension_preserved(
        self,
        filename: str,
    ) -> None:
        """Sanitized filename preserves the original file extension.

        **Validates: Requirements 4.6**
        """
        downloader = _make_downloader()
        sanitized = downloader._sanitize_filename(filename)

        # Extract original extension
        dot_idx = filename.rfind(".")
        if dot_idx > 0:
            original_ext = filename[dot_idx + 1:]
            # Clean the extension the same way the sanitizer does
            import re
            clean_ext = re.sub(r"[^a-zA-Z0-9]", "", original_ext)
            if clean_ext:
                assert sanitized.endswith(f".{clean_ext}"), (
                    f"Extension '.{clean_ext}' not preserved in {sanitized!r} "
                    f"(original: {filename!r})"
                )

    @given(
        prefix=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=10,
        ).filter(lambda s: s.strip()),
        suffix=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=10,
        ).filter(lambda s: s.strip()),
    )
    @settings(max_examples=100)
    def test_spaces_replaced_with_underscores(
        self,
        prefix: str,
        suffix: str,
    ) -> None:
        """Spaces in filenames are replaced with underscores.

        **Validates: Requirements 8.1**
        """
        # Build a stem that always contains a space
        stem = f"{prefix} {suffix}"
        filename = f"{stem}.png"
        downloader = _make_downloader()
        sanitized = downloader._sanitize_filename(filename)

        assert " " not in sanitized, (
            f"Sanitized filename still contains spaces: {sanitized!r} "
            f"(original: {filename!r})"
        )
