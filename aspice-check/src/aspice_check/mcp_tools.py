"""MCP tool JSON Schema declarations for the aspice-check MCP server.

Defines the input schemas for all five MCP tools exposed by the server.
These schemas follow the MCP protocol's JSON Schema format for parameter
validation.

Requirements: 18.2, 18.3, 18.4, 18.5, 18.6, 19.4
"""

from __future__ import annotations

EVALUATE_SDP_SCHEMA: dict = {
    "name": "evaluate_sdp",
    "description": (
        "Evaluate an SDP document against ASPICE knowledge base criteria "
        "and return a gap analysis report. Optionally saves the report to "
        "a local file and/or publishes it back to Confluence."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "sdp_content": {
                "type": "string",
                "description": "SDP document content as Markdown text",
            },
            "sdp_path": {
                "type": "string",
                "description": "Path to SDP Markdown file (alternative to sdp_content)",
            },
            "provider": {
                "type": "string",
                "enum": ["bedrock", "openai", "anthropic"],
                "description": "AI provider for evaluation",
            },
            "model": {
                "type": "string",
                "description": "Model identifier",
            },
            "target_level": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "default": 3,
                "description": "Target ASPICE capability level",
            },
            "process_groups": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Process groups to evaluate (default: SWE, SYS, MAN, SUP)",
            },
            "standard": {
                "type": "string",
                "default": "aspice",
                "description": "Knowledge base standard identifier",
            },
            "output_path": {
                "type": "string",
                "description": (
                    "Local file path to save the generated report. "
                    "If omitted, the report is only returned inline."
                ),
            },
            "output_format": {
                "type": "string",
                "enum": ["markdown", "html"],
                "default": "markdown",
                "description": "Report format (markdown or html)",
            },
        },
        "required": ["provider", "model"],
    },
}

VALIDATE_KB_SCHEMA: dict = {
    "name": "validate_kb",
    "description": "Validate a knowledge base directory for schema compliance and completeness",
    "inputSchema": {
        "type": "object",
        "properties": {
            "kb_path": {
                "type": "string",
                "description": "Path to knowledge base directory",
            },
            "standard": {
                "type": "string",
                "default": "aspice",
                "description": "Standard identifier to validate",
            },
        },
        "required": ["kb_path"],
    },
}

LIST_STANDARDS_SCHEMA: dict = {
    "name": "list_standards",
    "description": "List available knowledge base standards and their process groups",
    "inputSchema": {
        "type": "object",
        "properties": {
            "kb_path": {
                "type": "string",
                "description": "Path to knowledge base directory (uses bundled KB if omitted)",
            },
        },
    },
}

EXPORT_PAGE_SCHEMA: dict = {
    "name": "export_page",
    "description": "Export a Confluence Cloud page to Markdown with AI image descriptions",
    "inputSchema": {
        "type": "object",
        "properties": {
            "page_url": {
                "type": "string",
                "description": "Full Confluence Cloud page URL",
            },
            "output_dir": {
                "type": "string",
                "description": "Output directory path",
            },
            "email": {
                "type": "string",
                "description": "Confluence account email (falls back to CONFLUENCE_EMAIL env var)",
            },
            "api_token": {
                "type": "string",
                "description": "Confluence API token (falls back to CONFLUENCE_API_TOKEN env var)",
            },
            "ai_provider": {
                "type": "string",
                "enum": ["bedrock", "openai", "anthropic"],
                "description": "AI provider for image descriptions (optional)",
            },
            "ai_model": {
                "type": "string",
                "description": "AI model for image descriptions (optional)",
            },
            "output_format": {
                "type": "string",
                "default": "markdown",
                "description": "Output format (markdown, json, or custom)",
            },
        },
        "required": ["page_url", "output_dir"],
    },
}

DESCRIBE_IMAGE_SCHEMA: dict = {
    "name": "describe_image",
    "description": "Generate an AI description of an image file",
    "inputSchema": {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to the image file",
            },
            "provider": {
                "type": "string",
                "enum": ["bedrock", "openai", "anthropic"],
                "description": "AI provider for description",
            },
            "model": {
                "type": "string",
                "description": "Model identifier",
            },
            "is_gliffy": {
                "type": "boolean",
                "default": False,
                "description": "Whether the image is a Gliffy diagram",
            },
            "page_title": {
                "type": "string",
                "default": "",
                "description": "Page title for context",
            },
        },
        "required": ["image_path", "provider", "model"],
    },
}

