"""Property 3: SDP ingester accepts any valid Markdown content.

Generate random Markdown strings; verify ingester accepts and returns
``SDPDocument`` with non-empty content.

**Validates: Requirements 3.1**
"""

from __future__ import annotations

from hypothesis import given, strategies as st

from aspice_eval.models import SDPDocument
from aspice_eval.sdp_ingester import SDPIngester

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate random Markdown content with optional headers and body text.
# We ensure at least some non-whitespace content so the file is meaningful.
_header_st = st.from_regex(r"#{1,6} [A-Za-z0-9 ]+", fullmatch=True)

_body_line_st = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "Z"), max_codepoint=0x7E),
    min_size=1,
    max_size=120,
)

_markdown_st = st.lists(
    st.one_of(_header_st, _body_line_st),
    min_size=1,
    max_size=20,
).map("\n".join)


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------


class TestProperty03MarkdownAcceptance:
    """Property 3: SDP ingester accepts any valid Markdown content."""

    @given(content=_markdown_st)
    def test_ingester_accepts_markdown_and_returns_sdp_document(
        self,
        tmp_path_factory,
        content: str,
    ) -> None:
        """Any Markdown content written to a .md file is accepted by the
        ingester, returning an SDPDocument with non-empty content."""
        tmp_path = tmp_path_factory.mktemp("sdp")
        md_file = tmp_path / "test_sdp.md"
        md_file.write_text(content, encoding="utf-8")

        ingester = SDPIngester()
        result = ingester.ingest(str(md_file))

        assert isinstance(result, SDPDocument)
        assert result.content == content
        assert result.file_path == str(md_file)
        assert len(result.content) > 0

    @given(content=_markdown_st)
    def test_section_headers_extracted_from_markdown(
        self,
        tmp_path_factory,
        content: str,
    ) -> None:
        """Section headers in the Markdown content are extracted into
        the section_headers field of the returned SDPDocument."""
        tmp_path = tmp_path_factory.mktemp("sdp")
        md_file = tmp_path / "test_sdp.md"
        md_file.write_text(content, encoding="utf-8")

        ingester = SDPIngester()
        result = ingester.ingest(str(md_file))

        # Every extracted header should appear as text in the original content
        for header in result.section_headers:
            assert header in content, (
                f"Extracted header {header!r} not found in content"
            )

        # Count lines starting with '#' followed by space — should match
        expected_count = sum(
            1
            for line in content.splitlines()
            if line.strip().startswith("#") and " " in line.strip()
        )
        assert len(result.section_headers) <= expected_count
