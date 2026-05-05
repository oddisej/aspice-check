"""Property 10: Evaluator Type Validation.

**Validates: Requirements 13.6, 20.4**

For any value that is NOT a subclass of
:class:`~aspice_eval.evaluator.GapAnalysisEvaluator`, calling
``register_evaluator("<name>", value)`` raises :class:`TypeError` whose
message mentions ``GapAnalysisEvaluator`` so developers know which
interface their class must implement.
"""

from __future__ import annotations

import string

from hypothesis import given, strategies as st

from aspice_eval.providers import register_evaluator

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_IDENTIFIER_ALPHABET = string.ascii_letters + string.digits + "_-"

_valid_provider_name_st = st.text(
    alphabet=_IDENTIFIER_ALPHABET,
    min_size=1,
    max_size=32,
).filter(lambda s: s.strip() != "")


# ``register_evaluator`` intentionally accepts any ``str`` as a
# fully-qualified class path for lazy loading. Restrict the invalid-value
# strategy to values that are neither strings nor ``GapAnalysisEvaluator``
# subclasses.
_invalid_non_string_st: st.SearchStrategy[object] = st.one_of(
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.none(),
    st.dictionaries(st.text(max_size=3), st.integers(), max_size=3),
    st.lists(st.integers(), max_size=3),
    st.tuples(st.integers(), st.integers()),
    st.booleans(),
)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(provider_name=_valid_provider_name_st, value=_invalid_non_string_st)
def test_register_evaluator_rejects_non_gap_analysis_evaluator(
    provider_name: str, value: object
) -> None:
    """Non-class, non-string, non-``GapAnalysisEvaluator`` values raise ``TypeError``.

    The ``TypeError`` message must name ``GapAnalysisEvaluator`` so the
    caller knows which base class is required.
    """
    try:
        register_evaluator(provider_name, value)  # type: ignore[arg-type]
    except TypeError as exc:
        assert "GapAnalysisEvaluator" in str(exc)
        return
    raise AssertionError(
        f"Expected TypeError for value={value!r}, but register_evaluator "
        "succeeded"
    )


def test_register_evaluator_rejects_unrelated_class() -> None:
    """A class that does not subclass ``GapAnalysisEvaluator`` is rejected."""

    class NotAnEvaluator:
        pass

    try:
        register_evaluator("bogus", NotAnEvaluator)  # type: ignore[arg-type]
    except TypeError as exc:
        assert "GapAnalysisEvaluator" in str(exc)
    else:
        raise AssertionError(
            "Expected TypeError for unrelated class, but "
            "register_evaluator succeeded"
        )


def test_register_evaluator_rejects_builtin_types() -> None:
    """Common built-in class objects (``str``, ``int``, etc.) are rejected."""
    for builtin_cls in (str, int, list, dict, tuple, object):
        try:
            register_evaluator("bogus", builtin_cls)  # type: ignore[arg-type]
        except TypeError as exc:
            assert "GapAnalysisEvaluator" in str(exc)
        else:
            raise AssertionError(
                f"Expected TypeError for built-in class {builtin_cls!r}, "
                "but register_evaluator succeeded"
            )
