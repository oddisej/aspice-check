"""Property 18: Unknown Describer Provider Error Message.

**Validates: Requirements 20.3**

For any provider name that is not currently registered, calling
``create_describer`` with that provider in the config raises
``ImageDescriptionError`` whose message lists every registered built-in
provider name (``"anthropic"``, ``"openai"``, ``"bedrock"``) so the
developer can discover valid options.
"""

from __future__ import annotations

from hypothesis import assume, given

from confluence_ai.exceptions import ImageDescriptionError
from confluence_ai.models import ImageDescriberConfig
from confluence_ai.providers import _PROVIDERS, create_describer
from tests.conftest import valid_provider_name_st

_BUILTIN_PROVIDERS = ("anthropic", "openai", "bedrock")


def test_builtin_providers_registered() -> None:
    """Sanity check — all three built-in providers are present."""
    for name in _BUILTIN_PROVIDERS:
        assert name in _PROVIDERS


@given(provider_name=valid_provider_name_st)
def test_unknown_provider_error_lists_builtins(provider_name: str) -> None:
    """``create_describer`` raises ``ImageDescriptionError`` listing builtins.

    The message must name every built-in provider so the caller knows
    which provider identifiers are valid out of the box.
    """
    assume(provider_name not in _PROVIDERS)

    config = ImageDescriberConfig(provider=provider_name, model="m")
    try:
        create_describer(config)
    except ImageDescriptionError as exc:
        message = str(exc)
        for builtin in _BUILTIN_PROVIDERS:
            assert builtin in message, (
                f"Error message {message!r} is missing built-in provider "
                f"{builtin!r}"
            )
    else:
        raise AssertionError(
            f"Expected ImageDescriptionError for unknown provider "
            f"{provider_name!r}, but create_describer succeeded"
        )
