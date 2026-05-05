"""AI image description provider package.

Provides a factory function to create the appropriate image describer
based on the configured provider name. Provider dependencies (``anthropic``,
``openai``) are optional — only the chosen provider's package needs to be
installed.

Requirements: 6.1
"""

from __future__ import annotations

import importlib

from confluence_ai.exceptions import ImageDescriptionError
from confluence_ai.models import ImageDescriberConfig

# Fully-qualified class paths for each supported provider.
_PROVIDERS: dict[str, str] = {
    "anthropic": (
        "confluence_ai.providers.anthropic_describer"
        ".AnthropicImageDescriber"
    ),
    "openai": (
        "confluence_ai.providers.openai_describer"
        ".OpenAIImageDescriber"
    ),
    "bedrock": (
        "confluence_ai.providers.bedrock_describer"
        ".BedrockImageDescriber"
    ),
}


def create_describer(config: ImageDescriberConfig):
    """Create the appropriate image describer for the given configuration.

    Uses lazy imports so that only the chosen provider's dependencies
    need to be installed.

    Parameters
    ----------
    config:
        Image describer configuration specifying the provider name and
        model parameters.

    Returns
    -------
    ImageDescriber
        An image describer instance for the configured provider.

    Raises
    ------
    ImageDescriptionError
        If ``config.provider`` is not a supported provider name.
    """
    if config.provider not in _PROVIDERS:
        raise ImageDescriptionError(
            image_path="",
            provider=config.provider,
            message=(
                f"Unknown image description provider '{config.provider}'. "
                f"Valid providers: {', '.join(sorted(_PROVIDERS))}"
            ),
        )

    qualified_name = _PROVIDERS[config.provider]
    module_path, class_name = qualified_name.rsplit(".", 1)
    module = importlib.import_module(module_path)
    describer_class = getattr(module, class_name)
    return describer_class(config)
