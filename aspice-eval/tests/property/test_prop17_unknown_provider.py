"""Property 17: Unknown Evaluator Provider Error Message.

**Validates: Requirements 20.2**

For any provider name that is not currently registered, calling
:func:`create_evaluator` with that provider in the ``ModelConfig`` raises
:class:`~aspice_eval.exceptions.InvalidConfigError` whose message lists
every registered built-in provider name (``"bedrock"``, ``"openai"``,
``"anthropic"``, ``"mock"``) so the developer can discover valid options.
"""

from __future__ import annotations

import string

from hypothesis import assume, given, strategies as st

from aspice_eval.exceptions import InvalidConfigError
from aspice_eval.models import ModelConfig
from aspice_eval.providers import _PROVIDERS, create_evaluator

_BUILTIN_PROVIDERS = ("bedrock", "openai", "anthropic", "mock")


_IDENTIFIER_ALPHABET = string.ascii_letters + string.digits + "_-"

_valid_provider_name_st = st.text(
    alphabet=_IDENTIFIER_ALPHABET,
    min_size=1,
    max_size=32,
).filter(lambda s: s.strip() != "")


def test_builtin_providers_registered() -> None:
    """Sanity check — all four built-in providers are present."""
    for name in _BUILTIN_PROVIDERS:
        assert name in _PROVIDERS


@given(provider_name=_valid_provider_name_st)
def test_unknown_provider_error_lists_builtins(provider_name: str) -> None:
    """``create_evaluator`` raises ``InvalidConfigError`` listing builtins.

    The message must name every built-in provider so the caller knows
    which provider identifiers are valid out of the box.
    """
    assume(provider_name not in _PROVIDERS)

    config = ModelConfig(provider=provider_name, model_name="test-model")
    try:
        create_evaluator(config)
    except InvalidConfigError as exc:
        message = str(exc)
        for builtin in _BUILTIN_PROVIDERS:
            assert builtin in message, (
                f"Error message {message!r} is missing built-in provider "
                f"{builtin!r}"
            )
    else:
        raise AssertionError(
            f"Expected InvalidConfigError for unknown provider "
            f"{provider_name!r}, but create_evaluator succeeded"
        )


def test_unknown_provider_error_includes_custom_providers() -> None:
    """Custom providers registered at runtime appear in the error message.

    Requirement 16.2 / 20.2: the valid-providers list in the error
    message must include any custom provider registered via
    :func:`~aspice_eval.providers.register_evaluator`.
    """
    from aspice_eval.evaluator import GapAnalysisEvaluator
    from aspice_eval.providers import register_evaluator

    class _MyCustomEvaluator(GapAnalysisEvaluator):
        def _call_model(self, prompt: str) -> str:  # pragma: no cover - stub
            return "[]"

    custom_name = "__prop17_custom_provider__"
    previous = _PROVIDERS.get(custom_name)
    try:
        register_evaluator(custom_name, _MyCustomEvaluator)

        config = ModelConfig(
            provider="__definitely_not_registered__",
            model_name="test-model",
        )
        try:
            create_evaluator(config)
        except InvalidConfigError as exc:
            assert custom_name in str(exc), (
                f"Error message {str(exc)!r} should list the custom "
                f"provider {custom_name!r}"
            )
        else:
            raise AssertionError(
                "Expected InvalidConfigError for unknown provider"
            )
    finally:
        if previous is None:
            _PROVIDERS.pop(custom_name, None)
        else:
            _PROVIDERS[custom_name] = previous
