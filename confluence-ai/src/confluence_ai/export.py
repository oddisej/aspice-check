"""High-level convenience function for exporting Confluence pages.

Orchestrates the full export pipeline: URL parsing → Confluence retrieval
→ XHTML parsing → asset downloading → optional AI image description →
rendering → file output.

This module exposes :func:`export_page`, the single entry point that
wires :class:`~confluence_ai.client.ConfluenceClient`,
:class:`~confluence_ai.parser.StorageFormatParser`,
:class:`~confluence_ai.downloader.AssetDownloader`,
:class:`~confluence_ai.describer.ImageDescriber`, and the
pluggable :class:`~confluence_ai.output_renderer.OutputRenderer` registry
into a single callable.

Requirements: 4.1, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 22.6, 23.1, 23.2
"""

from __future__ import annotations

import datetime
import logging
import os
import re

import confluence_ai
from confluence_ai.client import ConfluenceClient
from confluence_ai.describer import ImageDescriber
from confluence_ai.downloader import AssetDownloader
from confluence_ai.exceptions import AuthenticationError
from confluence_ai.models import (
    BlockquoteMacroNode,
    ContentNode,
    ExportResult,
    GliffyNode,
    ImageContext,
    ImageDescriberConfig,
    ImageNode,
    LinkNode,
    ListNode,
    PageMetadata,
    ParagraphNode,
    TableNode,
    TextNode,
)
from confluence_ai.output_renderer import get_renderer
from confluence_ai.parser import StorageFormatParser
from confluence_ai.providers import create_describer
from confluence_ai.url_parser import URLParser

# Importing these modules has the side effect of registering the built-in
# renderers ("markdown" and "json") with the output_renderer registry.
import confluence_ai.json_renderer  # noqa: F401
import confluence_ai.renderer  # noqa: F401


logger = logging.getLogger(__name__)


# Account ID pattern: 24-character hex string (Confluence Cloud user IDs).
_ACCOUNT_ID_RE = re.compile(r"^[0-9a-f]{24}$")


# ---------------------------------------------------------------------------
# Public convenience function
# ---------------------------------------------------------------------------


