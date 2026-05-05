"""Property 3: aspice-eval Public API Completeness.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4**

Every symbol required by Requirement 5 must be present in
``aspice_eval.__all__`` and must resolve as an attribute of the
top-level package without raising ``ImportError``.
"""

from __future__ import annotations

import importlib

import aspice_eval
from hypothesis import given, strategies as st

# ---------------------------------------------------------------------------
# Symbols mandated by Requirement 5.1 (core classes + factories + registry +
# convenience functions + models) and 5.2 (all exception classes).
# ---------------------------------------------------------------------------

_REQUIRED_SYMBOLS: list[str] = [
    # Core classes
    "KnowledgeBase",
    "GapAnalysisEvaluator",
    "ReportRenderer",
    # Factory & registry
    "create_evaluator",
    "register_evaluator",
    "register_renderer",
    "register_kb_loader",
    # Convenience functions
    "evaluate_sdp",
    "validate_kb",
    # Models
    "ModelConfig",
    "EvaluationConfig",
    "EvaluationResult",
    "CriteriaEntry",
    "CriteriaRating",
    "SDPDocument",
    "CapabilityLevelResult",
    "ValidationResult",
    # Exceptions (Req 5.2)
    "KBValidationError",
    "UnsupportedFormatError",
    "InvalidConfigError",
    "AIModelError",
    "AIResponseParseError",
]


# ---------------------------------------------------------------------------
# Example-based sanity checks
# ---------------------------------------------------------------------------


def test_all_required_symbols_in_dunder_all() -> None:
    """Every required symbol must be enumerated in ``__all__`` (Req 5.3)."""
    missing = [s for s in _REQUIRED_SYMBOLS if s not in aspice_eval.__all__]
    assert not missing, f"Symbols missing from __all__: {missing}"


def test_star_import_exposes_core_symbols() -> None:
    """``from aspice_eval import *`` must expose every ``__all__`` entry."""
    module = importlib.import_module("aspice_eval")
    namespace: dict[str, object] = {}
    for name in module.__all__:
        namespace[name] = getattr(module, name)

    # Explicit sanity checks
    assert "KnowledgeBase" in namespace
    assert "evaluate_sdp" in namespace
    assert "validate_kb" in namespace


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(name=st.sampled_from(_REQUIRED_SYMBOLS))
def test_every_required_symbol_resolves(name: str) -> None:
    """Every required symbol SHALL resolve on the top-level module (Req 5.4).

    **Validates: Requirements 5.1, 5.2**

    Each mandated class, function, model, and exception must be importable
    directly from ``aspice_eval`` without raising ``ImportError``.
    """
    assert hasattr(aspice_eval, name), (
        f"{name!r} is required by Requirement 5 but missing from "
        "aspice_eval"
    )
    symbol = getattr(aspice_eval, name)
    assert symbol is not None, f"{name!r} resolved to None"


@given(name=st.sampled_from(list(aspice_eval.__all__)))
def test_every_all_entry_resolves(name: str) -> None:
    """Every ``__all__`` entry SHALL be resolvable on the module (Req 5.4).

    **Validates: Requirements 5.3, 5.4**

    Complements the required-symbol property by ensuring the reverse
    direction: nothing declared in ``__all__`` is dangling.
    """
    assert hasattr(aspice_eval, name), (
        f"{name!r} is in __all__ but not resolvable on aspice_eval"
    )
