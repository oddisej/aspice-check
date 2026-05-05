"""Property 9: Evaluator Registration Round-Trip.

**Validates: Requirements 13.2, 13.4**

For any valid provider name ``N`` and any class ``C`` that subclasses
:class:`~aspice_eval.evaluator.GapAnalysisEvaluator`, registering ``C``
under ``N`` via :func:`register_evaluator` and then calling
:func:`create_evaluator` with a ``ModelConfig`` whose ``provider`` is
``N`` yields an instance of ``C``.

The round-trip must hold when the class is registered as a class object
**or** as a fully qualified class path string.
"""

from __future__ import annotations

import string

from hypothesis import given, settings, strategies as st

from aspice_eval.evaluator import GapAnalysisEvaluator
from aspice_eval.models import ModelConfig
from aspice_eval.providers import (
    _PROVIDERS,
    create_evaluator,
    register_evaluator,
)

# ---------------------------------------------------------------------------
# Module-level stub evaluators.
# Defining them at module level guarantees that ``cls.__module__`` and
# ``cls.__qualname__`` resolve to importable paths, which is required for
# the string-path registration round-trip.
# ---------------------------------------------------------------------------


class _RoundtripEvaluatorA(GapAnalysisEvaluator):
    """Stub evaluator used to exercise the registration round-trip."""

    def _call_model(self, prompt: str) -> str:  # pragma: no cover - stub
        return "[]"


class _RoundtripEvaluatorB(GapAnalysisEvaluator):
    """Second stub evaluator — ensures the property holds across classes."""

    def _call_model(self, prompt: str) -> str:  # pragma: no cover - stub
        return "[]"


class _RoundtripEvaluatorC(GapAnalysisEvaluator):
    """Third stub evaluator for additional variety."""

    def _call_model(self, prompt: str) -> str:  # pragma: no cover - stub
        return "[]"


_SAMPLE_CLASSES = [
    _RoundtripEvaluatorA,
    _RoundtripEvaluatorB,
    _RoundtripEvaluatorC,
]

# Built-in providers we must not clobber during round-trip tests.
_BUILTIN_PROVIDERS = frozenset({"bedrock", "openai", "anthropic", "mock"})

_IDENTIFIER_ALPHABET = string.ascii_letters + string.digits + "_-"

_valid_provider_name_st = st.text(
    alphabet=_IDENTIFIER_ALPHABET,
    min_size=1,
    max_size=32,
).filter(lambda s: s.strip() != "")

_custom_provider_name_st = _valid_provider_name_st.filter(
    lambda n: n not in _BUILTIN_PROVIDERS
)


def _make_config(provider: str) -> ModelConfig:
    return ModelConfig(provider=provider, model_name="test-model")


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(
    provider_name=_custom_provider_name_st,
    evaluator_class=st.sampled_from(_SAMPLE_CLASSES),
)
@settings(deadline=None)
def test_register_class_roundtrip(
    provider_name: str,
    evaluator_class: type[GapAnalysisEvaluator],
) -> None:
    """``create_evaluator`` returns an instance of the registered class.

    Registration uses the class object directly.
    """
    previous = _PROVIDERS.get(provider_name)
    try:
        register_evaluator(provider_name, evaluator_class)
        instance = create_evaluator(_make_config(provider_name))
        assert isinstance(instance, evaluator_class)
    finally:
        if previous is None:
            _PROVIDERS.pop(provider_name, None)
        else:
            _PROVIDERS[provider_name] = previous


@given(
    provider_name=_custom_provider_name_st,
    evaluator_class=st.sampled_from(_SAMPLE_CLASSES),
)
@settings(deadline=None)
def test_register_string_path_roundtrip(
    provider_name: str,
    evaluator_class: type[GapAnalysisEvaluator],
) -> None:
    """``create_evaluator`` returns an instance when registered via path string.

    Uses the fully-qualified class path for registration, exercising the
    lazy-import branch of the factory.
    """
    qualified = f"{evaluator_class.__module__}.{evaluator_class.__qualname__}"
    previous = _PROVIDERS.get(provider_name)
    try:
        register_evaluator(provider_name, qualified)
        instance = create_evaluator(_make_config(provider_name))
        assert isinstance(instance, evaluator_class)
    finally:
        if previous is None:
            _PROVIDERS.pop(provider_name, None)
        else:
            _PROVIDERS[provider_name] = previous
