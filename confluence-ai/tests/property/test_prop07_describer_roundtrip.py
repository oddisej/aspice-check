"""Property 7: Describer Registration Round-Trip.

**Validates: Requirements 9.2, 9.4**

For any valid provider name ``N`` and any class ``C`` that subclasses
``ImageDescriber``, registering ``C`` under ``N`` via ``register_describer``
and then calling ``create_describer`` with a config whose ``provider`` is
``N`` yields an instance of ``C``.

The round-trip must hold when the class is registered as a class object
**or** as a fully qualified class path string.
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from confluence_ai.describer import ImageDescriber
from confluence_ai.models import ImageContext, ImageDescriberConfig
from confluence_ai.providers import (
    _PROVIDERS,
    create_describer,
    register_describer,
)
from tests.conftest import valid_provider_name_st

# ---------------------------------------------------------------------------
# Module-level stub describers.
# Defining them at module level guarantees that ``cls.__module__`` and
# ``cls.__qualname__`` resolve to importable paths, which is required for
# the string-path registration round-trip.
# ---------------------------------------------------------------------------


class _RoundtripDescriberA(ImageDescriber):
    """Stub describer used to exercise the registration round-trip."""

    def describe(self, image_path: str, context: ImageContext) -> str:
        return ""


class _RoundtripDescriberB(ImageDescriber):
    """Second stub describer — ensures the property holds across classes."""

    def describe(self, image_path: str, context: ImageContext) -> str:
        return ""


class _RoundtripDescriberC(ImageDescriber):
    """Third stub describer for additional variety."""

    def describe(self, image_path: str, context: ImageContext) -> str:
        return ""


_SAMPLE_CLASSES = [
    _RoundtripDescriberA,
    _RoundtripDescriberB,
    _RoundtripDescriberC,
]

# Exclude built-in provider names so we never clobber them.
_BUILTIN_PROVIDERS = frozenset({"anthropic", "openai", "bedrock"})

_custom_provider_name_st = valid_provider_name_st.filter(
    lambda n: n not in _BUILTIN_PROVIDERS
)


def _make_config(provider: str) -> ImageDescriberConfig:
    return ImageDescriberConfig(provider=provider, model="test-model")


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(
    provider_name=_custom_provider_name_st,
    describer_class=st.sampled_from(_SAMPLE_CLASSES),
)
@settings(deadline=None)
def test_register_class_roundtrip(
    provider_name: str, describer_class: type[ImageDescriber]
) -> None:
    """``create_describer`` returns an instance of the registered class.

    Registration uses the class object directly.
    """
    previous = _PROVIDERS.get(provider_name)
    try:
        register_describer(provider_name, describer_class)
        instance = create_describer(_make_config(provider_name))
        assert isinstance(instance, describer_class)
    finally:
        if previous is None:
            _PROVIDERS.pop(provider_name, None)
        else:
            _PROVIDERS[provider_name] = previous


@given(
    provider_name=_custom_provider_name_st,
    describer_class=st.sampled_from(_SAMPLE_CLASSES),
)
@settings(deadline=None)
def test_register_string_path_roundtrip(
    provider_name: str, describer_class: type[ImageDescriber]
) -> None:
    """``create_describer`` returns an instance when registered via path string.

    Uses the fully-qualified class path for registration, exercising the
    lazy-import branch of the factory.
    """
    qualified = f"{describer_class.__module__}.{describer_class.__qualname__}"
    previous = _PROVIDERS.get(provider_name)
    try:
        register_describer(provider_name, qualified)
        instance = create_describer(_make_config(provider_name))
        assert isinstance(instance, describer_class)
    finally:
        if previous is None:
            _PROVIDERS.pop(provider_name, None)
        else:
            _PROVIDERS[provider_name] = previous
