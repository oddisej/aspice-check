"""Unit tests for the StorageFormatParser.

Covers the element-to-IR mapping for all supported Confluence storage format
elements, including headings, paragraphs, inline formatting, lists, tables,
images, Gliffy macros, code blocks, links, horizontal rules, and unknown macros.
"""

from __future__ import annotations

import pytest

from confluence_ai.exceptions import ParseError
from confluence_ai.models import (
    BlockquoteMacroNode,
    CodeBlockNode,
    ContentNode,
    GliffyNode,
    HeadingNode,
    HorizontalRuleNode,
    ImageNode,
    LinkNode,
    ListItemNode,
    ListNode,
    MacroNode,
    ParagraphNode,
    TableNode,
    TextNode,
)
from confluence_ai.parser import StorageFormatParser


@pytest.fixture
def parser() -> StorageFormatParser:
    return StorageFormatParser()


# ------------------------------------------------------------------
# Headings
# ------------------------------------------------------------------


class TestHeadings:
    def test_h1_through_h6(self, parser: StorageFormatParser) -> None:
        for level in range(1, 7):
            xhtml = f"<h{level}>Heading {level}</h{level}>"
            nodes = parser.parse(xhtml)
            assert len(nodes) == 1
            assert isinstance(nodes[0], HeadingNode)
            assert nodes[0].level == level
            assert nodes[0].text == f"Heading {level}"

    def test_heading_with_inline_formatting(self, parser: StorageFormatParser) -> None:
        xhtml = "<h2>Hello <strong>World</strong></h2>"
        nodes = parser.parse(xhtml)
        assert len(nodes) == 1
        assert isinstance(nodes[0], HeadingNode)
        assert nodes[0].text == "Hello World"


# ------------------------------------------------------------------
# Paragraphs & inline formatting
# ------------------------------------------------------------------


class TestParagraphs:
    def test_plain_paragraph(self, parser: StorageFormatParser) -> None:
        xhtml = "<p>Hello world</p>"
        nodes = parser.parse(xhtml)
        assert len(nodes) == 1
        assert isinstance(nodes[0], ParagraphNode)
        assert len(nodes[0].children) == 1
        assert isinstance(nodes[0].children[0], TextNode)
        assert nodes[0].children[0].text == "Hello world"

    def test_bold_text(self, parser: StorageFormatParser) -> None:
        xhtml = "<p><strong>bold</strong></p>"
        nodes = parser.parse(xhtml)
        para = nodes[0]
        assert isinstance(para, ParagraphNode)
        assert len(para.children) == 1
        text_node = para.children[0]
        assert isinstance(text_node, TextNode)
        assert text_node.text == "bold"
        assert text_node.bold is True

    def test_italic_text(self, parser: StorageFormatParser) -> None:
        xhtml = "<p><em>italic</em></p>"
        nodes = parser.parse(xhtml)
        text_node = nodes[0].children[0]
        assert isinstance(text_node, TextNode)
        assert text_node.italic is True

    def test_underline_text(self, parser: StorageFormatParser) -> None:
        xhtml = "<p><u>underlined</u></p>"
        nodes = parser.parse(xhtml)
        text_node = nodes[0].children[0]
        assert isinstance(text_node, TextNode)
        assert text_node.underline is True

    def test_code_text(self, parser: StorageFormatParser) -> None:
        xhtml = "<p><code>inline code</code></p>"
        nodes = parser.parse(xhtml)
        text_node = nodes[0].children[0]
        assert isinstance(text_node, TextNode)
        assert text_node.code is True

    def test_nested_formatting(self, parser: StorageFormatParser) -> None:
        xhtml = "<p><strong><em>bold italic</em></strong></p>"
        nodes = parser.parse(xhtml)
        text_node = nodes[0].children[0]
        assert isinstance(text_node, TextNode)
        assert text_node.bold is True
        assert text_node.italic is True

    def test_mixed_inline_content(self, parser: StorageFormatParser) -> None:
        xhtml = "<p>Hello <strong>bold</strong> world</p>"
        nodes = parser.parse(xhtml)
        para = nodes[0]
        assert isinstance(para, ParagraphNode)
        assert len(para.children) == 3
        assert para.children[0].text == "Hello "
        assert para.children[1].text == "bold"
        assert para.children[1].bold is True
        assert para.children[2].text == " world"

    def test_html_anchor_link(self, parser: StorageFormatParser) -> None:
        xhtml = '<p><a href="https://example.com">click here</a></p>'
        nodes = parser.parse(xhtml)
        para = nodes[0]
        assert isinstance(para, ParagraphNode)
        link = para.children[0]
        assert isinstance(link, LinkNode)
        assert link.href == "https://example.com"
        assert link.text == "click here"


