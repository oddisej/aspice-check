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
            "publish": {
                "type": "boolean",
                "default": False,
                "description": "If true, publish the report to Confluence (requires confluence_* fields)",
            },
            "confluence_base_url": {
                "type": "string",
                "description": "Confluence base URL (e.g. https://acme.atlassian.net/wiki)",
            },
            "confluence_space_key": {
                "type": "string",
                "description": "Confluence space key where the report page will be created/updated",
            },
            "confluence_page_title": {
                "type": "string",
                "description": "Title for the published report page",
            },
            "confluence_parent_page_id": {
                "type": "string",
                "description": "Parent page ID (optional, makes the report a child page)",
            },
            "confluence_email": {
                "type": "string",
                "description": "Confluence email (required if publish=true)",
            },
            "confluence_api_token": {
                "type": "string",
                "description": "Confluence API token (required if publish=true)",
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
                "description": "Confluence account email",
            },
            "api_token": {
                "type": "string",
                "description": "Confluence API token",
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
        "required": ["page_url", "output_dir", "email", "api_token"],
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

ALL_TOOL_SCHEMAS: list[dict] = [
    EVALUATE_SDP_SCHEMA,
    VALIDATE_KB_SCHEMA,
    LIST_STANDARDS_SCHEMA,
    EXPORT_PAGE_SCHEMA,
    DESCRIBE_IMAGE_SCHEMA,
]
"""All MCP tool schemas in a single list for server registration."""
