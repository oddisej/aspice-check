"""Data models for the Confluence Page Exporter.

Contains all dataclasses for the intermediate representation (IR) content nodes,
API response models, configuration models, and result models.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Intermediate Representation (IR) — Content Nodes
# ---------------------------------------------------------------------------


@dataclass
class ContentNode:
    """Base class for all content nodes in the IR."""

    pass


@dataclass
class InlineNode:
    """Base for inline content within paragraphs."""

    pass


@dataclass
class TextNode(InlineNode):
    """A span of text with optional formatting."""

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    code: bool = False


@dataclass
class LinkNode(InlineNode):
    """A hyperlink."""

    href: str
    text: str


@dataclass
class HeadingNode(ContentNode):
    """A heading (h1–h6)."""

    level: int  # 1–6
    text: str


@dataclass
class ParagraphNode(ContentNode):
    """A paragraph containing inline content."""

    children: list[InlineNode] = field(default_factory=list)


@dataclass
class ListItemNode:
    """A single list item, which may contain nested content."""

    children: list[ContentNode] = field(default_factory=list)


@dataclass
class ListNode(ContentNode):
    """An ordered or unordered list."""

    ordered: bool
    items: list[ListItemNode] = field(default_factory=list)


@dataclass
class TableNode(ContentNode):
    """A table with optional header row."""

    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class ImageNode(ContentNode):
    """An inline image (attachment or external URL)."""

    source_type: str  # "attachment" or "external"
    filename: str | None = None
    url: str | None = None
    alt_text: str = ""
    local_path: str | None = None  # Set after download


@dataclass
class GliffyNode(ContentNode):
    """A Gliffy diagram macro."""

    name: str  # Diagram name/title
    diagram_id: str | None = None
    local_path: str | None = None  # Set after PNG download
    alt_text: str = ""


@dataclass
class CodeBlockNode(ContentNode):
    """A code block with optional language."""

    content: str
    language: str = ""


@dataclass
class HorizontalRuleNode(ContentNode):
    """A horizontal rule (<hr/>)."""

    pass


@dataclass
class BlockquoteMacroNode(ContentNode):
    """A known Confluence admonition macro (note, warning, tip, info, expand).

    Rendered as a Markdown blockquote with an appropriate prefix.
    """

    macro_type: str  # "note", "warning", "tip", "info", "expand"
    title: str = ""
    children: list[ContentNode] = field(default_factory=list)


@dataclass
class MacroNode(ContentNode):
    """A Confluence macro with no specific handler — rendered as plain text."""

    name: str
    parameters: dict[str, str] = field(default_factory=dict)
    body: str = ""


# ---------------------------------------------------------------------------
# API Models
# ---------------------------------------------------------------------------


@dataclass
class ParsedURL:
    """Result of parsing a Confluence Cloud page URL."""

    base_url: str  # e.g., "https://acme.atlassian.net/wiki"
    page_id: str  # e.g., "123456789"


@dataclass
class PageData:
    """Raw page data from the Confluence API."""

    page_id: str
    title: str
    storage_format: str  # Raw XHTML body
    version: int
    labels: list[str] = field(default_factory=list)
    space_key: str = ""


@dataclass
class AttachmentData:
    """Metadata for a page attachment."""

    filename: str
    media_type: str  # e.g., "image/png", "image/jpeg"
    download_url: str  # Relative URL for download
    file_size: int = 0
    comment: str = ""


@dataclass
class PageMetadata:
    """Metadata for the YAML front-matter block."""

    source_url: str
    page_id: str
    page_title: str
    export_timestamp: str  # ISO 8601
    exporter_version: str
    space_key: str = ""
    labels: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Config Models
# ---------------------------------------------------------------------------


@dataclass
class ImageDescriberConfig:
    """Configuration for the image description AI provider."""

    provider: str  # "anthropic", "openai", or "bedrock"
    model: str  # e.g., "claude-sonnet-4-20250514", "gpt-4o", Bedrock model ID
    api_key: str = ""
    max_tokens: int = 4096
    temperature: float = 0.2
    region: str = ""  # AWS region for Bedrock (default: us-east-1)


@dataclass
class ImageContext:
    """Context passed to the image describer for prompt construction."""

    is_gliffy: bool = False
    alt_text: str = ""
    page_title: str = ""
    filename: str = ""


# ---------------------------------------------------------------------------
# Result Models
# ---------------------------------------------------------------------------


@dataclass
class ExportResult:
    """Summary of an export operation for CLI output."""

    markdown_path: str
    images_downloaded: int
    descriptions_generated: int
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Calendar Models
# ---------------------------------------------------------------------------


@dataclass
class DateRange:
    """Inclusive start, exclusive end — matches most calendar APIs."""

    start: datetime.datetime
    end: datetime.datetime


@dataclass
class SubCalendar:
    """A child calendar nested under a parent Team Calendar."""

    calendar_id: str
    name: str
    type: str  # e.g., "custom", "leaves", "travel", "rota"
    color: str = ""
    description: str = ""


@dataclass
class Calendar:
    """A Confluence Team Calendar (parent)."""

    calendar_id: str
    name: str
    type: str
    space_key: str = ""
    description: str = ""
    sub_calendars: list[SubCalendar] = field(default_factory=list)


@dataclass
class Event:
    """A single calendar occurrence."""

    event_id: str
    summary: str
    start: datetime.datetime  # tz-aware
    end: datetime.datetime  # tz-aware
    all_day: bool = False
    description: str = ""
    location: str = ""
    organizer: str = ""
    sub_calendar_id: str = ""
    sub_calendar_name: str = ""


@dataclass
class CalendarMetadata:
    """Metadata block for the export output."""

    calendar_id: str
    calendar_name: str
    export_timestamp: str  # ISO 8601 UTC
    exporter_version: str
    date_range: DateRange
    event_count: int = 0


@dataclass
class CalendarExportResult:
    """Returned by export_calendar()."""

    output_path: str
    event_count: int
    warnings: list[str] = field(default_factory=list)