# ------------------------------------------------------------------
# Lists
# ------------------------------------------------------------------


class TestLists:
    def test_unordered_list(self, parser: StorageFormatParser) -> None:
        xhtml = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        nodes = parser.parse(xhtml)
        assert len(nodes) == 1
        lst = nodes[0]
        assert isinstance(lst, ListNode)
        assert lst.ordered is False
        assert len(lst.items) == 2

    def test_ordered_list(self, parser: StorageFormatParser) -> None:
        xhtml = "<ol><li>First</li><li>Second</li></ol>"
        nodes = parser.parse(xhtml)
        lst = nodes[0]
        assert isinstance(lst, ListNode)
        assert lst.ordered is True
        assert len(lst.items) == 2

    def test_nested_list(self, parser: StorageFormatParser) -> None:
        xhtml = "<ul><li>Parent<ul><li>Child</li></ul></li></ul>"
        nodes = parser.parse(xhtml)
        lst = nodes[0]
        assert isinstance(lst, ListNode)
        assert len(lst.items) == 1
        parent_item = lst.items[0]
        # Should have a paragraph for "Parent" and a nested ListNode
        has_nested_list = any(
            isinstance(c, ListNode) for c in parent_item.children
        )
        assert has_nested_list


# ------------------------------------------------------------------
# Tables
# ------------------------------------------------------------------


class TestTables:
    def test_simple_table(self, parser: StorageFormatParser) -> None:
        xhtml = (
            "<table>"
            "<tr><th>Name</th><th>Value</th></tr>"
            "<tr><td>A</td><td>1</td></tr>"
            "<tr><td>B</td><td>2</td></tr>"
            "</table>"
        )
        nodes = parser.parse(xhtml)
        assert len(nodes) == 1
        table = nodes[0]
        assert isinstance(table, TableNode)
        assert table.headers == ["Name", "Value"]
        assert table.rows == [["A", "1"], ["B", "2"]]

    def test_table_without_headers(self, parser: StorageFormatParser) -> None:
        xhtml = (
            "<table>"
            "<tr><td>A</td><td>1</td></tr>"
            "<tr><td>B</td><td>2</td></tr>"
            "</table>"
        )
        nodes = parser.parse(xhtml)
        table = nodes[0]
        assert isinstance(table, TableNode)
        assert table.headers == []
        assert len(table.rows) == 2

    def test_empty_table(self, parser: StorageFormatParser) -> None:
        xhtml = "<table></table>"
        nodes = parser.parse(xhtml)
        table = nodes[0]
        assert isinstance(table, TableNode)
        assert table.headers == []
        assert table.rows == []


# ------------------------------------------------------------------
# Code blocks
# ------------------------------------------------------------------


