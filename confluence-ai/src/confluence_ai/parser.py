"""Storage format parser — converts Confluence XHTML to an intermediate representation.

Parses Confluence Cloud storage format (XHTML with ``ac:`` and ``ri:`` namespaces)
into a list of :class:`ContentNode` objects that can be rendered to Markdown by the
:class:`MarkdownRenderer`.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET

from confluence_ai.exceptions import ParseError
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
    ParagraphNode,
    TableNode,
    TextNode,
)

# Known admonition macros that render as blockquotes
_ADMONITION_MACROS: frozenset[str] = frozenset({"note", "warning", "tip", "info", "expand"})

# Transparent wrapper macros whose children are parsed as regular content
_TRANSPARENT_MACROS: frozenset[str] = frozenset({"multiexcerpt"})

# Confluence XML namespace URIs
_NS_AC = "http://atlassian.com/content"
_NS_RI = "http://atlassian.com/resource/identifier"

_NAMESPACES = {
    "ac": _NS_AC,
    "ri": _NS_RI,
}

# Fully-qualified tag helpers
_AC = f"{{{_NS_AC}}}"
_RI = f"{{{_NS_RI}}}"

# Heading tags → level
_HEADING_TAGS: dict[str, int] = {f"h{i}": i for i in range(1, 7)}

# Inline formatting tags → TextNode keyword
_INLINE_FORMAT: dict[str, str] = {
    "strong": "bold",
    "em": "italic",
    "u": "underline",
    "code": "code",
}


class StorageFormatParser:
    """Parses Confluence XHTML storage format into an intermediate representation.

    Confluence storage format wraps page content in XHTML with two custom
    namespaces:

    * ``ac`` — ``http://atlassian.com/content``
    * ``ri`` — ``http://atlassian.com/resource/identifier``

    The parser converts elements into :class:`ContentNode` dataclasses that
    form a flat list representing the page structure.
    """

    # Expose namespaces for external use (e.g. tests)
    _NAMESPACES = _NAMESPACES

    def parse(self, xhtml: str) -> list[ContentNode]:
        """Parse Confluence storage format XHTML into content nodes.

        Args:
            xhtml: Raw XHTML string from Confluence storage format.

        Returns:
            Ordered list of ContentNode objects representing the page structure.

        Raises:
            ParseError: If the XHTML is malformed and cannot be parsed.
        """
        # Register namespaces so ET doesn't mangle prefixes
        for prefix, uri in _NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        # Confluence storage format may contain HTML entities (&nbsp;, &mdash;,
        # etc.) that are valid in HTML but not in XML.  Replace them with their
        # Unicode equivalents before parsing.
        sanitized = _resolve_html_entities(xhtml)

        # Wrap in a root element to handle fragments
        wrapped = f"<root xmlns:ac=\"{_NS_AC}\" xmlns:ri=\"{_NS_RI}\">{sanitized}</root>"

        try:
            root = ET.fromstring(wrapped)
        except ET.ParseError as exc:
            raise ParseError(f"Malformed XHTML: {exc}") from exc

        return self._parse_children(root)

    # ------------------------------------------------------------------
    # Top-level element dispatch
    # ------------------------------------------------------------------

    def _parse_children(self, parent: ET.Element) -> list[ContentNode]:
        """Parse all child elements of *parent* into content nodes."""
        nodes: list[ContentNode] = []
        for child in parent:
            tag = _local_tag(child)

            if tag in _HEADING_TAGS:
                nodes.append(self._parse_heading(child, _HEADING_TAGS[tag]))
            elif tag == "p":
                nodes.append(self._parse_paragraph(child))
            elif tag in ("ul", "ol"):
                nodes.append(self._parse_list(child, ordered=(tag == "ol")))
            elif tag == "table":
                nodes.append(self._parse_table(child))
            elif tag == "hr":
                nodes.append(HorizontalRuleNode())
            elif tag == "pre":
                nodes.append(self._parse_pre(child))
            elif child.tag == f"{_AC}structured-macro":
                result = self._parse_structured_macro(child)
                if isinstance(result, list):
                    nodes.extend(result)
                else:
                    nodes.append(result)
            elif child.tag == f"{_AC}image":
                nodes.append(self._parse_ac_image(child))
            elif child.tag == f"{_AC}link":
                nodes.append(self._parse_ac_link(child))
            else:
                # Recurse into unknown wrapper elements (e.g. <div>, <span>)
                nodes.extend(self._parse_children(child))

        return nodes

    # ------------------------------------------------------------------
    # Headings
    # ------------------------------------------------------------------

    def _parse_heading(self, elem: ET.Element, level: int) -> HeadingNode:
        """Parse ``<h1>``–``<h6>`` into a :class:`HeadingNode`."""
        return HeadingNode(level=level, text=_get_all_text(elem).strip())

    # ------------------------------------------------------------------
    # Paragraphs & inline content
    # ------------------------------------------------------------------

    def _parse_paragraph(self, elem: ET.Element) -> ParagraphNode:
        """Parse ``<p>`` into a :class:`ParagraphNode` with inline children."""
        children = self._parse_inline_children(elem)
        return ParagraphNode(children=children)

    def _parse_inline_children(
        self,
        elem: ET.Element,
        *,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        code: bool = False,
    ) -> list[InlineNode]:
        """Recursively collect inline nodes from *elem*.

        Formatting flags are inherited from ancestor elements so that
        ``<strong><em>text</em></strong>`` produces a single
        ``TextNode(text, bold=True, italic=True)``.
        """
        nodes: list[InlineNode] = []

        # Leading text of the element itself
        if elem.text:
            nodes.append(
                TextNode(
                    text=elem.text,
                    bold=bold,
                    italic=italic,
                    underline=underline,
                    code=code,
                )
            )

        for child in elem:
            child_tag = _local_tag(child)

            if child_tag in _INLINE_FORMAT:
                # Inherit + set the new flag
                fmt_key = _INLINE_FORMAT[child_tag]
                kwargs = dict(bold=bold, italic=italic, underline=underline, code=code)
                kwargs[fmt_key] = True
                nodes.extend(self._parse_inline_children(child, **kwargs))
            elif child.tag == f"{_AC}link":
                nodes.append(self._parse_ac_link(child))
            elif child.tag == f"{_AC}image":
                # Images can appear inline inside paragraphs — we still
                # produce an ImageNode but it's technically a ContentNode.
                # Callers that need strict InlineNode typing can filter.
                nodes.append(self._parse_ac_image(child))  # type: ignore[arg-type]
            elif child_tag == "a":
                href = child.get("href", "")
                link_text = _get_all_text(child).strip()
                nodes.append(LinkNode(href=href, text=link_text))
            elif child_tag == "br":
                nodes.append(TextNode(text="\n", bold=bold, italic=italic, underline=underline, code=code))
            else:
                # Unknown inline element — recurse and keep formatting
                nodes.extend(
                    self._parse_inline_children(
                        child,
                        bold=bold,
                        italic=italic,
                        underline=underline,
                        code=code,
                    )
                )

            # Tail text after the child element
            if child.tail:
                nodes.append(
                    TextNode(
                        text=child.tail,
                        bold=bold,
                        italic=italic,
                        underline=underline,
                        code=code,
                    )
                )

        return nodes

    # ------------------------------------------------------------------
    # Lists
    # ------------------------------------------------------------------

    def _parse_list(self, elem: ET.Element, *, ordered: bool) -> ListNode:
        """Parse ``<ul>`` / ``<ol>`` into a :class:`ListNode`."""
        items: list[ListItemNode] = []
        for child in elem:
            if _local_tag(child) == "li":
                items.append(self._parse_list_item(child))
        return ListNode(ordered=ordered, items=items)

    def _parse_list_item(self, elem: ET.Element) -> ListItemNode:
        """Parse ``<li>`` into a :class:`ListItemNode`.

        A list item may contain plain text, inline formatting, or nested
        lists.  Plain text / inline content is wrapped in a
        :class:`ParagraphNode`; nested ``<ul>``/``<ol>`` become child
        :class:`ListNode` objects.
        """
        children: list[ContentNode] = []
        inline_nodes: list[InlineNode] = []

        # Collect leading text
        if elem.text and elem.text.strip():
            inline_nodes.append(TextNode(text=elem.text))

        for child in elem:
            child_tag = _local_tag(child)
            if child_tag in ("ul", "ol"):
                # Flush any accumulated inline content first
                if inline_nodes:
                    children.append(ParagraphNode(children=inline_nodes))
                    inline_nodes = []
                children.append(self._parse_list(child, ordered=(child_tag == "ol")))
            elif child_tag in _INLINE_FORMAT or child_tag in ("a", "br") or child.tag == f"{_AC}link":
                # Inline content within the list item
                if child_tag in _INLINE_FORMAT:
                    fmt_key = _INLINE_FORMAT[child_tag]
                    kwargs: dict[str, bool] = {fmt_key: True}
                    inline_nodes.extend(self._parse_inline_children(child, **kwargs))
                elif child.tag == f"{_AC}link":
                    inline_nodes.append(self._parse_ac_link(child))
                elif child_tag == "a":
                    href = child.get("href", "")
                    link_text = _get_all_text(child).strip()
                    inline_nodes.append(LinkNode(href=href, text=link_text))
                elif child_tag == "br":
                    inline_nodes.append(TextNode(text="\n"))
            elif child_tag == "p":
                # Flush inline, then add paragraph
                if inline_nodes:
                    children.append(ParagraphNode(children=inline_nodes))
                    inline_nodes = []
                children.append(self._parse_paragraph(child))
            else:
                # Other block-level elements inside <li>
                if inline_nodes:
                    children.append(ParagraphNode(children=inline_nodes))
                    inline_nodes = []
                children.extend(self._parse_children(ET.Element("wrapper", {})))
                # Actually parse the child
                wrapper = ET.Element("wrapper")
                wrapper.append(child)
                children.extend(self._parse_children(wrapper))

            # Tail text
            if child.tail and child.tail.strip():
                inline_nodes.append(TextNode(text=child.tail))

        # Flush remaining inline content
        if inline_nodes:
            children.append(ParagraphNode(children=inline_nodes))

        # If no structured children were found but there's plain text, wrap it
        if not children and elem.text and elem.text.strip():
            children.append(ParagraphNode(children=[TextNode(text=elem.text.strip())]))

        return ListItemNode(children=children)

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------

    def _parse_table(self, elem: ET.Element) -> TableNode:
        """Parse ``<table>`` into a :class:`TableNode`."""
        headers: list[str] = []
        rows: list[list[str]] = []

        for descendant in elem.iter():
            tag = _local_tag(descendant)
            if tag == "tr":
                cells: list[str] = []
                has_th = False
                for cell in descendant:
                    cell_tag = _local_tag(cell)
                    if cell_tag == "th":
                        has_th = True
                        cells.append(_get_cell_text(cell))
                    elif cell_tag == "td":
                        cells.append(_get_cell_text(cell))

                if has_th and not headers:
                    headers = cells
                elif cells:
                    rows.append(cells)

        return TableNode(headers=headers, rows=rows)

    # ------------------------------------------------------------------
    # Code blocks
    # ------------------------------------------------------------------

    def _parse_pre(self, elem: ET.Element) -> CodeBlockNode:
        """Parse ``<pre>`` into a :class:`CodeBlockNode`."""
        return CodeBlockNode(
            content=_get_all_text(elem),
            language="",
        )

    def _parse_code_macro(self, elem: ET.Element) -> CodeBlockNode:
        """Parse ``<ac:structured-macro ac:name="code">`` into a :class:`CodeBlockNode`."""
        language = ""
        content = ""

        for child in elem:
            if child.tag == f"{_AC}parameter":
                param_name = child.get(f"{_AC}name", "") or child.get("name", "")
                if param_name == "language":
                    language = (child.text or "").strip()
            elif child.tag == f"{_AC}plain-text-body":
                content = (child.text or "").strip()

        return CodeBlockNode(content=content, language=language)

    # ------------------------------------------------------------------
    # Confluence macros (ac:structured-macro)
    # ------------------------------------------------------------------

    def _parse_structured_macro(self, elem: ET.Element) -> ContentNode | list[ContentNode]:
        """Dispatch ``<ac:structured-macro>`` by its ``ac:name`` attribute."""
        macro_name = elem.get(f"{_AC}name", "") or elem.get("name", "")

        if macro_name == "gliffy":
            return self._parse_gliffy_macro(elem)
        elif macro_name == "code":
            return self._parse_code_macro(elem)
        elif macro_name in _ADMONITION_MACROS:
            return self._parse_admonition_macro(elem, macro_name)
        elif macro_name in _TRANSPARENT_MACROS:
            return self._parse_transparent_macro(elem)
        elif macro_name == "toc":
            # TOC macro — skip it, the Markdown headings serve as the TOC
            return []
        else:
            return self._parse_unknown_macro(elem, macro_name)

    def _parse_gliffy_macro(self, elem: ET.Element) -> GliffyNode:
        """Parse a Gliffy macro into a :class:`GliffyNode`."""
        name = ""
        diagram_id: str | None = None

        for child in elem:
            if child.tag == f"{_AC}parameter":
                param_name = child.get(f"{_AC}name", "") or child.get("name", "")
                value = (child.text or "").strip()
                if param_name == "name":
                    name = value
                elif param_name == "diagramId" or param_name == "macroId":
                    diagram_id = value

        return GliffyNode(name=name, diagram_id=diagram_id)

    def _parse_admonition_macro(
        self, elem: ET.Element, macro_type: str
    ) -> BlockquoteMacroNode:
        """Parse a known admonition macro (note, warning, tip, info, expand).

        These macros have an optional title parameter and a rich-text body.
        They are rendered as Markdown blockquotes.
        """
        title = ""
        children: list[ContentNode] = []

        for child in elem:
            if child.tag == f"{_AC}parameter":
                param_name = child.get(f"{_AC}name", "") or child.get("name", "")
                if param_name == "title":
                    title = (child.text or "").strip()
            elif child.tag == f"{_AC}rich-text-body":
                children = self._parse_children(child)
            elif child.tag == f"{_AC}plain-text-body":
                text = (child.text or "").strip()
                if text:
                    children = [ParagraphNode(children=[TextNode(text=text)])]

        return BlockquoteMacroNode(
            macro_type=macro_type, title=title, children=children
        )

    def _parse_transparent_macro(self, elem: ET.Element) -> list[ContentNode]:
        """Parse a transparent wrapper macro (e.g. multiexcerpt).

        The macro's children are parsed as regular content nodes, effectively
        unwrapping the macro.
        """
        children: list[ContentNode] = []
        for child in elem:
            if child.tag == f"{_AC}rich-text-body":
                children.extend(self._parse_children(child))
            elif child.tag == f"{_AC}plain-text-body":
                text = (child.text or "").strip()
                if text:
                    children.append(
                        ParagraphNode(children=[TextNode(text=text)])
                    )
        return children

    def _parse_unknown_macro(self, elem: ET.Element, macro_name: str) -> MacroNode:
        """Parse an unrecognised macro into a :class:`MacroNode`."""
        params: dict[str, str] = {}
        body = ""

        for child in elem:
            if child.tag == f"{_AC}parameter":
                param_name = child.get(f"{_AC}name", "") or child.get("name", "")
                params[param_name] = (child.text or "").strip()
            elif child.tag == f"{_AC}rich-text-body":
                body = _get_all_text(child).strip()
            elif child.tag == f"{_AC}plain-text-body":
                body = (child.text or "").strip()

        return MacroNode(name=macro_name, parameters=params, body=body)

    # ------------------------------------------------------------------
    # Images (ac:image)
    # ------------------------------------------------------------------

    def _parse_ac_image(self, elem: ET.Element) -> ImageNode:
        """Parse ``<ac:image>`` into an :class:`ImageNode`.

        The image source is determined by the child element:

        * ``<ri:attachment ri:filename="...">`` → attachment
        * ``<ri:url ri:value="...">`` → external URL
        """
        alt_text = elem.get(f"{_AC}alt", "") or elem.get("alt", "")

        for child in elem:
            if child.tag == f"{_RI}attachment":
                filename = child.get(f"{_RI}filename", "") or child.get("filename", "")
                return ImageNode(
                    source_type="attachment",
                    filename=filename,
                    alt_text=alt_text,
                )
            elif child.tag == f"{_RI}url":
                url = child.get(f"{_RI}value", "") or child.get("value", "")
                return ImageNode(
                    source_type="external",
                    url=url,
                    alt_text=alt_text,
                )

        # Fallback — image element with no recognised source
        return ImageNode(source_type="attachment", filename="", alt_text=alt_text)

    # ------------------------------------------------------------------
    # Links (ac:link)
    # ------------------------------------------------------------------

    def _parse_ac_link(self, elem: ET.Element) -> LinkNode:
        """Parse ``<ac:link>`` into a :class:`LinkNode`.

        Confluence links may reference pages, attachments, external URLs,
        or user mentions (``@user``).  We extract the best available href
        and the visible link text.
        """
        href = ""
        text = ""

        for child in elem:
            if child.tag == f"{_RI}page":
                # Internal page link
                title = child.get(f"{_RI}content-title", "") or child.get("content-title", "")
                href = title  # Best we can do without resolving the page URL
            elif child.tag == f"{_RI}attachment":
                filename = child.get(f"{_RI}filename", "") or child.get("filename", "")
                href = filename
            elif child.tag == f"{_RI}url":
                href = child.get(f"{_RI}value", "") or child.get("value", "")
            elif child.tag == f"{_RI}user":
                # User mention: <ri:user ri:userkey="..." ri:account-id="..." />
                # The display name comes from the link body, but if missing
                # we fall back to the userkey attribute.
                userkey = (
                    child.get(f"{_RI}userkey", "")
                    or child.get("userkey", "")
                    or child.get(f"{_RI}account-id", "")
                    or child.get("account-id", "")
                )
                if not href:
                    href = userkey
            elif child.tag == f"{_AC}plain-text-link-body":
                text = (child.text or "").strip()
            elif child.tag == f"{_AC}link-body":
                text = _get_all_text(child).strip()

        if not text:
            text = href

        return LinkNode(href=href, text=text)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


# Regex matching HTML named entities like &nbsp; &mdash; &ndash; etc.
# Excludes the five XML built-in entities (&amp; &lt; &gt; &quot; &apos;)
# which are already valid in XML.
_HTML_ENTITY_RE = re.compile(r"&(?!amp;|lt;|gt;|quot;|apos;|#)([a-zA-Z][a-zA-Z0-9]*);")


def _resolve_html_entities(text: str) -> str:
    """Replace HTML named entities with their Unicode equivalents.

    Confluence storage format may contain entities like ``&nbsp;``,
    ``&mdash;``, ``&ndash;``, ``&hellip;``, etc. that are valid in HTML
    but cause ``xml.etree.ElementTree`` to fail with "undefined entity".

    This function replaces each HTML entity with its Unicode character
    using Python's ``html`` module, while preserving the five XML
    built-in entities (``&amp;``, ``&lt;``, ``&gt;``, ``&quot;``,
    ``&apos;``).
    """
    def _replace(match: re.Match) -> str:
        entity = match.group(0)  # e.g. "&nbsp;"
        resolved = html.unescape(entity)
        if resolved == entity:
            # html.unescape didn't recognise it — leave as-is
            return entity
        return resolved

    return _HTML_ENTITY_RE.sub(_replace, text)


def _local_tag(elem: ET.Element) -> str:
    """Return the local (un-namespaced) tag name of *elem*."""
    tag = elem.tag
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _get_all_text(elem: ET.Element) -> str:
    """Recursively collect all text content from *elem* and its descendants."""
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        parts.append(_get_all_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _get_cell_text(cell: ET.Element) -> str:
    """Extract text from a table cell, preserving structure with ``<br>`` separators.

    For cells containing multiple paragraphs, list items, or other block-level
    elements, each block is separated by ``<br>`` so the content stays on one
    line in a Markdown table while remaining readable.

    Handles ``<ac:link>`` elements (including user mentions) by extracting
    the link body text or falling back to the href/userkey.
    """
    blocks: list[str] = []

    def _collect_blocks(elem: ET.Element) -> None:
        tag = _local_tag(elem)

        if tag in ("p", "li"):
            text = _get_all_text_with_links(elem).strip()
            if text:
                # Prefix list items with a bullet for readability
                if tag == "li":
                    text = f"• {text}"
                blocks.append(text)
            return

        # Handle ac:link elements (user mentions, page links, etc.)
        if elem.tag == f"{_AC}link":
            link_text = _extract_link_text(elem)
            if link_text:
                blocks.append(link_text)
            return

        # For other elements, recurse into children
        if elem.text and elem.text.strip():
            blocks.append(elem.text.strip())

        for child in elem:
            _collect_blocks(child)
            if child.tail and child.tail.strip():
                blocks.append(child.tail.strip())

    _collect_blocks(cell)

    if blocks:
        result = " <br> ".join(blocks)
    else:
        result = _get_all_text(cell).strip()

    # Collapse any remaining newlines into spaces
    result = result.replace("\n", " ")
    # Collapse multiple spaces
    result = re.sub(r" {2,}", " ", result)
    return result


def _extract_link_text(elem: ET.Element) -> str:
    """Extract display text from an ``<ac:link>`` element.

    Checks for ``<ac:plain-text-link-body>``, ``<ac:link-body>``,
    ``<ri:page>`` content-title, ``<ri:user>`` userkey, or ``<ri:url>`` value.
    """
    for child in elem:
        if child.tag == f"{_AC}plain-text-link-body":
            return (child.text or "").strip()
        elif child.tag == f"{_AC}link-body":
            return _get_all_text(child).strip()

    # No explicit link body — try to get a meaningful identifier
    for child in elem:
        if child.tag == f"{_RI}page":
            return child.get(f"{_RI}content-title", "") or child.get("content-title", "")
        elif child.tag == f"{_RI}user":
            return (
                child.get(f"{_RI}userkey", "")
                or child.get("userkey", "")
                or child.get(f"{_RI}account-id", "")
                or child.get("account-id", "")
            )
        elif child.tag == f"{_RI}url":
            return child.get(f"{_RI}value", "") or child.get("value", "")
        elif child.tag == f"{_RI}attachment":
            return child.get(f"{_RI}filename", "") or child.get("filename", "")

    return ""


def _get_all_text_with_links(elem: ET.Element) -> str:
    """Like ``_get_all_text`` but also extracts text from ``<ac:link>`` elements."""
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        if child.tag == f"{_AC}link":
            link_text = _extract_link_text(child)
            if link_text:
                parts.append(link_text)
        else:
            parts.append(_get_all_text_with_links(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)
