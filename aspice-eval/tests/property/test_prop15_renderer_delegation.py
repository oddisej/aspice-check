"""Property 15: Report Renderer Delegation.

*For any* format name and ReportRenderer subclass registered via
register_renderer(name, cls), calling ReportGenerator.generate(...,
output_format=name) shall delegate to that renderer's render() method.
For any unregistered format name, it shall raise UnsupportedFormatError
listing all registered formats.

**Validates: Requirements 15.3, 15.5**
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from aspice_eval.exceptions import UnsupportedFormatError
from aspice_eval.models import (
    CapabilityLevelResult,
    EvaluationConfig,
    EvaluationResult,
    KBMetadata,
)
from aspice_eval.report_generator import ReportGenerator
from aspice_eval.report_renderer import (
    ReportRenderer,
    _RENDERERS,
    register_renderer,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Format names: simple lowercase identifiers that won't collide with built-ins
_custom_format_st = st.text(
    alphabet=st.characters(whitelist_categories=("Ll",), whitelist_characters="_"),
    min_size=4,
    max_size=12,
).filter(lambda s: s not in _RENDERERS)

# Unregistered format names: guaranteed not in the registry
_unregistered_format_st = st.text(
    alphabet=st.characters(whitelist_categories=("Ll",), whitelist_characters="_"),
    min_size=4,
    max_size=12,
).filter(lambda s: s not in _RENDERERS and s not in ("markdown", "html"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_evaluation_data() -> tuple[
    EvaluationResult,
    dict[str, CapabilityLevelResult],
    EvaluationConfig,
    KBMetadata,
]:
    """Create minimal valid evaluation data for testing delegation."""
    config = EvaluationConfig(
        sdp_path="test.md",
        target_capability_level=3,
        process_groups=["SWE"],
    )
    evaluation = EvaluationResult(
        ratings=[],
        evaluation_timestamp="2025-01-15T00:00:00Z",
        config=config,
    )
    levels = {
        "SWE": CapabilityLevelResult(
            process_group="SWE",
            achieved_level=2,
            target_level=3,
        ),
    }
    kb_metadata = KBMetadata(
        standard_name="Test Standard",
        short_name="TEST",
        version="1.0",
        release_date="2025-01",
        source_references=[],
        license_note="Test",
        kb_version="1.0.0",
        last_updated="2025-01-15",
        process_groups=[],
        capability_levels=[],
        rating_scale=[],
    )
    return evaluation, levels, config, kb_metadata


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestProperty15RendererDelegation:
    """Property 15: Report Renderer Delegation."""

    @given(format_name=_custom_format_st)
    def test_generate_delegates_to_registered_renderer(
        self,
        format_name: str,
    ) -> None:
        """For any registered format name, ReportGenerator.generate()
        SHALL delegate to the registered renderer's render() method.

        **Validates: Requirements 15.3**
        """
        # Track whether render() was called
        render_called = False
        sentinel = f"RENDERED_BY_{format_name}"

        class CustomRenderer(ReportRenderer):
            def render(self, evaluation, levels, config, kb_metadata) -> str:
                nonlocal render_called
                render_called = True
                return sentinel

        # Register and test
        try:
            register_renderer(format_name, CustomRenderer)

            evaluation, levels, config, kb_metadata = _minimal_evaluation_data()
            generator = ReportGenerator()
            result = generator.generate(
                evaluation, levels, config, kb_metadata,
                output_format=format_name,
            )

            assert render_called, (
                f"Renderer for format '{format_name}' was not called"
            )
            assert result == sentinel, (
                f"Expected sentinel '{sentinel}', got '{result[:50]}...'"
            )
        finally:
            # Clean up registry to avoid polluting other tests
            _RENDERERS.pop(format_name, None)

    @given(format_name=_unregistered_format_st)
    def test_unregistered_format_raises_with_available_formats(
        self,
        format_name: str,
    ) -> None:
        """For any unregistered format name, ReportGenerator.generate()
        SHALL raise UnsupportedFormatError listing all registered formats.

        **Validates: Requirements 15.5**
        """
        evaluation, levels, config, kb_metadata = _minimal_evaluation_data()
        generator = ReportGenerator()

        try:
            generator.generate(
                evaluation, levels, config, kb_metadata,
                output_format=format_name,
            )
            assert False, (
                f"Expected UnsupportedFormatError for format '{format_name}'"
            )
        except UnsupportedFormatError as exc:
            # Verify the error lists registered formats
            error_msg = str(exc)
            assert "markdown" in error_msg, (
                f"Error message should list 'markdown' as a registered format. "
                f"Got: {error_msg}"
            )
            assert "html" in error_msg, (
                f"Error message should list 'html' as a registered format. "
                f"Got: {error_msg}"
            )
            # Verify the supported_formats attribute
            assert "markdown" in exc.supported_formats, (
                f"supported_formats should contain 'markdown'. "
                f"Got: {exc.supported_formats}"
            )
            assert "html" in exc.supported_formats, (
                f"supported_formats should contain 'html'. "
                f"Got: {exc.supported_formats}"
            )
