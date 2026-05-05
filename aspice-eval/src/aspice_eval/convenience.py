"""High-level convenience functions for the ASPICE evaluation engine.

Provides :func:`evaluate_sdp` and :func:`validate_kb` — single-call
entry points that orchestrate the full evaluation and validation
pipelines without requiring users to wire together multiple classes.

Requirements: 11.1–11.6, 12.1–12.5, 22.6
"""

from __future__ import annotations

import pathlib
from typing import Any

from aspice_eval.knowledge_base import KnowledgeBase, get_kb_loader
from aspice_eval.level_calculator import CapabilityLevelCalculator
from aspice_eval.models import (
    EvaluationConfig,
    EvaluationResult,
    ModelConfig,
    ValidationResult,
)
from aspice_eval.providers import create_evaluator
from aspice_eval.sdp_ingester import SDPIngester


def _resolve_default_kb_path() -> str:
    """Resolve the bundled knowledge base path.

    Searches package-relative and repository-relative locations for the
    ``knowledge_base`` directory shipped with the package.

    Returns
    -------
    str
        Absolute path to the bundled knowledge base directory.

    Raises
    ------
    FileNotFoundError
        If the bundled knowledge base cannot be located.
    """
    pkg_root = pathlib.Path(__file__).resolve().parent
    candidates = [
        pkg_root / "knowledge_base",
        pkg_root.parent.parent / "knowledge_base",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(
        "Bundled knowledge base not found. Provide an explicit kb_path."
    )


def evaluate_sdp(
    sdp_path: str,
    model_config: ModelConfig,
    *,
    target_level: int = 3,
    process_groups: list[str] | None = None,
    kb_path: str | None = None,
    standard: str = "aspice",
) -> EvaluationResult:
    """Evaluate an SDP document against knowledge base criteria.

    Orchestrates the full evaluation pipeline: SDP ingestion → KB loading →
    criteria filtering → AI evaluation → capability level calculation.

    Parameters
    ----------
    sdp_path:
        Path to the SDP Markdown file.
    model_config:
        AI model configuration (provider, model name, temperature, etc.).
    target_level:
        Target ASPICE capability level (1–5). Defaults to 3 (Established).
    process_groups:
        Process groups to evaluate. Defaults to ``["SWE", "SYS", "MAN", "SUP"]``.
    kb_path:
        Path to the knowledge base directory. Defaults to the bundled KB.
    standard:
        Standard identifier (subdirectory name under kb_path).
        Defaults to ``"aspice"``.

    Returns
    -------
    EvaluationResult
        Contains per-criteria ratings, capability levels, and token usage.

    Raises
    ------
    FileNotFoundError
        If ``sdp_path`` or ``kb_path`` does not exist.
    UnsupportedFormatError
        If the SDP file is not Markdown format.
    InvalidConfigError
        If ``target_level`` is outside 1–5 or ``process_groups`` contains
        unknown codes.
    AIModelError
        If the AI model call fails after retries.

    Examples
    --------
    >>> from aspice_eval.convenience import evaluate_sdp
    >>> from aspice_eval.models import ModelConfig
    >>> result = evaluate_sdp(
    ...     "docs/sdp.md",
    ...     ModelConfig(provider="bedrock", model_name="us.anthropic.claude-sonnet-4-20250514-v1:0", region="us-east-1"),
    ...     target_level=3,
    ...     process_groups=["SWE", "SYS"],
    ... )
    >>> print(f"Gaps found: {len([r for r in result.ratings if r.gaps])}")
    """
    # Validate sdp_path exists
    sdp = pathlib.Path(sdp_path)
    if not sdp.exists():
        raise FileNotFoundError(f"SDP file does not exist: {sdp_path}")

    # Resolve kb_path
    resolved_kb_path = kb_path if kb_path is not None else _resolve_default_kb_path()
    if not pathlib.Path(resolved_kb_path).exists():
        raise FileNotFoundError(
            f"Knowledge base path does not exist: {resolved_kb_path}"
        )

    # Default process groups
    groups = process_groups if process_groups is not None else ["SWE", "SYS", "MAN", "SUP"]

    # Check for custom KB loader in the registry
    custom_loader_cls = get_kb_loader(standard)
    if custom_loader_cls is not None:
        kb = custom_loader_cls(resolved_kb_path)
    else:
        kb = KnowledgeBase(resolved_kb_path)

    kb.load(standard)
    criteria = kb.get_criteria(groups, target_level)

    # Ingest SDP
    ingester = SDPIngester()
    sdp_doc = ingester.ingest(sdp_path)

    # Build evaluation config
    config = EvaluationConfig(
        sdp_path=sdp_path,
        target_capability_level=target_level,
        process_groups=groups,
        kb_path=resolved_kb_path,
        standard=standard,
    )

    # Create evaluator and run evaluation
    evaluator = create_evaluator(model_config)
    evaluation = evaluator.evaluate(sdp_doc, criteria, config)

    # Calculate capability levels for metadata enrichment
    calculator = CapabilityLevelCalculator(target_level)
    levels = calculator.calculate(evaluation.ratings, groups)

    # Attach capability levels to evaluation metadata
    evaluation.sdp_metadata["capability_levels"] = {
        group: {
            "achieved_level": result.achieved_level,
            "target_level": result.target_level,
            "blocking_attributes": result.blocking_attributes,
        }
        for group, result in levels.items()
    }

    return evaluation


def validate_kb(
    kb_path: str,
    *,
    standard: str = "aspice",
) -> ValidationResult:
    """Validate a knowledge base directory for schema and completeness.

    Loads the specified standard from the knowledge base directory and
    runs schema validation and completeness checks against the bundled
    criteria JSON Schema.

    Parameters
    ----------
    kb_path:
        Path to the knowledge base root directory.
    standard:
        Standard identifier to validate. Defaults to ``"aspice"``.

    Returns
    -------
    ValidationResult
        Contains ``is_valid`` flag, ``schema_errors``, ``completeness_gaps``,
        and ``warnings``.

    Raises
    ------
    FileNotFoundError
        If ``kb_path`` does not exist.

    Examples
    --------
    >>> from aspice_eval.convenience import validate_kb
    >>> result = validate_kb("knowledge_base")
    >>> if not result.is_valid:
    ...     for error in result.schema_errors:
    ...         print(f"Schema error: {error}")
    """
    if not pathlib.Path(kb_path).exists():
        raise FileNotFoundError(
            f"Knowledge base path does not exist: {kb_path}"
        )

    kb = KnowledgeBase(kb_path)
    kb.load(standard)
    return kb.validate()
