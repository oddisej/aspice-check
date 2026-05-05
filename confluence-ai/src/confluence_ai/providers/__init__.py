"""AI image description provider package.

Provides a factory function to create the appropriate image describer
based on the configured provider name. Provider dependencies (``anthropic``,
``openai``) are optional — only the chosen provider's package needs to be
installed.

Also exposes ``register_describer`` so users can plug in their own
:class:`~confluence_ai.describer.ImageDescriber` implementations.

Requirements: 6.1, 9.1, 9.2, 9.5, 9.6, 10.1, 20.3, 20.5
"""

from __future__ import annotations

import importlib
import logging

from confluence_ai.describer import ImageDescriber
from confluence_ai.exceptions import ImageDescriptionError
from confluence_ai.models import ImageDescriberConfig

logger = logging.getLogger(__name__)

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

# Snapshot of the built-in providers, so ``register_describer`` can tell
# when it is about to overwrite one.
_BUILTIN_PROVIDERS: frozenset[str] = frozenset(_PROVIDERS)


def register_describer(
    provider_name: str,
    describer_class: type[ImageDescriber] | str,
) -> None:
    """Register a custom image description provider.

    Parameters
    ----------
    provider_name:
        Provider identifier used when looking up the describer via
        :func:`create_describer` (e.g., ``"local-llava"``, ``"azure-vision"``).
    describer_class:
        A class that subclasses
        :class:`~confluence_ai.describer.ImageDescriber`, or a fully
        qualified class path string (``"my_pkg.my_mod.MyDescriber"``)
        for lazy loading.

    Raises
    ------
    TypeError
        If ``describer_class`` is a class but not a subclass of
        ``ImageDescriber``, or is neither a class nor a string.

    Notes
    -----
    Registering a provider name that matches a built-in provider
    (``"anthropic"``, ``"openai"``, ``"bedrock"``) overwrites the
    entry and logs a warning.
    """
    if isinstance(describer_class, type):
        if not issubclass(describer_class, ImageDescriber):
            raise TypeError(
                "describer_class must be a subclass of ImageDescriber, "
                f"got {describer_class!r}"
            )
        qualified = (
            f"{describer_class.__module__}.{describer_class.__qualname__}"
        )
    elif isinstance(describer_class, str):
        qualified = describer_class
    else:
        raise TypeError(
            "describer_class must be a subclass of ImageDescriber or a "
            "fully-qualified class path string, "
            f"got {describer_class!r}"
        )

    if provider_name in _BUILTIN_PROVIDERS:
        logger.warning(
            "Overwriting built-in describer provider %r", provider_name
        )
    elif provider_name in _PROVIDERS:
        logger.warning(
            "Overwriting existing describer provider %r", provider_name
        )

    _PROVIDERS[provider_name] = qualified


def create_describer(config: ImageDescriberConfig) -> ImageDescriber:
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
        If ``config.provider`` is not a registered provider name. The
        error message lists all registered provider names (built-in and
        custom).
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
