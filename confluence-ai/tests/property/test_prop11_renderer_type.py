"""Property 11: OutputRenderer Type Validation.

**Validates: Requirements 8.4**

For any value that is NOT a subclass of ``OutputRenderer``, calling
``register_renderer("<name>", value)`` raises ``TypeError`` with a message
that mentions ``OutputRenderer``.
"""

from __future__ import annotations

from hypothesis import given

from confluence_ai.output_renderer import OutputRenderer, register_renderer
from tests.conftest import invalid_class_type_st, valid_provider_name_st


@given(format_name=valid_provider_name_st, value=invalid_class_type_st)
def test_register_renderer_rejects_non_output_renderer(
    format_name: str, value: object
) -> None:
    """``register_renderer`` raises ``TypeError`` for non-``OutputRenderer`` values.

    The ``TypeError`` message must name ``OutputRenderer`` so developers
    know what interface their class needs to implement.
    """
    try:
        register_renderer(format_name, value)  # type: ignore[arg-type]
    except TypeError as exc:
        assert "OutputRenderer" in str(exc)
        return
    raise AssertionError(
        f"Expected TypeError for value={value!r}, but register_renderer succeeded"
    )


def test_register_renderer_rejects_unrelated_class() -> None:
    """A class object that is not a subclass of ``OutputRenderer`` is rejected."""

    class NotARenderer:
        pass

    try:
        register_renderer("bogus", NotARenderer)  # type: ignore[arg-type]
    except TypeError as exc:
        assert "OutputRenderer" in str(exc)
    else:
        raise AssertionError(
            "Expected TypeError for unrelated class, but register_renderer succeeded"
        )


def test_register_renderer_accepts_subclass() -> None:
    """A valid ``OutputRenderer`` subclass registers without error (sanity check)."""

    class _TmpRenderer(OutputRenderer):
        def render(self, nodes, metadata, descriptions=None):  # type: ignore[override]
            return ""

    # Should not raise
    register_renderer("_tmp_prop11", _TmpRenderer)
