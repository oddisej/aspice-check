"""Base image describer with prompt construction for AI-powered image descriptions.

Provides the ``ImageDescriber`` base class that defines the interface for
generating textual descriptions of images using multimodal AI models.
Concrete providers (Anthropic, OpenAI) override the ``describe`` method.

Requirements: 6.1, 6.2, 6.4, 6.5
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from confluence_exporter.exceptions import ImageDescriptionError
from confluence_exporter.models import ImageContext, ImageDescriberConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_GENERAL_PROMPT = """\
You are converting a Confluence page to Markdown. This image is embedded in the page.
Your task is to produce a comprehensive Markdown transcription of everything visible in this image,
so that someone reading only the Markdown (without seeing the image) has the same information.

Instructions:
- Transcribe ALL visible text labels, headings, and annotations exactly as they appear.
- If the image contains a table, reproduce it as a Markdown table.
- If the image contains a list or bullet points, reproduce them as Markdown lists.
- If the image contains a diagram, describe its structure, components, and relationships in detail.
- Use Markdown formatting (headings, bold, bullet points, tables) to structure the output.
- Do NOT summarize — be exhaustive. Every piece of visible information must be captured.
- Do NOT add commentary or interpretation — just transcribe what is visible.
- Output raw Markdown only, no code fences.
"""

_GLIFFY_PROMPT = """\
You are converting a Confluence page to Markdown. This is a Gliffy process diagram embedded in the page.
Your task is to produce a comprehensive Markdown transcription of everything visible in this diagram,
so that someone reading only the Markdown (without seeing the diagram) has the same information.

Instructions:
- Identify the diagram type (flowchart, swimlane, stage-gate, sequence diagram, etc.).
- Transcribe ALL visible text labels, box titles, annotations, and stage names exactly as they appear.
- If the diagram has stages or phases, list each one with its name, milestone, and all activities and bullet points visible within it.
- If the diagram has swimlanes or tracks, identify each lane/track and describe what happens in each.
- If there are decision points, describe each branch and where it leads.
- Describe the flow direction and all transitions and connections/arrows between elements.
- If the diagram contains a legend, reproduce it as a Markdown table.
- Use Markdown formatting: headings for major sections, tables for structured data, bullet points for activities.
- Do NOT summarize — be exhaustive. Every piece of visible information must be captured.
- Do NOT add commentary or interpretation — just transcribe what is visible.
- Output raw Markdown only, no code fences.
"""

_PLACEHOLDER_DESCRIPTION = "Image description unavailable"


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class ImageDescriber(ABC):
    """Base class for AI-powered image description generation.

    Subclasses must implement :meth:`describe` to call a specific
    multimodal AI provider.
    """

    def __init__(self, config: ImageDescriberConfig) -> None:
        self._config = config

    @abstractmethod
    def describe(self, image_path: str, context: ImageContext) -> str:
        """Generate a textual description of a single image.

        Parameters
        ----------
        image_path:
            Local filesystem path to the image file.
        context:
            Additional context for prompt construction (e.g. is_gliffy,
            alt_text, page_title).

        Returns
        -------
        str
            Textual description of the image content.

        Raises
        ------
        ImageDescriptionError
            If the AI provider fails after retries.
        """

    def describe_batch(
        self, images: list[tuple[str, ImageContext]]
    ) -> dict[str, str]:
        """Generate descriptions for multiple images.

        Iterates over each ``(image_path, context)`` pair, calling
        :meth:`describe`. On failure the image receives a placeholder
        description and processing continues.

        Parameters
        ----------
        images:
            List of ``(image_path, context)`` tuples.

        Returns
        -------
        dict[str, str]
            Mapping of image_path → description text. Failed descriptions
            map to the placeholder ``"Image description unavailable"``.
        """
        results: dict[str, str] = {}
        for image_path, context in images:
            try:
                results[image_path] = self.describe(image_path, context)
            except ImageDescriptionError as exc:
                logger.warning(
                    "Failed to generate description for %s — using placeholder: %s",
                    image_path,
                    exc,
                    exc_info=True,
                )
                results[image_path] = _PLACEHOLDER_DESCRIPTION
        return results

    @staticmethod
    def _build_prompt(context: ImageContext) -> str:
        """Build the description prompt based on image context.

        Returns the Gliffy-specific prompt when ``context.is_gliffy``
        is ``True``, otherwise the general image prompt.

        Parameters
        ----------
        context:
            Image context used to select the appropriate prompt.

        Returns
        -------
        str
            The prompt string to send alongside the image.
        """
        if context.is_gliffy:
            return _GLIFFY_PROMPT
        return _GENERAL_PROMPT
