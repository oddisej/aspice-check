"""Markdown renderer — converts the intermediate representation to Markdown.

Renders a list of :class:`ContentNode` objects into a complete Markdown document
with YAML front-matter metadata, relative image paths, and embedded AI-generated
image descriptions.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import yaml

from confluence_ai.models import (
    BlockquoteMacroNode,
    CodeBlockNode,
    ContentNode,
    GliffyNode,
    HeadingNode,
    HorizontalRuleNode,
    ImageNode,
    InlineNode,
    LinkNode,
    ListItemNode,
    ListNode,
    MacroNode,
    PageMetadata,
    ParagraphNode,
    TableNode,
    TextNode,
)

if TYPE_CHECKING:
    pass


class MarkdownRenderer:
    """Renders ContentNode IR to Markdown with front-matter and image descriptions."""

    def render(
        self,
        nodes: list[ContentNode],
        metadata: PageMetadata,
        descriptions: dict[str, str] | None = None,
    ) -> str:
        """Render content nodes to a complete Markdown document.

        Args:
            nodes: Ordered list of content nodes from the parser.
            metadata: Page metadata for YAML front-matter.
            descriptions: Optional dict mapping image local paths to descriptions.

        Returns:
            Complete Markdown string with YAML front-matter.
        """
        self._descriptions = descriptions or {}
        parts: list[str] = []

        parts.append(self._render_front_matter(metadata))

        for node in nodes:
            rendered = self._render_node(node)
            if rendered is not None:
                # Strip leading/trailing blank lines but preserve internal spacing
                stripped = rendered.strip("\n")
                if stripped:
                    parts.append(stripped)

        return "\n\n".join(parts) + "\n"

    # ------------------------------------------------------------------
    # Front-matter
    # ------------------------------------------------------------------

    def _render_front_matter(self, metadata: PageMetadata) -> str:
        """Render YAML front-matter block.

        Produces a ``---`` delimited YAML block containing page metadata fields.
        """
        data: dict[str, str | list[str]] = {
            "source_url": metadata.source_url,
            "page_id": metadata.page_id,
            "page_title": metadata.page_title,
            "export_timestamp": metadata.export_timestamp,
            "exporter_version": metadata.exporter_version,
        }
        if metadata.space_key:
            data["space_key"] = metadata.space_key
        if metadata.labels:
            data["labels"] = metadata.labels

        yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return f"---\n{yaml_str}---"

    # ------------------------------------------------------------------
    # Node dispatch
    # ------------------------------------------------------------------

    def _render_node(self, node: ContentNode) -> str:
        """Render a single content node to Markdown."""
        if isinstance(node, HeadingNode):
            return self._render_heading(node)
        elif isinstance(node, ParagraphNode):
            return self._render_paragraph(node)
        elif isinstance(node, ListNode):
            return self._render_list(node)
        elif isinstance(node, TableNode):
            return self._render_table(node)
        elif isinstance(node, CodeBlockNode):
            return self._render_code_block(node)
        elif isinstance(node, ImageNode):
            return self._render_image(node)
        elif isinstance(node, GliffyNode):
            return self._render_gliffy(node)
        elif isinstance(node, BlockquoteMacroNode):
            return self._render_blockquote_macro(node)
        elif isinstance(node, MacroNode):
            return self._render_macro(node)
        elif isinstance(node, HorizontalRuleNode):
            return self._render_horizontal_rule()
        else:
            return ""

    # ------------------------------------------------------------------
    # Headings
    # ------------------------------------------------------------------

    def _render_heading(self, node: HeadingNode) -> str:
        """Render a heading node: ``# `` prefix matching level (1–6)."""
        prefix = "#" * node.level
        return f"\n{prefix} {node.text}\n"

    # ------------------------------------------------------------------
    # Paragraphs & inline content
    # ------------------------------------------------------------------

    def _render_paragraph(self, node: ParagraphNode) -> str:
        """Render a paragraph with inline children."""
        text = self._render_inline_children(node.children)
        return f"\n{text}\n"

    def _render_inline_children(self, children: list[InlineNode]) -> str:
        """Render a list of inline nodes to a single string."""
        parts: list[str] = []
        for child in children:
            if isinstance(child, TextNode):
                parts.append(self._render_text_node(child))
            elif isinstance(child, LinkNode):
                parts.append(self._render_link_node(child))
            else:
                # Fallback for unknown inline types
                parts.append(str(child))
        return "".join(parts)

    def _render_text_node(self, node: TextNode) -> str:
        """Render a text node with formatting markers."""
        text = node.text
        if not text:
            return ""

        if node.code:
            return f"`{text}`"

        # Apply formatting — underline is rendered as italic per task spec
        if node.bold and (node.italic or node.underline):
            return f"***{text}***"
        if node.bold:
            return f"**{text}**"
        if node.italic or node.underline:
            return f"*{text}*"

        return text

    def _render_link_node(self, node: LinkNode) -> str:
        """Render a link node as ``[text](href)``."""
        return f"[{node.text}]({node.href})"

    # ------------------------------------------------------------------
    # Lists
    # ------------------------------------------------------------------

    def _render_list(self, node: ListNode, indent: int = 0) -> str:
        """Render an ordered or unordered list with nesting support."""
        lines: list[str] = []
        prefix_space = "    " * indent

        for i, item in enumerate(node.items):
            if node.ordered:
                bullet = f"{i + 1}."
            else:
                bullet = "-"

            item_lines = self._render_list_item(item, indent)
            if item_lines:
                # First line gets the bullet
                first_line = item_lines[0]
                lines.append(f"{prefix_space}{bullet} {first_line}")
                # Subsequent lines are indented to align with content after bullet
                continuation_indent = prefix_space + " " * (len(bullet) + 1)
                for line in item_lines[1:]:
                    if line.strip():
                        lines.append(f"{continuation_indent}{line}")
                    else:
                        lines.append("")
            else:
                lines.append(f"{prefix_space}{bullet} ")

        result = "\n".join(lines)
        if indent == 0:
            return f"\n{result}\n"
        return result

    def _render_list_item(self, item: ListItemNode, parent_indent: int = 0) -> list[str]:
        """Render a list item's children, returning lines of text."""
        lines: list[str] = []

        for child in item.children:
            if isinstance(child, ParagraphNode):
                text = self._render_inline_children(child.children)
                lines.append(text)
            elif isinstance(child, ListNode):
                nested = self._render_list(child, indent=parent_indent + 1)
                # Strip leading/trailing newlines from nested list
                nested_stripped = nested.strip()
                if nested_stripped:
                    lines.extend([""] + nested_stripped.split("\n"))
            else:
                rendered = self._render_node(child)
                if rendered:
                    lines.append(rendered.strip())

        return lines

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------

    def _render_table(self, node: TableNode) -> str:
        """Render a table with pipe-delimited columns and header separator row."""
        if not node.headers and not node.rows:
            return ""

        lines: list[str] = []

        # Determine column count
        col_count = max(
            len(node.headers) if node.headers else 0,
            max((len(row) for row in node.rows), default=0),
        )

        if col_count == 0:
            return ""

        # Render header row
        if node.headers:
            header_cells = self._pad_row(node.headers, col_count)
            header_cells = [c.replace("|", "\\|").replace("\n", " ") for c in header_cells]
            lines.append("| " + " | ".join(header_cells) + " |")
            lines.append("| " + " | ".join("---" for _ in range(col_count)) + " |")
        else:
            # No headers — use empty header row
            lines.append("| " + " | ".join("" for _ in range(col_count)) + " |")
            lines.append("| " + " | ".join("---" for _ in range(col_count)) + " |")

        # Render data rows
        for row in node.rows:
            cells = self._pad_row(row, col_count)
            # Escape pipe characters and replace newlines for table compatibility
            escaped = [cell.replace("|", "\\|").replace("\n", " ") for cell in cells]
            lines.append("| " + " | ".join(escaped) + " |")

        return "\n" + "\n".join(lines) + "\n"

    def _pad_row(self, row: list[str], col_count: int) -> list[str]:
        """Pad a row to the expected column count."""
        padded = list(row)
        while len(padded) < col_count:
            padded.append("")
        return padded[:col_count]

    # ------------------------------------------------------------------
    # Code blocks
    # ------------------------------------------------------------------

    def _render_code_block(self, node: CodeBlockNode) -> str:
        """Render a fenced code block with optional language."""
        lang = node.language or ""
        return f"\n```{lang}\n{node.content}\n```\n"

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def _render_image(self, node: ImageNode) -> str:
        """Render an image node.

        If ``local_path`` is set, produces a Markdown image reference with an
        optional blockquote description.  If ``local_path`` is ``None``,
        produces placeholder text indicating the missing image.
        """
        if node.local_path is None:
            filename = node.filename or node.url or "unknown"
            return f"\n*[Image not available: {filename}]*\n"

        alt = node.alt_text or node.filename or ""
        rel_path = f"images/{os.path.basename(node.local_path)}"
        lines = [f"![{alt}]({rel_path})"]

        description = self._descriptions.get(node.local_path)
        if description:
            lines.append("")
            lines.append(description)

        return "\n" + "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Gliffy diagrams
    # ------------------------------------------------------------------

    def _render_gliffy(self, node: GliffyNode) -> str:
        """Render a Gliffy diagram node.

        If ``local_path`` is set, produces a Markdown image reference using the
        diagram name as alt-text, with an optional blockquote description.
        If ``local_path`` is ``None``, produces placeholder text.
        """
        if node.local_path is None:
            return f"\n*[Gliffy diagram not available: {node.name}]*\n"

        alt = node.name or node.alt_text or "Gliffy diagram"
        rel_path = f"images/{os.path.basename(node.local_path)}"
        lines = [f"![{alt}]({rel_path})"]

        description = self._descriptions.get(node.local_path)
        if description:
            lines.append("")
            lines.append(description)

        return "\n" + "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Blockquote macros (note, warning, tip, info, expand)
    # ------------------------------------------------------------------

    # Prefix map for known admonition macros
    _ADMONITION_PREFIXES: dict[str, str] = {
        "note": "**Note:**",
        "warning": "⚠️ **Warning:**",
        "tip": "💡 **Tip:**",
        "info": "ℹ️ **Info:**",
        "expand": "**Expand:**",
    }

    def _render_blockquote_macro(self, node: BlockquoteMacroNode) -> str:
        """Render a known admonition macro as a Markdown blockquote."""
        prefix = self._ADMONITION_PREFIXES.get(node.macro_type, f"**{node.macro_type.title()}:**")

        # If there's a custom title, use it instead of the default prefix
        if node.title:
            prefix = f"**{node.title}:**"

        # Collect the body text from children
        body_lines: list[str] = []
        for child in node.children:
            rendered = self._render_node(child)
            if rendered:
                body_lines.append(rendered.strip())

        body_text = " ".join(body_lines) if body_lines else ""

        # Strip leading macro type name from body if it duplicates the prefix
        # (Confluence often includes "Note", "Warning", etc. as visible text
        # at the start of the body, e.g. "Note The Levels of...")
        if body_text:
            macro_label = node.macro_type.capitalize()
            for sep in [": ", " "]:
                candidate = f"{macro_label}{sep}"
                if body_text.startswith(candidate):
                    body_text = body_text[len(candidate):]
                    break

        if body_text:
            # Wrap each line in blockquote markers
            combined = f"{prefix} {body_text}"
            bq_lines = []
            for line in combined.split("\n"):
                bq_lines.append(f"> {line}" if line.strip() else ">")
            return "\n" + "\n".join(bq_lines) + "\n"
        else:
            return f"\n> {prefix}\n"

    # ------------------------------------------------------------------
    # Macros
    # ------------------------------------------------------------------

    def _render_macro(self, node: MacroNode) -> str:
        """Render an unknown macro as plain text with an HTML comment."""
        parts: list[str] = []
        if node.body:
            parts.append(node.body)
        parts.append(f"<!-- confluence macro: {node.name} -->")
        return "\n" + "\n".join(parts) + "\n"

    # ------------------------------------------------------------------
    # Horizontal rule
    # ------------------------------------------------------------------

    def _render_horizontal_rule(self) -> str:
        """Render a horizontal rule."""
        return "\n---\n"
