"""AI-powered Confluence toolkit — export, publish, and describe pages.

Programmatic API for Confluence Cloud: read pages, resolve user mentions,
download attachments, describe images via multimodal AI, render to
Markdown or JSON (or custom formats), and publish HTML back to Confluence.
"""

from __future__ import annotations

__version__ = "0.2.0"

# --- Core classes ---
from confluence_ai.client import ConfluenceClient
from confluence_ai.describer import ImageDescriber
from confluence_ai.downloader import AssetDownloader
from confluence_ai.output_renderer import OutputRenderer, register_renderer
from confluence_ai.parser import StorageFormatParser
from confluence_ai.renderer import MarkdownRenderer
from confluence_ai.url_parser import URLParser

# --- Factory & registry functions ---
from confluence_ai.providers import create_describer, register_describer

# --- Convenience functions ---
from confluence_ai.export import export_page
from confluence_ai.publish import publish_page

# --- Config & result models ---
from confluence_ai.models import (      
    ExportResult,
    ImageContext,
    ImageDescriberConfig,
    PageMetadata,
)

# --- Exceptions ---
from confluence_ai.exceptions import (
    AuthenticationError,
    ConfluenceConnectionError,
    DownloadError,
    ExporterError,
    FileSystemError,
    ImageDescriptionError,
    InvalidURLError,
    PageNotFoundError,
    ParseError,
)

# Importing this ensures the built-in JSON renderer registers itself.
from confluence_ai import json_renderer  # noqa: F401

__all__ = [
    # Version
    "__version__",
    # Core classes
    "ConfluenceClient",
    "StorageFormatParser",
    "MarkdownRenderer",
    "AssetDownloader",
    "ImageDescriber",
    "URLParser",
    "OutputRenderer",
    # Factory & registry
    "create_describer",
    "register_describer",
    "register_renderer",
    # Convenience functions
    "export_page",
    "publish_page",
    # Models
    "ImageDescriberConfig",
    "ImageContext",
    "PageMetadata",
    "ExportResult",
    # Exceptions
    "ExporterError",
    "InvalidURLError",
    "AuthenticationError",
    "ConfluenceConnectionError",
    "PageNotFoundError",
    "ParseError",
    "DownloadError",
    "ImageDescriptionError",
    "FileSystemError",
]
