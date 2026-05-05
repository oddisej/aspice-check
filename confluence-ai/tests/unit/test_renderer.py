"""Unit tests for the MarkdownRenderer class.

Tests cover all node types, front-matter generation, image descriptions,
placeholder text for failed downloads, and edge cases.
"""

from __future__ import annotations

from confluence_ai.models import (
    BlockquoteMacroNode,
    CodeBlockNode,
    GliffyNode,
    HeadingNode,
    HorizontalRuleNode,
    ImageNode,
    LinkNode,
    ListItemNode,
    ListNode,
    MacroNode,
    PageMetadata,
    ParagraphNode,
    TableNode,
    TextNode,
)
from confluence_ai.renderer import MarkdownRenderer


def _make_metadata(**overrides: str | list[str]) -> PageMetadata:
    """Create a PageMetadata with sensible defaults."""
    defaults = {
        "source_url": "https://acme.atlassian.net/wiki/spaces/ENG/pages/123/Test",
        "page_id": "123",
        "page_title": "Test Page",
        "export_timestamp": "2025-01-15T10:30:00Z",
        "exporter_version": "0.1.0",
        "space_key": "ENG",
        "labels": ["sdp", "process"],
    }
    defaults.update(overrides)
    return PageMetadata(**defaults)  # type: ignore[arg-type]


class TestRenderFrontMatter:
    """Tests for YAML front-matter generation."""

    def test_front_matter_contains_required_fields(self) -> None:
        renderer = MarkdownRenderer()
        metadata = _make_metadata()
        result = renderer._render_front_matter(metadata)

        assert result.startswith("---\n")
        assert result.endswith("---")
        assert "source_url:" in result
        assert "page_id:" in result
        assert "page_title:" in result
        assert "export_timestamp:" in result
        assert "exporter_version:" in result

    def test_front_matter_includes_space_key(self) -> None:
        renderer = MarkdownRenderer()
        metadata = _make_metadata(space_key="ENG")
        result = renderer._render_front_matter(metadata)

        assert "space_key: ENG" in result

    def test_front_matter_includes_labels(self) -> None:
        renderer = MarkdownRenderer()
        metadata = _make_metadata(labels=["sdp", "process"])
        result = renderer._render_front_matter(metadata)

        assert "labels:" in result
        assert "sdp" in result
        assert "process" in result

    def test_front_matter_omits_empty_space_key(self) -> None:
        renderer = MarkdownRenderer()
        metadata = _make_metadata(space_key="")
        result = renderer._render_front_matter(metadata)

        assert "space_key" not in result

    def test_front_matter_omits_empty_labels(self) -> None:
        renderer = MarkdownRenderer()
        metadata = _make_metadata(labels=[])
        result = renderer._render_front_matter(metadata)

        assert "labels" not in result

    def test_front_matter_values_match_metadata(self) -> None:
        renderer = MarkdownRenderer()
        metadata = _make_metadata()
        result = renderer._render_front_matter(metadata)

        assert metadata.source_url in result
        assert metadata.page_id in result
        assert metadata.page_title in result
        assert metadata.export_timestamp in result
        assert metadata.exporter_version in result


class TestRenderHeading:
    """Tests for heading rendering."""

    def test_h1(self) -> None:
        renderer = MarkdownRenderer()
        node = HeadingNode(level=1, text="Title")
        result = renderer._render_node(node)
        assert "# Title" in result
        assert not result.strip().startswith("##")

    def test_h3(self) -> None:
        renderer = MarkdownRenderer()
        node = HeadingNode(level=3, text="Subsection")
        result = renderer._render_node(node)
        assert "### Subsection" in result

    def test_h6(self) -> None:
        renderer = MarkdownRenderer()
        node = HeadingNode(level=6, text="Deep")
        result = renderer._render_node(node)
        assert "###### Deep" in result


