"""AI model provider package for the ASPICE evaluation tool.

Provides a factory function to create the appropriate evaluator based on
the configured provider name. Provider dependencies are optional — only
the chosen provider's package needs to be installed.

Also exposes :func:`register_evaluator` so users can plug in their own
:class:`~aspice_eval.evaluator.GapAnalysisEvaluator` implementations.

Requirements: 4.1, 4.5, 9.4, 13.1, 13.2, 13.5, 13.6, 16.1, 16.2, 20.2, 20.4
"""

from __future__ import annotations

import importlib
import logging

from aspice_eval.evaluator import GapAnalysisEvaluator
from aspice_eval.exceptions import InvalidConfigError
from aspice_eval.models import ModelConfig

logger = logging.getLogger(__name__)

# Fully-qualified class paths for each supported provider.
_PROVIDERS: dict[str, str] = {
    "bedrock": "aspice_eval.providers.bedrock.BedrockEvaluator",
    "openai": "aspice_eval.providers.openai_provider.OpenAIEvaluator",
    "anthropic": "aspice_eval.providers.anthropic_provider.AnthropicEvaluator",
    "mock": "aspice_eval.evaluator.MockEvaluator",
}

# Snapshot of the built-in providers, so ``register_evaluator`` can tell
# when it is about to overwrite one.
_BUILTIN_PROVIDERS: frozenset[str] = frozenset(_PROVIDERS)


def register_evaluator(
    provider_name: str,
    evaluator_class: type[GapAnalysisEvaluator] | str,
) -> None:
    """Register a custom evaluator provider.

    Parameters
    ----------
    provider_name:
        Provider identifier used when looking up the evaluator via
        :func:`create_evaluator` (e.g., ``"local-llama"``, ``"rule-based"``).
    evaluator_class:
        A class that subclasses
        :class:`~aspice_eval.evaluator.GapAnalysisEvaluator`, or a fully
        qualified class path string (``"my_pkg.my_mod.MyEvaluator"``) for
        lazy loading.

    Raises
    ------
    TypeError
        If ``evaluator_class`` is a class but not a subclass of
        ``GapAnalysisEvaluator``, or is neither a class nor a string.

    Notes
    -----
    Registering a provider name that matches a built-in provider
    (``"bedrock"``, ``"openai"``, ``"anthropic"``, ``"mock"``) overwrites
    the entry and logs a warning. Registering an already-registered
    custom provider likewise logs a warning.
    """
    if isinstance(evaluator_class, type):
        if not issubclass(evaluator_class, GapAnalysisEvaluator):
            raise TypeError(
                "evaluator_class must be a subclass of GapAnalysisEvaluator, "
                f"got {evaluator_class!r}"
            )
        qualified = (
            f"{evaluator_class.__module__}.{evaluator_class.__qualname__}"
        )
    elif isinstance(evaluator_class, str):
        qualified = evaluator_class
    else:
        raise TypeError(
            "evaluator_class must be a subclass of GapAnalysisEvaluator or a "
            "fully-qualified class path string, "
            f"got {evaluator_class!r}"
        )

    if provider_name in _BUILTIN_PROVIDERS:
        logger.warning(
            "Overwriting built-in evaluator provider %r", provider_name
        )
    elif provider_name in _PROVIDERS:
        logger.warning(
            "Overwriting existing evaluator provider %r", provider_name
        )

    _PROVIDERS[provider_name] = qualified


def create_evaluator(config: ModelConfig) -> GapAnalysisEvaluator:
    """Create the appropriate evaluator for the given model configuration.

    Uses lazy imports so that only the chosen provider's dependencies
    need to be installed.

    Parameters
    ----------
    config:
        Model configuration specifying the provider name and model
        parameters.

    Returns
    -------
    GapAnalysisEvaluator
        An evaluator instance for the configured provider.

    Raises
    ------
    InvalidConfigError
        If ``config.provider`` is not a registered provider name. The
        error message lists all registered provider names (built-in and
        custom).
    """
    if config.provider not in _PROVIDERS:
        raise InvalidConfigError(
            f"Unknown provider '{config.provider}'. "
            f"Valid providers: {', '.join(sorted(_PROVIDERS))}",
            parameter="provider",
            actual_value=config.provider,
            expected_values=sorted(_PROVIDERS.keys()),
        )

    qualified_name = _PROVIDERS[config.provider]
    module_path, class_name = qualified_name.rsplit(".", 1)
    module = importlib.import_module(module_path)
    evaluator_class = getattr(module, class_name)
    return evaluator_class(config)
