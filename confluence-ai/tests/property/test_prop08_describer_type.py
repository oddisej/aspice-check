"""Property 8: Describer Type Validation.

**Validates: Requirements 9.6, 20.5**

For any value that is NOT a subclass of ``ImageDescriber``, calling
``register_describer("<name>", value)`` raises ``TypeError`` whose
message mentions ``ImageDescriber`` so developers know which interface
their class must implement.
"""

from __future__ import annotations

from hypothesis import given

from confluence_ai.providers import register_describer
from tests.conftest import invalid_class_type_st, valid_provider_name_st

# ``register_describer`` intentionally accepts any ``str`` as a
# fully-qualified class path for lazy loading. Restrict the invalid-value
# strategy to values that are neither strings nor ``ImageDescriber`` subclasses.
_non_string_invalid_st = invalid_class_type_st.filter(
    lambda v: not isinstance(v, str)
)


@given(provider_name=valid_provider_name_st, value=_non_string_invalid_st)
def test_register_describer_rejects_non_image_describer(
    provider_name: str, value: object
) -> None:
    """Non-class and non-``ImageDescriber`` values raise ``TypeError``.

    The ``TypeError`` message must name ``ImageDescriber`` so the caller
    knows which base class is required.
    """
    try:
        register_describer(provider_name, value)  # type: ignore[arg-type]
    except TypeError as exc:
        assert "ImageDescriber" in str(exc)
        return
    raise AssertionError(
        f"Expected TypeError for value={value!r}, but register_describer "
        "succeeded"
    )


def test_register_describer_rejects_unrelated_class() -> None:
    """A class that does not subclass ``ImageDescriber`` is rejected."""

    class NotADescriber:
        pass

    try:
        register_describer("bogus", NotADescriber)  # type: ignore[arg-type]
    except TypeError as exc:
        assert "ImageDescriber" in str(exc)
    else:
        raise AssertionError(
            "Expected TypeError for unrelated class, but "
            "register_describer succeeded"
        )
