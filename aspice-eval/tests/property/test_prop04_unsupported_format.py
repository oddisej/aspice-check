"""Property 4: SDP ingester rejects unsupported formats with descriptive error.

Generate random non-Markdown file extensions; verify ingester raises
``UnsupportedFormatError`` with message identifying expected format.

**Validates: Requirements 3.3**
"""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from aspice_eval.exceptions import UnsupportedFormatError
from aspice_eval.sdp_ingester import SDPIngester

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Common non-Markdown extensions that should be rejected
_KNOWN_BAD_EXTENSIONS = [".docx", ".pdf", ".xlsx", ".doc", ".pptx", ".txt", ".csv", ".rtf", ".odt"]

# Strategy: pick from known bad extensions or generate random non-.md extensions
_bad_extension_st = st.one_of(
    st.sampled_from(_KNOWN_BAD_EXTENSIONS),
    st.from_regex(r"\.[a-z]{1,5}", fullmatch=True).filter(lambda e: e != ".md"),
)

# Random file content (doesn't matter — rejection is based on extension)
_content_st = st.text(min_size=0, max_size=200)


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------


class TestProperty04UnsupportedFormatRejection:
    """Property 4: SDP ingester rejects unsupported formats with descriptive error."""

    @given(extension=_bad_extension_st, content=_content_st)
    def test_non_markdown_extension_raises_unsupported_format_error(
        self,
        tmp_path_factory,
        extension: str,
        content: str,
    ) -> None:
        """Any file with a non-.md extension raises UnsupportedFormatError
        whose message identifies the expected Markdown format."""
        tmp_path = tmp_path_factory.mktemp("sdp")
        bad_file = tmp_path / f"document{extension}"
        bad_file.write_text(content, encoding="utf-8")

        ingester = SDPIngester()

        with pytest.raises(UnsupportedFormatError) as exc_info:
            ingester.ingest(str(bad_file))

        error = exc_info.value
        error_msg = str(error)

        # Message must mention the expected Markdown format
        assert "markdown" in error_msg.lower() or ".md" in error_msg.lower(), (
            f"Error message should identify expected Markdown format, got: {error_msg}"
        )

        # Message must mention the actual bad extension
        assert extension in error_msg, (
            f"Error message should mention the actual extension '{extension}', got: {error_msg}"
        )

        # Structured fields should be populated
        assert error.file_path != ""
        assert error.actual_extension == extension

    @given(extension=_bad_extension_st)
    def test_missing_non_markdown_file_raises_file_not_found(
        self,
        tmp_path_factory,
        extension: str,
    ) -> None:
        """A non-existent file raises FileNotFoundError regardless of extension."""
        tmp_path = tmp_path_factory.mktemp("sdp")
        missing_file = tmp_path / f"nonexistent{extension}"

        ingester = SDPIngester()

        with pytest.raises(FileNotFoundError):
            ingester.ingest(str(missing_file))