def export_page(
    page_url: str,
    output_dir: str,
    *,
    email: str,
    api_token: str,
    confluence_base_url: str | None = None,
    ai_config: ImageDescriberConfig | None = None,
    output_format: str = "markdown",
) -> ExportResult:
    """Export a Confluence Cloud page to a local file.

    Orchestrates the full export pipeline: URL parsing → page retrieval
    → XHTML parsing → asset downloading → AI image description →
    rendering → file output. Returns an :class:`ExportResult` describing
    the outcome.

    Parameters
    ----------
    page_url:
        Full Confluence Cloud page URL.
    output_dir:
        Directory where the output file and ``images/`` subdirectory will
        be written. Created if it does not exist.
    email:
        Confluence account email for authentication. Must be non-empty.
    api_token:
        Confluence Cloud API token. Must be non-empty.
    confluence_base_url:
        Override the base URL extracted from ``page_url``. Useful for
        custom Confluence domains.
    ai_config:
        Configuration for AI image description. If ``None``, image
        descriptions are skipped.
    output_format:
        Output format name. Defaults to ``"markdown"``. Use ``"json"``
        for structured IR output. Custom formats can be registered via
        :func:`confluence_ai.register_renderer`.

    Returns
    -------
    ExportResult
        Contains output file path, image count, description count, and
        any warnings produced during export.

    Raises
    ------
    AuthenticationError
        If ``email`` or ``api_token`` is empty or ``None``. The message
        names the missing field.
    InvalidURLError
        If ``page_url`` doesn't match Confluence Cloud URL patterns.
    ValueError
        If ``output_format`` is not a registered renderer name. The
        message lists all registered format names.
    ConfluenceConnectionError
        If the Confluence server is unreachable.
    PageNotFoundError
        If the page doesn't exist or the user lacks access.

    Examples
    --------
    Minimal Markdown export without AI descriptions::

        from confluence_ai import export_page

        result = export_page(
            "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456/My-SDP",
            "./output",
            email="user@acme.com",
            api_token="secret-token",
        )
        print(result.markdown_path)  # ./output/My-SDP.md

    Export with AI-generated image descriptions via Bedrock::

        from confluence_ai import export_page, ImageDescriberConfig

        result = export_page(
            "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456/My-SDP",
            "./output",
            email="user@acme.com",
            api_token="secret-token",
            ai_config=ImageDescriberConfig(
                provider="bedrock",
                model="us.anthropic.claude-sonnet-4-20250514-v1:0",
                region="us-east-1",
            ),
        )
        print(f"Images: {result.images_downloaded}, "
              f"Descriptions: {result.descriptions_generated}")

    Export as structured JSON for programmatic consumption::

        result = export_page(
            "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456/My-SDP",
            "./output",
            email="user@acme.com",
            api_token="secret-token",
            output_format="json",
        )
    """
    # --- 1. Validate credentials up front -------------------------------
    if not email:
        raise AuthenticationError(
            base_url=confluence_base_url or "",
            message=(
                "Confluence email is required but was empty or None. "
                "Pass a non-empty value via the 'email' parameter."
            ),
        )
    if not api_token:
        raise AuthenticationError(
            base_url=confluence_base_url or "",
            message=(
                "Confluence API token is required but was empty or None. "
                "Pass a non-empty value via the 'api_token' parameter."
            ),
        )

    # --- 2. Parse URL (raises InvalidURLError on mismatch) --------------
    parsed = URLParser().parse(page_url)
    base_url = confluence_base_url or parsed.base_url
    page_id = parsed.page_id
    logger.debug("Base URL: %s, Page ID: %s", base_url, page_id)

    # --- 3. Resolve renderer (raises ValueError listing formats) -------
    renderer_class = get_renderer(output_format)
    renderer = renderer_class()

    warnings_list: list[str] = []

    # --- 4. Connect to Confluence ---------------------------------------
    logger.info("Connecting to Confluence at %s", base_url)
    client = ConfluenceClient(
        base_url=base_url, email=email, api_token=api_token
    )

    # --- 5. Retrieve page + attachments ---------------------------------
    logger.info("Retrieving page %s", page_id)
    page_data = client.get_page(page_id)
    logger.info("Page title: %s", page_data.title)

    attachments = client.get_attachments(page_id)
    logger.info("Found %d attachments", len(attachments))

    # --- 6. Parse storage format ----------------------------------------
    nodes = StorageFormatParser().parse(page_data.storage_format)
    logger.info("Parsed %d content nodes", len(nodes))

    # --- 7. Resolve user mentions (Req 23.1, 23.2) ----------------------
    account_ids = _collect_account_ids(nodes)
    if account_ids:
        logger.info("Resolving %d user mention(s)", len(account_ids))
        try:
            user_map = client.resolve_user_ids(account_ids)
        except Exception as exc:
            # Network/API failure — fall back to raw account IDs + warn.
            warning = (
                f"Failed to resolve user mentions: {exc}. "
                "Raw account IDs preserved in output."
            )
            logger.warning(warning)
            warnings_list.append(warning)
            user_map = {}

        if user_map:
            _replace_account_ids(nodes, user_map)

        unresolved = account_ids - set(user_map)
        if unresolved:
            warning = (
                f"Could not resolve {len(unresolved)} user mention(s); "
                "raw account IDs preserved in output."
            )
            logger.warning(warning)
            warnings_list.append(warning)

    # --- 8. Create output directories -----------------------------------
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "images"), exist_ok=True)

    # --- 9. Download assets ---------------------------------------------
    downloader = AssetDownloader(client=client, output_dir=output_dir)
    nodes = downloader.download_assets(nodes, attachments)
    images_downloaded = sum(
        1
        for n in nodes
        if isinstance(n, (ImageNode, GliffyNode)) and n.local_path is not None
    )
    logger.info("Downloaded %d images", images_downloaded)

    # --- 10. Generate AI descriptions (optional) ------------------------
    descriptions: dict[str, str] = {}
    descriptions_generated = 0
    if ai_config is not None:
        describer: ImageDescriber = create_describer(ai_config)
        image_tasks = _collect_image_tasks(
            nodes, page_data.title, output_dir
        )
        if image_tasks:
            logger.info(
                "Generating AI descriptions for %d images", len(image_tasks)
            )
            raw_descriptions = describer.describe_batch(image_tasks)
            # describe_batch uses absolute paths; the renderer keys off
            # the node.local_path which is stored relative to output_dir.
            descriptions = {
                os.path.relpath(full_path, output_dir): desc
                for full_path, desc in raw_descriptions.items()
            }
            descriptions_generated = sum(
                1
                for desc in descriptions.values()
                if desc != "Image description unavailable"
            )

    # --- 11. Build metadata --------------------------------------------
    metadata = PageMetadata(
        source_url=page_url,
        page_id=page_id,
        page_title=page_data.title,
        export_timestamp=datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        exporter_version=confluence_ai.__version__,
        space_key=page_data.space_key,
        labels=page_data.labels,
    )

    # --- 12. Render + write file ---------------------------------------
    rendered = renderer.render(nodes, metadata, descriptions)
    sanitized = _sanitize_title(page_data.title)
    extension = "json" if output_format == "json" else "md"
    output_filename = f"{sanitized}.{extension}"
    output_path = os.path.join(output_dir, output_filename)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)
    logger.info("Wrote output to %s", output_path)

    return ExportResult(
        markdown_path=output_path,
        images_downloaded=images_downloaded,
        descriptions_generated=descriptions_generated,
        warnings=warnings_list,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sanitize_title(title: str) -> str:
    """Sanitize a page title for use as a filename.

    Replaces spaces with underscores and removes special characters,
    keeping only alphanumeric characters, underscores, and hyphens.
    Falls back to ``"untitled"`` when the result would be empty.
    """
    sanitized = title.replace(" ", "_")
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "", sanitized)
    return sanitized or "untitled"


