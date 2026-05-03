"""CLI entry point for the Confluence Page Exporter.

Provides the ``confluence-export`` Click command that wires together the
full export pipeline: URL parsing → Confluence retrieval → XHTML parsing →
asset downloading → AI image description → Markdown rendering → file output.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.4, 9.1, 9.2, 9.3, 9.4, 9.5
"""

from __future__ import annotations

import datetime
import logging
import os
import re
import sys

import click

import confluence_exporter
from confluence_exporter.client import ConfluenceClient
from confluence_exporter.describer import ImageDescriber
from confluence_exporter.downloader import AssetDownloader
from confluence_exporter.exceptions import (
    AuthenticationError,
    ConfluenceConnectionError,
    ExporterError,
    InvalidURLError,
    PageNotFoundError,
    ParseError,
)
from confluence_exporter.models import (
    BlockquoteMacroNode,
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
from confluence_exporter.parser import StorageFormatParser
from confluence_exporter.providers import create_describer
from confluence_exporter.renderer import MarkdownRenderer
from confluence_exporter.url_parser import URLParser

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def sanitize_title(title: str) -> str:
    """Sanitize a page title for use as a filename.

    Replaces spaces with underscores and removes special characters,
    keeping only alphanumeric characters, underscores, and hyphens.

    Args:
        title: Raw Confluence page title.

    Returns:
        Sanitized string safe for use as a filename stem.
    """
    # Replace spaces with underscores
    sanitized = title.replace(" ", "_")
    # Remove special characters — keep alphanumeric, underscores, hyphens
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "", sanitized)
    return sanitized or "untitled"


def format_summary(result: ExportResult) -> str:
    """Format an ExportResult as a human-readable summary string.

    Args:
        result: The export result to format.

    Returns:
        Multi-line summary string suitable for printing to stdout.
    """
    lines: list[str] = [
        "Export complete:",
        f"  Markdown file: {result.markdown_path}",
        f"  Images downloaded: {result.images_downloaded}",
        f"  Descriptions generated: {result.descriptions_generated}",
    ]
    if result.warnings:
        lines.append(f"  Warnings ({len(result.warnings)}):")
        for warning in result.warnings:
            lines.append(f"    - {warning}")
    return "\n".join(lines)