PUBLISH_PAGE_SCHEMA: dict = {
    "name": "publish_page",
    "description": (
        "Publish content to Confluence Cloud as a page. Accepts either a "
        "local file path (Markdown or HTML) or inline HTML content. "
        "Updates existing pages with the same title instead of creating duplicates."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": (
                    "Path to a local Markdown or HTML file to publish. "
                    "If provided, file content is read and used as the page body."
                ),
            },
            "html_content": {
                "type": "string",
                "description": (
                    "Inline HTML content to publish (alternative to file_path)."
                ),
            },
            "email": {
                "type": "string",
                "description": "Confluence account email (falls back to CONFLUENCE_EMAIL env var)",
            },
            "api_token": {
                "type": "string",
                "description": "Confluence API token (falls back to CONFLUENCE_API_TOKEN env var)",
            },
            "base_url": {
                "type": "string",
                "description": (
                    "Confluence Cloud base URL "
                    "(e.g. https://acme.atlassian.net/wiki)"
                ),
            },
            "space_key": {
                "type": "string",
                "description": "Confluence space key",
            },
            "title": {
                "type": "string",
                "description": "Page title (used for deduplication — updates if exists)",
            },
            "parent_page_id": {
                "type": "string",
                "description": "Parent page ID to create the page under (optional)",
            },
        },
        "required": ["base_url", "space_key", "title"],
    },
}

EXPORT_CALENDAR_SCHEMA: dict = {
    "name": "export_calendar",
    "description": (
        "Export events from a Confluence Team Calendar to JSON or Markdown. "
        "Fetches events within an optional date range and writes the output file."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "base_url": {
                "type": "string",
                "description": (
                    "Confluence Cloud base URL "
                    "(e.g. https://acme.atlassian.net/wiki)"
                ),
            },
            "calendar_id": {
                "type": "string",
                "description": "The calendar or sub-calendar ID to export",
            },
            "output_dir": {
                "type": "string",
                "description": "Output directory path",
            },
            "output_format": {
                "type": "string",
                "enum": ["json", "markdown"],
                "default": "json",
                "description": "Output format (json or markdown)",
            },
            "start_date": {
                "type": "string",
                "description": "Start of date range in ISO 8601 format (optional)",
            },
            "end_date": {
                "type": "string",
                "description": "End of date range in ISO 8601 format (optional)",
            },
            "email": {
                "type": "string",
                "description": "Confluence account email (falls back to CONFLUENCE_EMAIL env var)",
            },
            "api_token": {
                "type": "string",
                "description": "Confluence API token (falls back to CONFLUENCE_API_TOKEN env var)",
            },
        },
        "required": ["base_url", "calendar_id", "output_dir"],
    },
}

LIST_CALENDARS_SCHEMA: dict = {
    "name": "list_calendars",
    "description": "List available calendars in a Confluence space",
    "inputSchema": {
        "type": "object",
        "properties": {
            "base_url": {
                "type": "string",
                "description": (
                    "Confluence Cloud base URL "
                    "(e.g. https://acme.atlassian.net/wiki)"
                ),
            },
            "space_key": {
                "type": "string",
                "description": "Confluence space key to query",
            },
            "email": {
                "type": "string",
                "description": "Confluence account email (falls back to CONFLUENCE_EMAIL env var)",
            },
            "api_token": {
                "type": "string",
                "description": "Confluence API token (falls back to CONFLUENCE_API_TOKEN env var)",
            },
        },
        "required": ["base_url", "space_key"],
    },
}

ALL_TOOL_SCHEMAS: list[dict] = [
    EVALUATE_SDP_SCHEMA,
    VALIDATE_KB_SCHEMA,
    LIST_STANDARDS_SCHEMA,
    EXPORT_PAGE_SCHEMA,
    DESCRIBE_IMAGE_SCHEMA,
    PUBLISH_PAGE_SCHEMA,
    EXPORT_CALENDAR_SCHEMA,
    LIST_CALENDARS_SCHEMA,
]
"""All MCP tool schemas in a single list for server registration."""
