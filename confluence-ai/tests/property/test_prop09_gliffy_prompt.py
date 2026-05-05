"""Property 9: Gliffy diagram prompts include process flow instructions.

*For any* ``ImageContext`` where ``is_gliffy`` is ``True``, the constructed
prompt string SHALL contain keywords related to process flow analysis:
"activities", "decision points", "swimlanes", and "transitions".

**Validates: Requirements 6.4**

Feature: confluence-ai, Property 9: Gliffy diagram prompts include process flow instructions
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.describer import ImageDescriber
from confluence_ai.models import ImageContext

# Required keywords that must appear in every Gliffy prompt
_REQUIRED_KEYWORDS = ["activities", "decision points", "swimlanes", "transitions"]


class TestProperty09GliffyPrompt:
    """Property 9: Gliffy prompts contain process flow keywords."""

    @given(
        alt_text=st.text(min_size=0, max_size=100),
        page_title=st.text(min_size=0, max_size=200),
        filename=st.text(min_size=0, max_size=100),
    )
    @settings(max_examples=100)
    def test_gliffy_prompt_contains_required_keywords(
        self,
        alt_text: str,
        page_title: str,
        filename: str,
    ) -> None:
        """Gliffy prompts always contain process flow keywords.

        **Validates: Requirements 6.4**
        """
        context = ImageContext(
            is_gliffy=True,
            alt_text=alt_text,
            page_title=page_title,
            filename=filename,
        )

        prompt = ImageDescriber._build_prompt(context)

        for keyword in _REQUIRED_KEYWORDS:
            assert keyword in prompt, (
                f"Gliffy prompt missing required keyword {keyword!r}. "
                f"Prompt was: {prompt!r}"
            )

    @given(
        alt_text=st.text(min_size=0, max_size=100),
        page_title=st.text(min_size=0, max_size=200),
        filename=st.text(min_size=0, max_size=100),
    )
    @settings(max_examples=100)
    def test_non_gliffy_prompt_is_general(
        self,
        alt_text: str,
        page_title: str,
        filename: str,
    ) -> None:
        """Non-Gliffy prompts use the general image prompt.

        **Validates: Requirements 6.2**
        """
        context = ImageContext(
            is_gliffy=False,
            alt_text=alt_text,
            page_title=page_title,
            filename=filename,
        )

        prompt = ImageDescriber._build_prompt(context)

        # General prompt should mention image description basics
        assert "image" in prompt.lower()
        assert "describe" in prompt.lower()
