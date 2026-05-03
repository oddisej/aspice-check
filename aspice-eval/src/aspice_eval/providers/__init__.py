"""AI model provider package for the ASPICE evaluation tool.

Provides a factory function to create the appropriate evaluator
based on the configured provider name. Provider dependencies are
optional — only the chosen provider's package needs to be installed.

Requirements: 4.1, 4.5, 9.4
"""

from __future__ import annotations

import importlib

from aspice_eval.exceptions import InvalidConfigError
from aspice_eval.models import ModelConfig

# Fully-qualified class paths for each supported provider.
_PROVIDERS: dict[str, str] = {
    "bedrock": "aspice_eval.providers.bedrock.BedrockEvaluator",
    "openai": "aspice_eval.providers.openai_provider.OpenAIEvaluator",
    "anthropic": "aspice_eval.providers.anthropic_provider.AnthropicEvaluator",
    "mock": "aspice_eval.evaluator.MockEvaluator",
}


def create_evaluator(config: ModelConfig):
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
        If ``config.provider`` is not one of the supported provider
        names ("bedrock", "openai", "anthropic", "mock").
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