def _configure_logging(verbose: bool) -> None:
    """Configure logging to stderr with appropriate level.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    # Configure the root logger for the confluence_exporter package
    pkg_logger = logging.getLogger("confluence_exporter")
    pkg_logger.setLevel(level)
    # Remove existing handlers to avoid duplicates on repeated calls
    pkg_logger.handlers.clear()
    pkg_logger.addHandler(handler)


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


@click.command("confluence-export")
@click.argument("page_url")
@click.argument("output_dir")
@click.option(
    "--email",
    envvar="CONFLUENCE_EMAIL",
    default=None,
    help="Confluence account email (env: CONFLUENCE_EMAIL).",
)
@click.option(
    "--api-token",
    envvar="CONFLUENCE_API_TOKEN",
    default=None,
    help="Confluence API token (env: CONFLUENCE_API_TOKEN).",
)
@click.option(
    "--confluence-url",
    default=None,
    help="Override the Confluence base URL extracted from the page URL.",
)
@click.option(
    "--ai-provider",
    envvar="CONFLUENCE_EXPORT_AI_PROVIDER",
    default=None,
    help="AI provider for image descriptions: anthropic, openai, or bedrock (env: CONFLUENCE_EXPORT_AI_PROVIDER).",
)
@click.option(
    "--ai-model",
    envvar="CONFLUENCE_EXPORT_AI_MODEL",
    default=None,
    help="AI model name (env: CONFLUENCE_EXPORT_AI_MODEL).",
)
@click.option(
    "--ai-api-key",
    default=None,
    help="AI provider API key. Falls back to ANTHROPIC_API_KEY or OPENAI_API_KEY env vars.",
)
@click.option(
    "--region",
    envvar="AWS_DEFAULT_REGION",
    default=None,
    help="AWS region for Bedrock provider (default: us-east-1). Env: AWS_DEFAULT_REGION.",
)
@click.option(
    "--no-ai",
    is_flag=True,
    default=False,
    help="Skip AI image description generation.",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Enable DEBUG-level logging.",
)
def main(
    page_url: str,
    output_dir: str,
    email: str | None,
    api_token: str | None,
    confluence_url: str | None,
    ai_provider: str | None,
    ai_model: str | None,
    ai_api_key: str | None,
    region: str | None,
    no_ai: bool,
    verbose: bool,
) -> None:
    """Export a Confluence Cloud page to Markdown with images and AI descriptions.

    PAGE_URL is the full Confluence Cloud page URL.

    OUTPUT_DIR is the directory where the Markdown file and images will be written.
    """
    _configure_logging(verbose)
    warnings_list: list[str] = []

    try:
        # --- 1. Parse URL ---
        logger.info("Parsing page URL: %s", page_url)
        url_parser = URLParser()
        parsed = url_parser.parse(page_url)
        base_url = confluence_url or parsed.base_url
        page_id = parsed.page_id
        logger.debug("Base URL: %s, Page ID: %s", base_url, page_id)

        # --- 2. Validate credentials ---
        if not email:
            raise click.UsageError(
                "Confluence email is required. "
                "Use --email or set CONFLUENCE_EMAIL."
            )
        if not api_token:
            raise click.UsageError(
                "Confluence API token is required. "
                "Use --api-token or set CONFLUENCE_API_TOKEN."
            )

        # --- 3. Connect to Confluence ---
        logger.info("Connecting to Confluence at %s", base_url)
        client = ConfluenceClient(base_url=base_url, email=email, api_token=api_token)

        # --- 4. Retrieve page and attachments ---
        logger.info("Retrieving page %s", page_id)
        page_data = client.get_page(page_id)
        logger.info("Page title: %s", page_data.title)

        logger.info("Retrieving attachments for page %s", page_id)
        attachments = client.get_attachments(page_id)
        logger.info("Found %d attachments", len(attachments))

        # --- 5. Parse storage format ---
        logger.info("Parsing storage format XHTML")
        parser = StorageFormatParser()
        nodes = parser.parse(page_data.storage_format)
        logger.info("Parsed %d content nodes", len(nodes))

        # --- 5b. Resolve user mentions ---
        account_ids = _collect_account_ids(nodes)
        if account_ids:
            logger.info("Resolving %d user mention(s)", len(account_ids))
            user_map = client.resolve_user_ids(account_ids)
            if user_map:
                _replace_account_ids(nodes, user_map)
                logger.info("Resolved %d user name(s)", len(user_map))

        # --- 6. Create output directories ---
        os.makedirs(output_dir, exist_ok=True)
        images_dir = os.path.join(output_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        logger.debug("Output directory: %s", output_dir)

        # --- 7. Download assets ---
        logger.info("Downloading assets")
        downloader = AssetDownloader(client=client, output_dir=output_dir)
        nodes = downloader.download_assets(nodes, attachments)

        # Count downloaded images
        images_downloaded = sum(
            1
            for n in nodes
            if isinstance(n, (ImageNode, GliffyNode)) and n.local_path is not None
        )
        logger.info("Downloaded %d images", images_downloaded)

        # --- 8. Generate AI descriptions (unless --no-ai) ---
        descriptions: dict[str, str] = {}
        descriptions_generated = 0

        if not no_ai:
            describer = _create_describer(ai_provider, ai_model, ai_api_key, region)
            if describer is not None:
                image_tasks = _collect_image_tasks(nodes, page_data.title, output_dir)
                if image_tasks:
                    logger.info(
                        "Generating AI descriptions for %d images",
                        len(image_tasks),
                    )
                    raw_descriptions = describer.describe_batch(image_tasks)
                    # Remap keys: describe_batch uses full paths (output_dir/images/...)
                    # but the renderer looks up by node.local_path (images/...)
                    descriptions = {}
                    for full_path, desc in raw_descriptions.items():
                        # Strip the output_dir prefix to get the relative path
                        rel_path = os.path.relpath(full_path, output_dir)
                        descriptions[rel_path] = desc
                    descriptions_generated = sum(
                        1
                        for desc in descriptions.values()
                        if desc != "Image description unavailable"
                    )
                    logger.info(
                        "Generated %d descriptions", descriptions_generated
                    )
            else:
                msg = "AI provider not configured — skipping image descriptions."
                logger.warning(msg)
                warnings_list.append(msg)
        else:
            logger.info("AI descriptions disabled (--no-ai)")

        # --- 9. Build metadata ---
        metadata = PageMetadata(
            source_url=page_url,
            page_id=page_id,
            page_title=page_data.title,
            export_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            exporter_version=confluence_exporter.__version__,
            space_key=page_data.space_key,
            labels=page_data.labels,
        )

        # --- 10. Render Markdown ---
        logger.info("Rendering Markdown")
        renderer = MarkdownRenderer()
        markdown = renderer.render(nodes, metadata, descriptions)

        # --- 11. Write output file ---
        sanitized = sanitize_title(page_data.title)
        md_filename = f"{sanitized}.md"
        md_path = os.path.join(output_dir, md_filename)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown)
        logger.info("Wrote Markdown to %s", md_path)

        # --- 12. Print summary ---
        result = ExportResult(
            markdown_path=md_path,
            images_downloaded=images_downloaded,
            descriptions_generated=descriptions_generated,
            warnings=warnings_list,
        )
        click.echo(format_summary(result))

    except InvalidURLError as exc:
        logger.error("Invalid URL: %s", exc)
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except AuthenticationError as exc:
        logger.error("Authentication failed: %s", exc)
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except ConfluenceConnectionError as exc:
        logger.error("Connection failed: %s", exc)
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except PageNotFoundError as exc:
        logger.error("Page not found: %s", exc)
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except ParseError as exc:
        logger.error("Parse error: %s", exc)
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except click.UsageError:
        raise  # Let Click handle usage errors
    except ExporterError as exc:
        logger.error("Export failed: %s", exc)
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except OSError as exc:
        logger.error("Filesystem error: %s", exc)
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _create_describer(
    ai_provider: str | None,
    ai_model: str | None,
    ai_api_key: str | None,
    region: str | None = None,
) -> ImageDescriber | None:
    """Create an image describer from CLI options, or return None.

    Resolves the API key from the explicit ``--ai-api-key`` option first,
    then falls back to provider-specific environment variables
    (``ANTHROPIC_API_KEY`` or ``OPENAI_API_KEY``). For Bedrock, no API
    key is needed — authentication uses the AWS credential chain.

    Returns:
        An ``ImageDescriber`` instance, or ``None`` if the provider is
        not configured.
    """
    if not ai_provider:
        return None

    # Resolve API key: explicit > provider-specific env var
    api_key = ai_api_key
    if not api_key:
        env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
        env_var = env_map.get(ai_provider)
        if env_var:
            api_key = os.environ.get(env_var, "")

    # Default model names per provider
    model = ai_model
    if not model:
        model_defaults = {
            "anthropic": "claude-sonnet-4-20250514",
            "openai": "gpt-4o",
            "bedrock": "us.anthropic.claude-sonnet-4-20250514-v1:0",
        }
        model = model_defaults.get(ai_provider, ai_provider)

    config = ImageDescriberConfig(
        provider=ai_provider,
        model=model,
        api_key=api_key or "",
        region=region or "",
    )
    return create_describer(config)


def _collect_image_tasks(
    nodes: list,
    page_title: str,
    output_dir: str,
) -> list[tuple[str, ImageContext]]:
    """Collect (image_path, context) tuples for images that need descriptions.

    Only includes nodes with a non-None ``local_path`` (successfully
    downloaded images). The returned paths are absolute (prefixed with
    ``output_dir``) so the describer can read the files regardless of
    the current working directory.
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


