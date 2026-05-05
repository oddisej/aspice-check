"""Property 13: Non-Existent Path Raises FileNotFoundError.

**Validates: Requirements 11.5, 11.6, 12.5**

For any file path that does not exist on the filesystem, calling
:func:`evaluate_sdp` or :func:`validate_kb` shall raise
``FileNotFoundError`` with a message identifying the missing path.
"""

from __future__ import annotations

import os
import string

from hypothesis import given, settings, strategies as st

from aspice_eval.convenience import evaluate_sdp, validate_kb
from aspice_eval.models import ModelConfig

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate path-like strings that definitely do not exist on the filesystem.
# We use a prefix that is extremely unlikely to exist and append random chars.
_PATH_CHARS = string.ascii_letters + string.digits + "_-."

_nonexistent_path_st = st.builds(
    lambda prefix, name, ext: os.path.join(
        "/tmp", f"__nonexistent_{prefix}__", f"{name}{ext}"
    ),
    prefix=st.text(alphabet=string.ascii_lowercase, min_size=4, max_size=12),
    name=st.text(alphabet=_PATH_CHARS, min_size=1, max_size=20).filter(
        lambda s: s.strip(".") != ""
    ),
    ext=st.sampled_from([".md", ".txt", ".pdf", ""]),
)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(path=_nonexistent_path_st)
@settings(deadline=None)
def test_evaluate_sdp_raises_file_not_found_for_nonexistent_sdp(
    path: str,
) -> None:
    """``evaluate_sdp`` raises FileNotFoundError for non-existent SDP path.

    The error message must contain the path that was not found.
    """
    config = ModelConfig(provider="mock", model_name="test")
    try:
        evaluate_sdp(path, config)
        # Should not reach here
        assert False, f"Expected FileNotFoundError for path: {path}"
    except FileNotFoundError as exc:
        assert path in str(exc), (
            f"Error message should contain the missing path '{path}', "
            f"got: {exc}"
        )


@given(path=_nonexistent_path_st)
@settings(deadline=None)
def test_evaluate_sdp_raises_file_not_found_for_nonexistent_kb(
    path: str,
) -> None:
    """``evaluate_sdp`` raises FileNotFoundError for non-existent KB path.

    When a valid SDP path is provided but the KB path does not exist,
    the error message must identify the missing KB path.
    """
    import tempfile

    # Create a temporary valid SDP file
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write("# Test SDP\n\nContent here.\n")
        sdp_file = f.name

    try:
        config = ModelConfig(provider="mock", model_name="test")
        try:
            evaluate_sdp(sdp_file, config, kb_path=path)
            assert False, f"Expected FileNotFoundError for kb_path: {path}"
        except FileNotFoundError as exc:
            assert path in str(exc), (
                f"Error message should contain the missing KB path '{path}', "
                f"got: {exc}"
            )
    finally:
        os.unlink(sdp_file)


@given(path=_nonexistent_path_st)
@settings(deadline=None)
def test_validate_kb_raises_file_not_found_for_nonexistent_path(
    path: str,
) -> None:
    """``validate_kb`` raises FileNotFoundError for non-existent KB path.

    The error message must contain the path that was not found.
    """
    try:
        validate_kb(path)
        assert False, f"Expected FileNotFoundError for path: {path}"
    except FileNotFoundError as exc:
        assert path in str(exc), (
            f"Error message should contain the missing path '{path}', "
            f"got: {exc}"
        )
