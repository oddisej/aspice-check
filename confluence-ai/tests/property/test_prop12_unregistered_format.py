"""Property 12: Unregistered Format Error Lists Available Formats.

**Validates: Requirements 8.5**

For any ``format_name`` that is not currently in ``_RENDERERS``, calling
``get_renderer(format_name)`` raises an error whose message mentions at
least one of the currently registered format names (e.g., ``"markdown"``
or ``"json"``) so the developer can discover what's available.
"""

from __future__ import annotations

from hypothesis import assume, given

# Importing renderer modules triggers registration of the built-ins.
import confluence_ai.json_renderer  # noqa: F401  -- registers "json"
import confluence_ai.renderer  # noqa: F401  -- registers "markdown"
from confluence_ai.output_renderer import _RENDERERS, get_renderer
from tests.conftest import valid_provider_name_st


def test_builtin_renderers_registered() -> None:
    """Sanity check — the built-in renderers are available at import time."""
    assert "markdown" in _RENDERERS
    assert "json" in _RENDERERS


@given(format_name=valid_provider_name_st)
def test_unregistered_format_error_lists_registered_formats(
    format_name: str,
) -> None:
    """``get_renderer`` raises ``ValueError`` listing registered formats.

    For any ``format_name`` not currently registered, the error message
    must include at least one registered format name.
    """
    assume(format_name not in _RENDERERS)

    try:
        get_renderer(format_name)
    except ValueError as exc:
        message = str(exc)
        # The error must mention the bogus format name (for context) and
        # at least one real registered format (for discoverability).
        registered = set(_RENDERERS)
        assert any(
            name in message for name in registered
        ), (
            f"Error message {message!r} does not mention any registered "
            f"format from {sorted(registered)!r}"
        )
    else:
        raise AssertionError(
            f"Expected ValueError for unknown format {format_name!r}, "
            f"but get_renderer succeeded"
        )
