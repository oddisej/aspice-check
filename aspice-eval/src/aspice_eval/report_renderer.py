"""Pluggable report renderer registry for ASPICE evaluation results.

Defines the :class:`ReportRenderer` abstract base class and a module-level
registry with :func:`register_renderer` and :func:`get_report_renderer`.

Requirements: 15.1, 15.2, 15.6
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from aspice_eval.models import (
    CapabilityLevelResult,
    EvaluationConfig,
    EvaluationResult,
    KBMetadata,
)

logger = logging.getLogger(__name__)


class ReportRenderer(ABC):
    """Abstract base class for evaluation report renderers.

    Subclass this to add custom report formats (JSON, SARIF, CSV, etc.).
    Register implementations via ``register_renderer()``.
    """

    @abstractmethod
    def render(
        self,
        evaluation: EvaluationResult,
        levels: dict[str, CapabilityLevelResult],
        config: EvaluationConfig,
        kb_metadata: KBMetadata,
    ) -> str:
        """Render evaluation results to the target format.

        Parameters
        ----------
        evaluation:
            Per-criteria evaluation results.
        levels:
            Per-group capability level results.
        config:
            The evaluation configuration used.
        kb_metadata:
            Knowledge base metadata.

        Returns
        -------
        str
            Rendered report content.
        """


_RENDERERS: dict[str, type[ReportRenderer]] = {}


def register_renderer(format_name: str, renderer_class: type[ReportRenderer]) -> None:
    """Register a custom report renderer.

    Parameters
    ----------
    format_name:
        Format identifier (e.g., "json", "sarif", "csv").
    renderer_class:
        A class that subclasses ReportRenderer.

    Raises
    ------
    TypeError
        If renderer_class is not a subclass of ReportRenderer.
    """
    if not (isinstance(renderer_class, type) and issubclass(renderer_class, ReportRenderer)):
        raise TypeError(
            f"renderer_class must be a subclass of ReportRenderer, "
            f"got {renderer_class!r}"
        )
    if format_name in _RENDERERS:
        logger.warning("Overwriting existing report renderer for format %r", format_name)
    _RENDERERS[format_name] = renderer_class


def get_report_renderer(format_name: str) -> type[ReportRenderer]:
    """Look up a registered report renderer by format name.

    Parameters
    ----------
    format_name:
        The format identifier to look up.

    Returns
    -------
    type[ReportRenderer]
        The registered renderer class.

    Raises
    ------
    UnsupportedFormatError
        If no renderer is registered for format_name.
    """
    from aspice_eval.exceptions import UnsupportedFormatError

    if format_name not in _RENDERERS:
        raise UnsupportedFormatError(
            f"Unknown report format '{format_name}'. "
            f"Registered formats: {sorted(_RENDERERS)}",
            supported_formats=sorted(_RENDERERS.keys()),
        )
    return _RENDERERS[format_name]
