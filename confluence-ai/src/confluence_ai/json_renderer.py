"""Built-in JSON output renderer for the Confluence exporter.

Serialises the IR node tree (plus page metadata and optional image
descriptions) as a structured JSON document. This enables programmatic
consumers to work with Confluence page content without having to parse
Markdown.

Registers itself as the ``"json"`` renderer at import time.

Requirements: 8.2
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from confluence_ai.models import ContentNode, PageMetadata
from confluence_ai.output_renderer import OutputRenderer, register_renderer


class JSONRenderer(OutputRenderer):
    """Renders ContentNode IR as a structured JSON document.

    Output shape::

        {
          "metadata": { ... PageMetadata fields ... },
          "nodes": [ ... list of serialised ContentNode dataclasses ... ],
          "descriptions": { "<local_path>": "<description text>", ... }
        }

    The JSON is pretty-printed with ``indent=2`` for readability.
    """

    def render(
        self,
        nodes: list[ContentNode],
        metadata: PageMetadata,
        descriptions: dict[str, str] | None = None,
    ) -> str:
        """Serialise nodes + metadata + descriptions as JSON.

        Parameters
        ----------
        nodes:
            Ordered list of content nodes from the parser.
        metadata:
            Page metadata block.
        descriptions:
            Optional map of image local paths to AI-generated description
            text.

        Returns
        -------
        str
            The JSON-serialised document.
        """
        payload: dict[str, Any] = {
            "metadata": asdict(metadata),
            "nodes": [asdict(node) for node in nodes],
            "descriptions": dict(descriptions) if descriptions else {},
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

register_renderer("json", JSONRenderer)
