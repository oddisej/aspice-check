"""Property 16: Unsupported File Format Error Message.

**Validates: Requirements 20.1**

For any file path with an extension other than ``.md``, calling the SDP
ingester shall raise ``UnsupportedFormatError`` with a message containing
the actual file extension and the list of supported formats.
"""

from __future__ import annotations

import os
import string
import tempfile

from hypothesis import given, settings, strategies as st

from aspice_eval.exceptions import UnsupportedFormatError
from aspice_eval.sdp_ingester import SDPIngester

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate file extensions that are NOT .md (the only supported format).
_EXTENSION_CHARS = string.ascii_lowercase + string.digits

_unsupported_extension_st = st.text(
    alphabet=_EXTENSION_CHARS,
    min_size=1,
    max_size=8,
).map(lambda s: f".{s}").filter(lambda ext: ext.lower() != ".md")


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(ext=_unsupported_extension_st)
@settings(deadline=None)
def test_unsupported_format_error_contains_extension_and_supported_formats(
    ext: str,
) -> None:
    """``SDPIngester.ingest`` raises UnsupportedFormatError for non-.md files.

    The error message must contain:
    1. The actual file extension that was rejected.
    2. At least one supported format (i.e., ``.md``).
    3. A conversion suggestion.

    The error object must also carry structured attributes:
    - ``actual_extension``: the rejected extension
    - ``supported_formats``: list of supported format strings
    """
    # Create a temporary file with the unsupported extension
    with tempfile.NamedTemporaryFile(
        suffix=ext, mode="w", delete=False, prefix="test_sdp_"
    ) as f:
        f.write("Some content\n")
        tmp_path = f.name

    try:
        ingester = SDPIngester()
        try:
            ingester.ingest(tmp_path)
            assert False, (
                f"Expected UnsupportedFormatError for extension '{ext}'"
            )
        except UnsupportedFormatError as exc:
            msg = str(exc)
            # 1. Message contains the actual extension
            assert ext in msg, (
                f"Error message should contain the actual extension '{ext}', "
                f"got: {msg}"
            )
            # 2. Message contains at least one supported format
            assert ".md" in msg, (
                f"Error message should mention supported format '.md', "
                f"got: {msg}"
            )
            # 3. Message contains a conversion suggestion
            assert "convert" in msg.lower() or "Convert" in msg, (
                f"Error message should contain a conversion suggestion, "
                f"got: {msg}"
            )
            # 4. Structured attributes
            assert exc.actual_extension == ext.lower(), (
                f"actual_extension should be '{ext.lower()}', "
                f"got: {exc.actual_extension!r}"
            )
            assert ".md" in exc.supported_formats, (
                f"supported_formats should contain '.md', "
                f"got: {exc.supported_formats!r}"
            )
    finally:
        os.unlink(tmp_path)
