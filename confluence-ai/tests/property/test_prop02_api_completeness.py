"""Property 2: confluence-ai Public API Completeness.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

Every symbol required by Requirement 4 must be present in
``confluence_ai.__all__`` and must resolve as an attribute of the
top-level package without raising ``ImportError``.
"""

from __future__ import annotations

import importlib

import confluence_ai
from hypothesis import given, strategies as st

# ---------------------------------------------------------------------------
# Symbols mandated by Requirement 4.1 (core classes + factories + convenience
# functions + models) and 4.2 (all exception classes).
# ---------------------------------------------------------------------------

_REQUIRED_SYMBOLS: list[str] = [
    # Core classes
    "ConfluenceClient",
    "StorageFormatParser",
    "MarkdownRenderer",
    "AssetDownloader",
    "ImageDescriber",
    "URLParser",
    "OutputRenderer",
    # Factory & registry
    "create_describer",
    "register_describer",
    "register_renderer",
    # Convenience functions
    "export_page",
    "publish_page",
    # Models
    "ImageDescriberConfig",
    "ImageContext",
    "PageMetadata",
    "ExportResult",
    # Exceptions (Req 4.2)
    "ExporterError",
    "InvalidURLError",
    "AuthenticationError",
    "ConfluenceConnectionError",
    "PageNotFoundError",
    "ParseError",
    "DownloadError",
    "ImageDescriptionError",
    "FileSystemError",
]


# ---------------------------------------------------------------------------
# Example-based sanity checks
# ---------------------------------------------------------------------------


def test_all_required_symbols_in_dunder_all() -> None:
    """Every required symbol must be enumerated in ``__all__`` (Req 4.3)."""
    missing = [s for s in _REQUIRED_SYMBOLS if s not in confluence_ai.__all__]
    assert not missing, f"Symbols missing from __all__: {missing}"


def test_star_import_exposes_core_symbols() -> None:
    """``from confluence_ai import *`` must expose every ``__all__`` entry."""
    module = importlib.import_module("confluence_ai")
    namespace: dict[str, object] = {}
    for name in module.__all__:
        namespace[name] = getattr(module, name)

    # A couple of explicit sanity checks so the test fails loudly if the
    # loop above silently yielded an empty namespace.
    assert "ConfluenceClient" in namespace
    assert "export_page" in namespace
    assert "publish_page" in namespace


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(name=st.sampled_from(_REQUIRED_SYMBOLS))
def test_every_required_symbol_resolves(name: str) -> None:
    """Every required symbol SHALL resolve on the top-level module (Req 4.4).

    Validates Requirements 4.1 and 4.2: each mandated class, function,
    model, and exception must be importable directly from
    ``confluence_ai`` without raising ``ImportError``.
    """
    assert hasattr(confluence_ai, name), (
        f"{name!r} is required by Requirement 4 but missing from "
        "confluence_ai"
    )
    symbol = getattr(confluence_ai, name)
    assert symbol is not None, f"{name!r} resolved to None"


@given(name=st.sampled_from(list(confluence_ai.__all__)))
def test_every_all_entry_resolves(name: str) -> None:
    """Every ``__all__`` entry SHALL be resolvable on the module (Req 4.4).

    Complements the required-symbol property by ensuring the reverse
    direction: nothing declared in ``__all__`` is dangling.
    """
    assert hasattr(confluence_ai, name), (
        f"{name!r} is in __all__ but not resolvable on confluence_ai"
    )
