"""Pluggable output renderer registry for exporting Confluence pages.

Defines the :class:`OutputRenderer` abstract base class that all output
format renderers must implement, together with a module-level registry
(``_RENDERERS``) and helper functions :func:`register_renderer` and
:func:`get_renderer`.

Built-in renderers (Markdown, JSON) register themselves at import time.
Custom renderers can be plugged in by calling :func:`register_renderer`.

Requirements: 8.1, 8.3, 8.4, 8.5
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from confluence_ai.models import ContentNode, PageMetadata

logger = logging.getLogger(__name__)


class OutputRenderer(ABC):
    """Abstract base class for output format renderers.

    Subclasses must implement :meth:`render`, which converts an IR node
    tree plus page metadata (and optional image descriptions) into a
    serialised string representation of the target format.
    """

    @abstractmethod
    def render(
        self,
        nodes: list[ContentNode],
        metadata: PageMetadata,
        descriptions: dict[str, str] | None = None,
    ) -> str:
        """Render the IR node tree to a string in the target format.

        Parameters
        ----------
        nodes:
            Ordered list of content nodes from the parser.
        metadata:
            Page metadata (source URL, title, labels, etc.).
        descriptions:
            Optional mapping of image local paths to AI-generated
            description text.

        Returns
        -------
        str
            The rendered output as a single string.
        """


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_RENDERERS: dict[str, type[OutputRenderer]] = {}
"""Module-level registry mapping format name -> renderer class."""


def register_renderer(
    format_name: str, renderer_class: type[OutputRenderer]
) -> None:
    """Register a renderer class for a given output format name.

    Parameters
    ----------
    format_name:
        The name under which the renderer will be looked up (e.g.,
        ``"markdown"``, ``"json"``).
    renderer_class:
        A class object that is a subclass of :class:`OutputRenderer`.

    Raises
    ------
    TypeError
        If ``renderer_class`` is not a subclass of :class:`OutputRenderer`.
    """
    if not (
        isinstance(renderer_class, type)
        and issubclass(renderer_class, OutputRenderer)
    ):
        raise TypeError(
            f"renderer_class must be a subclass of OutputRenderer, "
            f"got {renderer_class!r}"
        )
    if format_name in _RENDERERS:
        logger.warning(
            "Overwriting existing renderer for format %r", format_name
        )
    _RENDERERS[format_name] = renderer_class


def get_renderer(format_name: str) -> type[OutputRenderer]:
    """Look up a registered renderer class by format name.

    Parameters
    ----------
    format_name:
        The format name previously registered via :func:`register_renderer`.

    Returns
    -------
    type[OutputRenderer]
        The renderer class for ``format_name``.

    Raises
    ------
    ValueError
        If no renderer is registered for ``format_name``. The message
        lists all currently registered format names.
    """
    if format_name not in _RENDERERS:
        raise ValueError(
            f"Unknown output format '{format_name}'. "
            f"Registered formats: {sorted(_RENDERERS)}"
        )
    return _RENDERERS[format_name]