def _collect_image_tasks(
    nodes: list[ContentNode],
    page_title: str,
    output_dir: str,
) -> list[tuple[str, ImageContext]]:
    """Collect ``(image_path, context)`` tuples for images that need descriptions.

    Only includes nodes with a non-None ``local_path`` (successfully
    downloaded images). The returned paths are absolute (prefixed with
    ``output_dir``) so the describer can read the files regardless of the
    current working directory.
    """
    tasks: list[tuple[str, ImageContext]] = []
    for node in nodes:
        if isinstance(node, ImageNode) and node.local_path is not None:
            context = ImageContext(
                is_gliffy=False,
                alt_text=node.alt_text,
                page_title=page_title,
                filename=node.filename or "",
            )
            full_path = os.path.join(output_dir, node.local_path)
            tasks.append((full_path, context))
        elif isinstance(node, GliffyNode) and node.local_path is not None:
            context = ImageContext(
                is_gliffy=True,
                alt_text=node.alt_text,
                page_title=page_title,
                filename=node.name,
            )
            full_path = os.path.join(output_dir, node.local_path)
            tasks.append((full_path, context))
    return tasks


def _is_account_id(text: str) -> bool:
    """Check if a string looks like a Confluence Cloud account ID."""
    return bool(_ACCOUNT_ID_RE.match(text))


def _collect_account_ids(nodes: list[ContentNode]) -> set[str]:
    """Scan all nodes for Confluence account IDs that need resolution.

    Account IDs appear as link text or href when user mentions have no
    display name in the storage format.
    """
    ids: set[str] = set()

    def _scan(node: object) -> None:
        if isinstance(node, LinkNode):
            if _is_account_id(node.text):
                ids.add(node.text)
            if _is_account_id(node.href):
                ids.add(node.href)
            return

        if isinstance(node, TextNode):
            if _is_account_id(node.text.strip()):
                ids.add(node.text.strip())
            return

        if isinstance(node, ParagraphNode):
            for child in node.children:
                _scan(child)
        elif isinstance(node, ListNode):
            for item in node.items:
                for child in item.children:
                    _scan(child)
        elif isinstance(node, BlockquoteMacroNode):
            for child in node.children:
                _scan(child)
        elif isinstance(node, TableNode):
            for header in node.headers:
                if _is_account_id(header):
                    ids.add(header)
            for row in node.rows:
                for cell in row:
                    for word in cell.split():
                        cleaned = word.strip("; ,")
                        if _is_account_id(cleaned):
                            ids.add(cleaned)

    for node in nodes:
        _scan(node)

    return ids


def _replace_account_ids(
    nodes: list[ContentNode], user_map: dict[str, str]
) -> None:
    """Replace account IDs with display names in all nodes (in-place).

    Mutates ``LinkNode.text``, ``LinkNode.href``, ``TextNode.text``, and
    table cell strings where account IDs are found.
    """

    def _replace_in_node(node: object) -> None:
        if isinstance(node, LinkNode):
            if node.text in user_map:
                node.text = user_map[node.text]
            if node.href in user_map:
                node.href = user_map[node.href]
            return

        if isinstance(node, TextNode):
            stripped = node.text.strip()
            if stripped in user_map:
                node.text = node.text.replace(
                    stripped, user_map[stripped]
                )
            return

        if isinstance(node, ParagraphNode):
            for child in node.children:
                _replace_in_node(child)
        elif isinstance(node, ListNode):
            for item in node.items:
                for child in item.children:
                    _replace_in_node(child)
        elif isinstance(node, BlockquoteMacroNode):
            for child in node.children:
                _replace_in_node(child)
        elif isinstance(node, TableNode):
            node.headers = [
                _replace_ids_in_text(h, user_map) for h in node.headers
            ]
            node.rows = [
                [_replace_ids_in_text(cell, user_map) for cell in row]
                for row in node.rows
            ]

    for node in nodes:
        _replace_in_node(node)


def _replace_ids_in_text(
    text: str, user_map: dict[str, str]
) -> str:
    """Replace any account IDs found in a text string with display names."""
    for aid, name in user_map.items():
        if aid in text:
            text = text.replace(aid, name)
    return text