class TestRenderParagraph:
    """Tests for paragraph and inline content rendering."""

    def test_plain_text(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = ParagraphNode(children=[TextNode(text="Hello world")])
        result = renderer._render_node(node)
        assert "Hello world" in result

    def test_bold_text(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = ParagraphNode(children=[TextNode(text="bold", bold=True)])
        result = renderer._render_node(node)
        assert "**bold**" in result

    def test_italic_text(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = ParagraphNode(children=[TextNode(text="italic", italic=True)])
        result = renderer._render_node(node)
        assert "*italic*" in result

    def test_underline_rendered_as_italic(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = ParagraphNode(children=[TextNode(text="underlined", underline=True)])
        result = renderer._render_node(node)
        assert "*underlined*" in result

    def test_code_text(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = ParagraphNode(children=[TextNode(text="code", code=True)])
        result = renderer._render_node(node)
        assert "`code`" in result

    def test_bold_italic_combined(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = ParagraphNode(children=[TextNode(text="both", bold=True, italic=True)])
        result = renderer._render_node(node)
        assert "***both***" in result

    def test_link(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = ParagraphNode(children=[LinkNode(href="https://example.com", text="Example")])
        result = renderer._render_node(node)
        assert "[Example](https://example.com)" in result

    def test_mixed_inline(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = ParagraphNode(
            children=[
                TextNode(text="Hello "),
                TextNode(text="world", bold=True),
                TextNode(text=" and "),
                LinkNode(href="https://example.com", text="link"),
            ]
        )
        result = renderer._render_node(node)
        assert "Hello " in result
        assert "**world**" in result
        assert "[link](https://example.com)" in result


class TestRenderList:
    """Tests for list rendering."""

    def test_unordered_list(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = ListNode(
            ordered=False,
            items=[
                ListItemNode(children=[ParagraphNode(children=[TextNode(text="Item 1")])]),
                ListItemNode(children=[ParagraphNode(children=[TextNode(text="Item 2")])]),
            ],
        )
        result = renderer._render_node(node)
        assert "- Item 1" in result
        assert "- Item 2" in result

    def test_ordered_list(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = ListNode(
            ordered=True,
            items=[
                ListItemNode(children=[ParagraphNode(children=[TextNode(text="First")])]),
                ListItemNode(children=[ParagraphNode(children=[TextNode(text="Second")])]),
            ],
        )
        result = renderer._render_node(node)
        assert "1. First" in result
        assert "2. Second" in result

    def test_nested_list(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        inner = ListNode(
            ordered=False,
            items=[
                ListItemNode(children=[ParagraphNode(children=[TextNode(text="Nested")])]),
            ],
        )
        node = ListNode(
            ordered=False,
            items=[
                ListItemNode(
                    children=[
                        ParagraphNode(children=[TextNode(text="Parent")]),
                        inner,
                    ]
                ),
            ],
        )
        result = renderer._render_node(node)
        assert "- Parent" in result
        assert "Nested" in result


class TestRenderTable:
    """Tests for table rendering."""

    def test_table_with_headers(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = TableNode(
            headers=["Name", "Value"],
            rows=[["foo", "1"], ["bar", "2"]],
        )
        result = renderer._render_node(node)
        assert "| Name | Value |" in result
        assert "| --- | --- |" in result
        assert "| foo | 1 |" in result
        assert "| bar | 2 |" in result

    def test_table_without_headers(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = TableNode(
            headers=[],
            rows=[["a", "b"], ["c", "d"]],
        )
        result = renderer._render_node(node)
        assert "| --- | --- |" in result
        assert "| a | b |" in result

    def test_empty_table(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = TableNode(headers=[], rows=[])
        result = renderer._render_node(node)
        assert result == ""

    def test_table_escapes_pipes(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = TableNode(
            headers=["Col"],
            rows=[["a|b"]],
        )
        result = renderer._render_node(node)
        assert "a\\|b" in result


class TestRenderCodeBlock:
    """Tests for code block rendering."""

    def test_code_block_with_language(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = CodeBlockNode(content="print('hello')", language="python")
        result = renderer._render_node(node)
        assert "```python" in result
        assert "print('hello')" in result
        assert result.strip().endswith("```")

    def test_code_block_without_language(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = CodeBlockNode(content="some code", language="")
        result = renderer._render_node(node)
        assert "```\n" in result
        assert "some code" in result


class TestRenderImage:
    """Tests for image rendering."""

    def test_image_with_local_path(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = ImageNode(
            source_type="attachment",
            filename="diagram.png",
            local_path="/output/images/diagram.png",
            alt_text="My Diagram",
        )
        result = renderer._render_node(node)
        assert "![My Diagram](images/diagram.png)" in result

    def test_image_with_description(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {"/output/images/diagram.png": "A process flow diagram"}
        node = ImageNode(
            source_type="attachment",
            filename="diagram.png",
            local_path="/output/images/diagram.png",
            alt_text="Diagram",
        )
        result = renderer._render_node(node)
        assert "![Diagram](images/diagram.png)" in result
        assert "A process flow diagram" in result

    def test_image_without_local_path_shows_placeholder(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = ImageNode(
            source_type="attachment",
            filename="missing.png",
            local_path=None,
        )
        result = renderer._render_node(node)
        assert "*[Image not available: missing.png]*" in result
        assert "![" not in result

    def test_image_placeholder_for_external(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = ImageNode(
            source_type="external",
            url="https://example.com/img.png",
            local_path=None,
        )
        result = renderer._render_node(node)
        assert "*[Image not available: https://example.com/img.png]*" in result

    def test_image_alt_falls_back_to_filename(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = ImageNode(
            source_type="attachment",
            filename="photo.jpg",
            local_path="/output/images/photo.jpg",
            alt_text="",
        )
        result = renderer._render_node(node)
        assert "![photo.jpg](images/photo.jpg)" in result


class TestRenderGliffy:
    """Tests for Gliffy diagram rendering."""

    def test_gliffy_with_local_path(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = GliffyNode(
            name="Process Flow",
            local_path="/output/images/process_flow.png",
        )
        result = renderer._render_node(node)
        assert "![Process Flow](images/process_flow.png)" in result

    def test_gliffy_with_description(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {"/output/images/flow.png": "A swimlane diagram"}
        node = GliffyNode(
            name="Flow",
            local_path="/output/images/flow.png",
        )
        result = renderer._render_node(node)
        assert "![Flow](images/flow.png)" in result
        assert "A swimlane diagram" in result

    def test_gliffy_without_local_path_shows_placeholder(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = GliffyNode(name="Missing Diagram", local_path=None)
        result = renderer._render_node(node)
        assert "*[Gliffy diagram not available: Missing Diagram]*" in result
        assert "![" not in result

    def test_gliffy_alt_text_is_diagram_name(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = GliffyNode(
            name="My Diagram",
            local_path="/output/images/my_diagram.png",
        )
        result = renderer._render_node(node)
        assert "![My Diagram](" in result


class TestRenderMacro:
    """Tests for unknown macro rendering."""

    def test_macro_with_body(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = MacroNode(name="custom-panel", body="This is important")
        result = renderer._render_node(node)
        assert "This is important" in result
        assert "<!-- confluence macro: custom-panel -->" in result

    def test_macro_without_body(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = MacroNode(name="toc", body="")
        result = renderer._render_node(node)
        assert "<!-- confluence macro: toc -->" in result


class TestRenderBlockquoteMacro:
    """Tests for admonition macro rendering as blockquotes."""

    def test_note_macro(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = BlockquoteMacroNode(
            macro_type="note",
            children=[ParagraphNode(children=[TextNode(text="This is a note.")])],
        )
        result = renderer._render_node(node)
        assert "> **Note:** This is a note." in result

    def test_warning_macro(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = BlockquoteMacroNode(
            macro_type="warning",
            children=[ParagraphNode(children=[TextNode(text="Be careful!")])],
        )
        result = renderer._render_node(node)
        assert "> ⚠️ **Warning:** Be careful!" in result

    def test_tip_macro(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = BlockquoteMacroNode(
            macro_type="tip",
            children=[ParagraphNode(children=[TextNode(text="A helpful tip.")])],
        )
        result = renderer._render_node(node)
        assert "> 💡 **Tip:** A helpful tip." in result

    def test_info_macro(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = BlockquoteMacroNode(
            macro_type="info",
            children=[ParagraphNode(children=[TextNode(text="Some information.")])],
        )
        result = renderer._render_node(node)
        assert "> ℹ️ **Info:** Some information." in result

    def test_expand_macro(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = BlockquoteMacroNode(
            macro_type="expand",
            children=[ParagraphNode(children=[TextNode(text="Expandable content.")])],
        )
        result = renderer._render_node(node)
        assert "> **Expand:** Expandable content." in result

    def test_admonition_with_custom_title(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = BlockquoteMacroNode(
            macro_type="note",
            title="Important",
            children=[ParagraphNode(children=[TextNode(text="Read this.")])],
        )
        result = renderer._render_node(node)
        assert "> **Important:** Read this." in result

    def test_admonition_empty_body(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = BlockquoteMacroNode(macro_type="note", children=[])
        result = renderer._render_node(node)
        assert "> **Note:**" in result


class TestRenderHorizontalRule:
    """Tests for horizontal rule rendering."""

    def test_horizontal_rule(self) -> None:
        renderer = MarkdownRenderer()
        renderer._descriptions = {}
        node = HorizontalRuleNode()
        result = renderer._render_node(node)
        assert "---" in result


class TestFullRender:
    """Tests for the complete render pipeline."""

    def test_full_document(self) -> None:
        renderer = MarkdownRenderer()
        metadata = _make_metadata()
        nodes = [
            HeadingNode(level=1, text="Title"),
            ParagraphNode(children=[TextNode(text="Hello world")]),
            HorizontalRuleNode(),
        ]
        result = renderer.render(nodes, metadata)

        # Front-matter present
        assert result.startswith("---\n")
        assert "page_title: Test Page" in result
        # Content present
        assert "# Title" in result
        assert "Hello world" in result
        assert "---" in result

    def test_render_with_descriptions(self) -> None:
        renderer = MarkdownRenderer()
        metadata = _make_metadata()
        nodes = [
            ImageNode(
                source_type="attachment",
                filename="img.png",
                local_path="/out/images/img.png",
                alt_text="Photo",
            ),
        ]
        descriptions = {"/out/images/img.png": "A beautiful photo"}
        result = renderer.render(nodes, metadata, descriptions)

        assert "![Photo](images/img.png)" in result
        assert "A beautiful photo" in result

    def test_render_ends_with_newline(self) -> None:
        renderer = MarkdownRenderer()
        metadata = _make_metadata()
        result = renderer.render([], metadata)
        assert result.endswith("\n")