# Account ID pattern: 24-character hex string (Confluence Cloud user IDs)
_ACCOUNT_ID_RE = re.compile(r"^[0-9a-f]{24}$")


def _is_account_id(text: str) -> bool:
    """Check if a string looks like a Confluence Cloud account ID."""
    return bool(_ACCOUNT_ID_RE.match(text))


def _collect_account_ids(nodes: list) -> set[str]:
    """Scan all nodes for Confluence account IDs that need resolution.

    Account IDs appear as link text or href when user mentions have no
    display name in the storage format.
    """
    ids: set[str] = set()

    def _scan(node: object) -> None:
        # Check LinkNode text and href
        if isinstance(node, LinkNode):
            if _is_account_id(node.text):
                ids.add(node.text)
            if _is_account_id(node.href):
                ids.add(node.href)
            return

        # Check TextNode text
        if isinstance(node, TextNode):
            if _is_account_id(node.text.strip()):
                ids.add(node.text.strip())
            return

        # Recurse into container nodes
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
                    # Cells may contain account IDs as plain text
                    for word in cell.split():
                        cleaned = word.strip("; ,")
                        if _is_account_id(cleaned):
                            ids.add(cleaned)

    for node in nodes:
        _scan(node)

    return ids


def _replace_account_ids(nodes: list, user_map: dict[str, str]) -> None:
    """Replace account IDs with display names in all nodes (in-place).

    Mutates LinkNode.text, LinkNode.href, TextNode.text, and table cell
    strings where account IDs are found.
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
                node.text = node.text.replace(stripped, user_map[stripped])
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


def _replace_ids_in_text(text: str, user_map: dict[str, str]) -> str:
    """Replace any account IDs found in a text string with display names."""
    for aid, name in user_map.items():
        if aid in text:
            text = text.replace(aid, name)
    return text
