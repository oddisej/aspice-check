"""ASPICE evaluation engine — knowledge base, evaluator, and reports."""

from __future__ import annotations

__version__ = "0.2.1"

# --- Core classes ---
from aspice_eval.knowledge_base import KnowledgeBase
from aspice_eval.evaluator import GapAnalysisEvaluator
from aspice_eval.report_renderer import ReportRenderer

# --- Factory & registry functions ---
from aspice_eval.providers import create_evaluator, register_evaluator
from aspice_eval.report_renderer import register_renderer
from aspice_eval.knowledge_base import register_kb_loader

# --- Convenience functions ---
from aspice_eval.convenience import evaluate_sdp, validate_kb

# --- Models ---
from aspice_eval.models import (
    ModelConfig,
    EvaluationConfig,
    EvaluationResult,
    CriteriaEntry,
    CriteriaRating,
    SDPDocument,
    CapabilityLevelResult,
    ValidationResult,
)

# --- Exceptions ---
from aspice_eval.exceptions import (
    KBValidationError,
    UnsupportedFormatError,
    InvalidConfigError,
    AIModelError,
    AIResponseParseError,
)

__all__ = [
    # Version
    "__version__",
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
    # Exceptions
    "KBValidationError",
    "UnsupportedFormatError",
    "InvalidConfigError",
    "AIModelError",
    "AIResponseParseError",
]