class TestCodeBlocks:
    def test_pre_element(self, parser: StorageFormatParser) -> None:
        xhtml = "<pre>print('hello')</pre>"
        nodes = parser.parse(xhtml)
        assert len(nodes) == 1
        code = nodes[0]
        assert isinstance(code, CodeBlockNode)
        assert code.content == "print('hello')"
        assert code.language == ""

    def test_code_macro_with_language(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="code">'
            '<ac:parameter ac:name="language">python</ac:parameter>'
            "<ac:plain-text-body>def foo(): pass</ac:plain-text-body>"
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        assert len(nodes) == 1
        code = nodes[0]
        assert isinstance(code, CodeBlockNode)
        assert code.language == "python"
        assert code.content == "def foo(): pass"

    def test_code_macro_without_language(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="code">'
            "<ac:plain-text-body>some code</ac:plain-text-body>"
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        code = nodes[0]
        assert isinstance(code, CodeBlockNode)
        assert code.language == ""
        assert code.content == "some code"


# ------------------------------------------------------------------
# Images
# ------------------------------------------------------------------


class TestImages:
    def test_attachment_image(self, parser: StorageFormatParser) -> None:
        xhtml = (
            "<ac:image>"
            '<ri:attachment ri:filename="diagram.png" />'
            "</ac:image>"
        )
        nodes = parser.parse(xhtml)
        assert len(nodes) == 1
        img = nodes[0]
        assert isinstance(img, ImageNode)
        assert img.source_type == "attachment"
        assert img.filename == "diagram.png"

    def test_external_image(self, parser: StorageFormatParser) -> None:
        xhtml = (
            "<ac:image>"
            '<ri:url ri:value="https://example.com/img.png" />'
            "</ac:image>"
        )
        nodes = parser.parse(xhtml)
        img = nodes[0]
        assert isinstance(img, ImageNode)
        assert img.source_type == "external"
        assert img.url == "https://example.com/img.png"


# ------------------------------------------------------------------
# Gliffy macros
# ------------------------------------------------------------------


class TestGliffyMacros:
    def test_gliffy_macro(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="gliffy">'
            '<ac:parameter ac:name="name">My Diagram</ac:parameter>'
            '<ac:parameter ac:name="diagramId">12345</ac:parameter>'
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        assert len(nodes) == 1
        gliffy = nodes[0]
        assert isinstance(gliffy, GliffyNode)
        assert gliffy.name == "My Diagram"
        assert gliffy.diagram_id == "12345"

    def test_gliffy_macro_without_id(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="gliffy">'
            '<ac:parameter ac:name="name">Simple Diagram</ac:parameter>'
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        gliffy = nodes[0]
        assert isinstance(gliffy, GliffyNode)
        assert gliffy.name == "Simple Diagram"
        assert gliffy.diagram_id is None


# ------------------------------------------------------------------
# Links (ac:link)
# ------------------------------------------------------------------


class TestLinks:
    def test_ac_link_with_page_reference(self, parser: StorageFormatParser) -> None:
        xhtml = (
            "<ac:link>"
            '<ri:page ri:content-title="Target Page" />'
            "<ac:plain-text-link-body>Click here</ac:plain-text-link-body>"
            "</ac:link>"
        )
        nodes = parser.parse(xhtml)
        assert len(nodes) == 1
        link = nodes[0]
        assert isinstance(link, LinkNode)
        assert link.href == "Target Page"
        assert link.text == "Click here"

    def test_ac_link_with_url(self, parser: StorageFormatParser) -> None:
        xhtml = (
            "<ac:link>"
            '<ri:url ri:value="https://example.com" />'
            "<ac:plain-text-link-body>Example</ac:plain-text-link-body>"
            "</ac:link>"
        )
        nodes = parser.parse(xhtml)
        link = nodes[0]
        assert isinstance(link, LinkNode)
        assert link.href == "https://example.com"
        assert link.text == "Example"

    def test_ac_link_without_text(self, parser: StorageFormatParser) -> None:
        xhtml = (
            "<ac:link>"
            '<ri:url ri:value="https://example.com" />'
            "</ac:link>"
        )
        nodes = parser.parse(xhtml)
        link = nodes[0]
        assert isinstance(link, LinkNode)
        assert link.text == "https://example.com"  # Falls back to href


# ------------------------------------------------------------------
# Horizontal rules
# ------------------------------------------------------------------


class TestHorizontalRules:
    def test_hr(self, parser: StorageFormatParser) -> None:
        xhtml = "<hr />"
        nodes = parser.parse(xhtml)
        assert len(nodes) == 1
        assert isinstance(nodes[0], HorizontalRuleNode)


# ------------------------------------------------------------------
# Unknown macros → MacroNode
# ------------------------------------------------------------------


class TestUnknownMacros:
    def test_unknown_macro(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="custom-panel">'
            '<ac:parameter ac:name="title">Note</ac:parameter>'
            "<ac:rich-text-body>This is important info.</ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        assert len(nodes) == 1
        macro = nodes[0]
        assert isinstance(macro, MacroNode)
        assert macro.name == "custom-panel"
        assert macro.parameters == {"title": "Note"}
        assert macro.body == "This is important info."

    def test_unknown_macro_with_plain_text_body(
        self, parser: StorageFormatParser
    ) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="noformat">'
            "<ac:plain-text-body>raw text here</ac:plain-text-body>"
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        macro = nodes[0]
        assert isinstance(macro, MacroNode)
        assert macro.name == "noformat"
        assert macro.body == "raw text here"


# ------------------------------------------------------------------
# Admonition macros → BlockquoteMacroNode
# ------------------------------------------------------------------


class TestAdmonitionMacros:
    def test_note_macro(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="note">'
            "<ac:rich-text-body><p>This is a note.</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        assert len(nodes) == 1
        node = nodes[0]
        assert isinstance(node, BlockquoteMacroNode)
        assert node.macro_type == "note"
        assert len(node.children) == 1
        assert isinstance(node.children[0], ParagraphNode)

    def test_warning_macro(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="warning">'
            "<ac:rich-text-body><p>Be careful!</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        node = nodes[0]
        assert isinstance(node, BlockquoteMacroNode)
        assert node.macro_type == "warning"

    def test_tip_macro(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="tip">'
            "<ac:rich-text-body><p>A helpful tip.</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        node = nodes[0]
        assert isinstance(node, BlockquoteMacroNode)
        assert node.macro_type == "tip"

    def test_info_macro(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="info">'
            "<ac:rich-text-body><p>Some information.</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        node = nodes[0]
        assert isinstance(node, BlockquoteMacroNode)
        assert node.macro_type == "info"

    def test_expand_macro(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="expand">'
            "<ac:rich-text-body><p>Expandable content.</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        node = nodes[0]
        assert isinstance(node, BlockquoteMacroNode)
        assert node.macro_type == "expand"

    def test_admonition_with_title(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="note">'
            '<ac:parameter ac:name="title">Important</ac:parameter>'
            "<ac:rich-text-body><p>Read this carefully.</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        node = nodes[0]
        assert isinstance(node, BlockquoteMacroNode)
        assert node.macro_type == "note"
        assert node.title == "Important"

    def test_admonition_with_plain_text_body(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="note">'
            "<ac:plain-text-body>Plain text note.</ac:plain-text-body>"
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        node = nodes[0]
        assert isinstance(node, BlockquoteMacroNode)
        assert node.macro_type == "note"
        assert len(node.children) == 1
        assert isinstance(node.children[0], ParagraphNode)

    def test_admonition_with_complex_body(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="info">'
            "<ac:rich-text-body>"
            "<p>First paragraph.</p>"
            "<p>Second paragraph.</p>"
            "</ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        node = nodes[0]
        assert isinstance(node, BlockquoteMacroNode)
        assert len(node.children) == 2


# ------------------------------------------------------------------
# Transparent macros (multiexcerpt)
# ------------------------------------------------------------------


class TestTransparentMacros:
    def test_multiexcerpt_unwraps_children(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="multiexcerpt">'
            '<ac:parameter ac:name="MultiExcerptName">excerpt1</ac:parameter>'
            "<ac:rich-text-body>"
            "<h2>Section Title</h2>"
            "<p>Some content.</p>"
            "</ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        # Should produce the children directly, not a MacroNode
        assert len(nodes) == 2
        assert isinstance(nodes[0], HeadingNode)
        assert nodes[0].text == "Section Title"
        assert isinstance(nodes[1], ParagraphNode)

    def test_multiexcerpt_with_plain_text_body(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="multiexcerpt">'
            "<ac:plain-text-body>Just text.</ac:plain-text-body>"
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        assert len(nodes) == 1
        assert isinstance(nodes[0], ParagraphNode)

    def test_multiexcerpt_empty_body(self, parser: StorageFormatParser) -> None:
        xhtml = (
            '<ac:structured-macro ac:name="multiexcerpt">'
            '<ac:parameter ac:name="MultiExcerptName">empty</ac:parameter>'
            "</ac:structured-macro>"
        )
        nodes = parser.parse(xhtml)
        assert nodes == []


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------


class TestParseErrors:
    def test_malformed_xhtml_raises_parse_error(
        self, parser: StorageFormatParser
    ) -> None:
        xhtml = "<p>Unclosed paragraph"
        with pytest.raises(ParseError, match="Malformed XHTML"):
            parser.parse(xhtml)

    def test_completely_invalid_xml(self, parser: StorageFormatParser) -> None:
        xhtml = "<<<not xml at all>>>"
        with pytest.raises(ParseError):
            parser.parse(xhtml)


# ------------------------------------------------------------------
# Mixed content
# ------------------------------------------------------------------


class TestMixedContent:
    def test_multiple_elements(self, parser: StorageFormatParser) -> None:
        xhtml = (
            "<h1>Title</h1>"
            "<p>Some text</p>"
            "<hr />"
            "<ul><li>Item</li></ul>"
        )
        nodes = parser.parse(xhtml)
        assert len(nodes) == 4
        assert isinstance(nodes[0], HeadingNode)
        assert isinstance(nodes[1], ParagraphNode)
        assert isinstance(nodes[2], HorizontalRuleNode)
        assert isinstance(nodes[3], ListNode)

    def test_empty_input(self, parser: StorageFormatParser) -> None:
        nodes = parser.parse("")
        assert nodes == []

    def test_table_with_tbody(self, parser: StorageFormatParser) -> None:
        """Tables wrapped in <tbody> should still parse correctly."""
        xhtml = (
            "<table><tbody>"
            "<tr><th>H1</th><th>H2</th></tr>"
            "<tr><td>A</td><td>B</td></tr>"
            "</tbody></table>"
        )
        nodes = parser.parse(xhtml)
        table = nodes[0]
        assert isinstance(table, TableNode)
        assert table.headers == ["H1", "H2"]
        assert table.rows == [["A", "B"]]


# ------------------------------------------------------------------
# HTML entity handling
# ------------------------------------------------------------------


class TestHTMLEntities:
    """Tests for HTML entity resolution in Confluence storage format."""

    def test_nbsp_entity(self, parser: StorageFormatParser) -> None:
        """&nbsp; entities are resolved to Unicode non-breaking space."""
        xhtml = "<p>Hello&nbsp;world</p>"
        nodes = parser.parse(xhtml)
        assert len(nodes) == 1
        assert isinstance(nodes[0], ParagraphNode)
        text = nodes[0].children[0].text
        assert "Hello" in text
        assert "world" in text

    def test_mdash_entity(self, parser: StorageFormatParser) -> None:
        """&mdash; entities are resolved to Unicode em dash."""
        xhtml = "<p>Hello&mdash;world</p>"
        nodes = parser.parse(xhtml)
        text = nodes[0].children[0].text
        assert "\u2014" in text  # em dash

    def test_ndash_entity(self, parser: StorageFormatParser) -> None:
        """&ndash; entities are resolved to Unicode en dash."""
        xhtml = "<p>2020&ndash;2025</p>"
        nodes = parser.parse(xhtml)
        text = nodes[0].children[0].text
        assert "\u2013" in text  # en dash

    def test_multiple_entities(self, parser: StorageFormatParser) -> None:
        """Multiple HTML entities in one document are all resolved."""
        xhtml = "<p>A&nbsp;B&mdash;C&hellip;D</p>"
        nodes = parser.parse(xhtml)
        text = nodes[0].children[0].text
        assert "A" in text
        assert "B" in text
        assert "C" in text
        assert "D" in text

    def test_xml_entities_preserved(self, parser: StorageFormatParser) -> None:
        """XML built-in entities (&amp; &lt; &gt;) are preserved correctly."""
        xhtml = "<p>A &amp; B &lt; C &gt; D</p>"
        nodes = parser.parse(xhtml)
        text = nodes[0].children[0].text
        assert "A & B < C > D" == text

    def test_numeric_entities(self, parser: StorageFormatParser) -> None:
        """Numeric character references (&#160;) work without modification."""
        xhtml = "<p>Hello&#160;world</p>"
        nodes = parser.parse(xhtml)
        text = nodes[0].children[0].text
        assert "Hello" in text
        assert "world" in text
