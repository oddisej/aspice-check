"""Single-command ASPICE analysis pipeline.

Provides the ``aspice-analyze`` CLI command that orchestrates the full
ASPICE gap analysis pipeline in one step: export a Confluence SDP page
to Markdown, evaluate it against the ASPICE knowledge base, and publish
the gap analysis report back to Confluence as a child page.

The command is an orchestration layer that composes existing functionality
from the ``confluence-exporter`` and ``aspice-eval`` packages into a
seamless, minimal-parameter workflow.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1–2.8, 3.1–3.4,
              4.1–4.7, 5.1–5.5, 6.1–6.4, 7.1–7.5, 8.1–8.6,
              9.1–9.5, 10.1–10.6, 11.1–11.5, 12.1–12.5, 13.1–13.4
"""

from __future__ import annotations

import datetime
import importlib.resources as pkg_resources
import logging
import os
import pathlib
import re
import sys
from dataclasses import dataclass, field
from typing import Any

import click

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class TokenTracker:
    """Accumulates AI token usage across pipeline stages."""

    export_input_tokens: int = 0
    export_output_tokens: int = 0
    export_calls: int = 0
    eval_input_tokens: int = 0
    eval_output_tokens: int = 0
    eval_calls: int = 0

    @property
    def total_input_tokens(self) -> int:
        return self.export_input_tokens + self.eval_input_tokens

    @property
    def total_output_tokens(self) -> int:
        return self.export_output_tokens + self.eval_output_tokens

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_calls(self) -> int:
        return self.export_calls + self.eval_calls


@dataclass
class ExportStageResult:
    """Result of the Export Stage."""

    markdown_path: str
    page_title: str
    page_id: str
    space_key: str
    images_downloaded: int
    descriptions_generated: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class EvaluateStageResult:
    """Result of the Evaluate Stage."""

    report_markdown: str
    report_html: str
    levels: dict[str, Any] = field(default_factory=dict)
    total_gaps: int = 0
    criteria_assessed: int = 0


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def _sanitize_title(title: str) -> str:
    """Sanitize a page title for use as a directory/file name.

    Replaces spaces with underscores and removes special characters,
    keeping only alphanumeric characters, underscores, and hyphens.

    Args:
        title: Raw Confluence page title.

    Returns:
        Sanitized string safe for use as a directory name.
        Returns ``"untitled"`` for empty or all-special-character titles.
    """
    sanitized = title.replace(" ", "_")
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "", sanitized)
    return sanitized or "untitled"


def _resolve_credentials(
    email: str | None,
    api_token: str | None,
) -> tuple[str, str]:
    """Resolve Confluence credentials from CLI options or environment.

    CLI options take precedence over environment variables.

    Args:
        email: Value from ``--email`` CLI option (may be ``None``).
        api_token: Value from ``--api-token`` CLI option (may be ``None``).

    Returns:
        Tuple of ``(email, api_token)``.

    Raises:
        click.UsageError: If either credential is missing from both
            CLI options and environment variables.
    """
    resolved_email = email or os.environ.get("CONFLUENCE_EMAIL")
    resolved_token = api_token or os.environ.get("CONFLUENCE_API_TOKEN")

    if not resolved_email:
        raise click.UsageError(
            "Confluence email is required. "
            "Use --email or set CONFLUENCE_EMAIL."
        )
    if not resolved_token:
        raise click.UsageError(
            "Confluence API token is required. "
            "Use --api-token or set CONFLUENCE_API_TOKEN."
        )
    return resolved_email, resolved_token


def _resolve_ai_config(
    provider: str | None,
    model: str | None,
    region: str | None,
) -> tuple[str, str, str]:
    """Resolve AI provider, model, and region with sensible defaults.

    Defaults:
        - provider: ``"bedrock"``
        - model: ``"us.anthropic.claude-sonnet-4-20250514-v1:0"``
        - region: from ``AWS_DEFAULT_REGION`` env var

    Args:
        provider: Value from ``--provider`` CLI option.
        model: Value from ``--model`` CLI option.
        region: Value from ``--region`` CLI option.

    Returns:
        Tuple of ``(provider, model, region)``.

    Raises:
        click.UsageError: If region is required (bedrock provider) but
            not available from CLI or environment.
    """
    resolved_provider = (
        provider
        or os.environ.get("ASPICE_EVAL_PROVIDER")
        or "bedrock"
    )

    _model_defaults: dict[str, str] = {
        "bedrock": "us.anthropic.claude-sonnet-4-20250514-v1:0",
        "openai": "gpt-4o",
        "anthropic": "claude-sonnet-4-20250514",
    }
    resolved_model = model or _model_defaults.get(resolved_provider, resolved_provider)

    resolved_region = region or os.environ.get("AWS_DEFAULT_REGION") or ""

    if resolved_provider == "bedrock" and not resolved_region:
        raise click.UsageError(
            "AWS region is required for Bedrock provider. "
            "Use --region or set AWS_DEFAULT_REGION."
        )

    return resolved_provider, resolved_model, resolved_region


def _format_summary(
    page_url: str | None,
    levels: dict[str, Any],
    total_gaps: int,
    output_dir: str,
    token_tracker: TokenTracker,
    provider: str,
    model: str,
    region: str,
) -> str:
    """Format the final pipeline summary for stdout.

    Args:
        page_url: URL of the published Confluence child page, or ``None``
            if publishing was skipped.
        levels: Mapping of process group code to ``CapabilityLevelResult``.
        total_gaps: Total number of gaps identified across all criteria.
        output_dir: Path to the local output directory.
        token_tracker: Accumulated token usage across stages.
        provider: AI provider name.
        model: AI model name.
        region: AWS region (when using Bedrock).

    Returns:
        Multi-line summary string.
    """
    lines: list[str] = ["Pipeline complete:"]

    if page_url:
        lines.append(f"  Published page: {page_url}")

    lines.append("  Capability levels:")
    for group in sorted(levels.keys()):
        result = levels[group]
        achieved = result.achieved_level
        target = result.target_level
        status = "meets target" if achieved >= target else "below target"
        lines.append(f"    {group}: level {achieved}/{target} ({status})")

    lines.append(f"  Total gaps: {total_gaps}")
    lines.append(f"  Output directory: {output_dir}")
    lines.append(
        f"  Token usage: {token_tracker.total_input_tokens:,} input + "
        f"{token_tracker.total_output_tokens:,} output = "
        f"{token_tracker.total_tokens:,} total "
        f"({token_tracker.total_calls} call{'s' if token_tracker.total_calls != 1 else ''})"
    )
    lines.append(f"  AI provider: {provider}, model: {model}")
    if region:
        lines.append(f"  Region: {region}")

    return "\n".join(lines)


def _configure_logging(verbose: bool, quiet: bool) -> None:
    """Configure logging to stderr with appropriate level.

    Args:
        verbose: If ``True``, set DEBUG level.
        quiet: If ``True``, suppress all progress messages (WARNING only).
            If both verbose and quiet are set, quiet wins.
    """
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    # Configure loggers for both packages
    for pkg_name in ("aspice_eval", "confluence_exporter"):
        pkg_logger = logging.getLogger(pkg_name)
        pkg_logger.setLevel(level)
        pkg_logger.handlers.clear()
        pkg_logger.addHandler(handler)


# ---------------------------------------------------------------------------
# Knowledge base path resolution
# ---------------------------------------------------------------------------


def _resolve_kb_path() -> str:
    """Resolve the knowledge base path from installed package data or filesystem.

    Tries multiple strategies to find the ``knowledge_base/`` directory:
    1. Relative to the ``aspice_eval`` package location (pip install from git
       places the source tree in site-packages).
    2. Relative to ``__file__`` (development mode with ``pip install -e``).
    3. Common parent directories up to 5 levels.

    Returns:
        Absolute path to the ``knowledge_base/`` directory.

    Raises:
        FileNotFoundError: If the KB directory cannot be found.
    """
    candidates: list[pathlib.Path] = []

    # Strategy 1: importlib.resources — find package root
    try:
        pkg_root = pathlib.Path(str(pkg_resources.files("aspice_eval")))
        # KB might be inside the package (if package-data works)
        candidates.append(pkg_root / "knowledge_base")
        # KB might be a sibling of src/ in the installed source tree
        candidates.append(pkg_root.parent.parent / "knowledge_base")
        # KB might be at the site-packages level (data_files install)
        candidates.append(pkg_root.parent / "knowledge_base")
    except (TypeError, FileNotFoundError, ModuleNotFoundError):
        pass

    # Strategy 2: relative to __file__ (development mode)
    # __file__ is at src/aspice_eval/analyze.py
    this_file = pathlib.Path(__file__).resolve()
    candidates.append(this_file.parent.parent.parent / "knowledge_base")
    # Also check if running from the repo root
    candidates.append(this_file.parent.parent.parent.parent / "aspice-eval" / "knowledge_base")

    # Strategy 3: current working directory
    candidates.append(pathlib.Path.cwd() / "knowledge_base")
    candidates.append(pathlib.Path.cwd() / "aspice-eval" / "knowledge_base")

    for candidate in candidates:
        if candidate.exists() and (candidate / "aspice").exists():
            return str(candidate)

    raise FileNotFoundError(
        "Knowledge base not found. Searched:\n"
        + "\n".join(f"  - {c}" for c in candidates)
    )


# ---------------------------------------------------------------------------
# Stage functions
# ---------------------------------------------------------------------------


def _run_export_stage(
    page_url: str,
    email: str,
    api_token: str,
    provider: str,
    model: str,
    region: str,
    output_dir: str,
    quiet: bool,
    token_tracker: TokenTracker,
) -> ExportStageResult:
    """Execute the Export Stage: retrieve Confluence page and produce Markdown.

    Replicates the pipeline logic from ``confluence-exporter``'s CLI
    ``main()`` function but as a callable function.

    Args:
        page_url: Full Confluence Cloud page URL.
        email: Confluence account email.
        api_token: Confluence API token.
        provider: AI provider name for image descriptions.
        model: AI model name.
        region: AWS region for Bedrock.
        output_dir: Local directory for output artifacts.
        quiet: Suppress progress messages.
        token_tracker: Token tracker to update with export counts.

    Returns:
        ExportStageResult with page metadata and artifact counts.
    """
    import confluence_exporter
    from confluence_exporter.client import ConfluenceClient
    from confluence_exporter.downloader import AssetDownloader
    from confluence_exporter.models import (
        GliffyNode,
        ImageContext,
        ImageDescriberConfig,
        ImageNode,
        PageMetadata,
    )
    from confluence_exporter.parser import StorageFormatParser
    from confluence_exporter.providers import create_describer
    from confluence_exporter.renderer import MarkdownRenderer
    from confluence_exporter.url_parser import URLParser

    warnings_list: list[str] = []

    if not quiet:
        click.echo("Exporting Confluence page...", err=True)

    # 1. Parse URL
    logger.info("Parsing page URL: %s", page_url)
    url_parser = URLParser()
    parsed = url_parser.parse(page_url)
    base_url = parsed.base_url
    page_id = parsed.page_id
    logger.debug("Base URL: %s, Page ID: %s", base_url, page_id)

    # 2. Connect to Confluence
    logger.info("Connecting to Confluence at %s", base_url)
    client = ConfluenceClient(base_url=base_url, email=email, api_token=api_token)

    # 3. Retrieve page and attachments
    logger.info("Retrieving page %s", page_id)
    page_data = client.get_page(page_id)
    logger.info("Page title: %s", page_data.title)

    logger.info("Retrieving attachments for page %s", page_id)
    attachments = client.get_attachments(page_id)
    logger.info("Found %d attachments", len(attachments))

    # 4. Parse storage format
    logger.info("Parsing storage format XHTML")
    parser = StorageFormatParser()
    nodes = parser.parse(page_data.storage_format)
    logger.info("Parsed %d content nodes", len(nodes))

    # 5. Resolve user mentions
    from confluence_exporter.cli import _collect_account_ids, _replace_account_ids

    account_ids = _collect_account_ids(nodes)
    if account_ids:
        logger.info("Resolving %d user mention(s)", len(account_ids))
        user_map = client.resolve_user_ids(account_ids)
        if user_map:
            _replace_account_ids(nodes, user_map)
            logger.info("Resolved %d user name(s)", len(user_map))

    # 6. Create output directories
    os.makedirs(output_dir, exist_ok=True)
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    # 7. Download assets
    logger.info("Downloading assets")
    downloader = AssetDownloader(client=client, output_dir=output_dir)
    nodes = downloader.download_assets(nodes, attachments)

    images_downloaded = sum(
        1
        for n in nodes
        if isinstance(n, (ImageNode, GliffyNode)) and n.local_path is not None
    )
    logger.info("Downloaded %d images", images_downloaded)

    # 8. Generate AI descriptions
    descriptions: dict[str, str] = {}
    descriptions_generated = 0

    describer_config = ImageDescriberConfig(
        provider=provider,
        model=model,
        api_key="",  # Bedrock uses AWS credential chain
        region=region,
    )
    try:
        describer = create_describer(describer_config)
    except Exception:
        describer = None
        msg = "AI provider not configured — skipping image descriptions."
        logger.warning(msg)
        warnings_list.append(msg)

    if describer is not None:
        image_tasks: list[tuple[str, ImageContext]] = []
        for node in nodes:
            if isinstance(node, ImageNode) and node.local_path is not None:
                context = ImageContext(
                    is_gliffy=False,
                    alt_text=node.alt_text,
                    page_title=page_data.title,
                    filename=node.filename or "",
                )
                full_path = os.path.join(output_dir, node.local_path)
                image_tasks.append((full_path, context))
            elif isinstance(node, GliffyNode) and node.local_path is not None:
                context = ImageContext(
                    is_gliffy=True,
                    alt_text=node.alt_text,
                    page_title=page_data.title,
                    filename=node.name,
                )
                full_path = os.path.join(output_dir, node.local_path)
                image_tasks.append((full_path, context))

        if image_tasks:
            if not quiet:
                click.echo(f"Generating AI descriptions for {len(image_tasks)} images...", err=True)
            logger.info("Generating AI descriptions for %d images", len(image_tasks))
            raw_descriptions = describer.describe_batch(image_tasks)
            for full_path, desc in raw_descriptions.items():
                rel_path = os.path.relpath(full_path, output_dir)
                descriptions[rel_path] = desc
            descriptions_generated = sum(
                1
                for desc in descriptions.values()
                if desc != "Image description unavailable"
            )
            logger.info("Generated %d descriptions", descriptions_generated)

    # Export token tracking: image describer doesn't currently track tokens
    # Set to 0 for now — can add tracking later
    token_tracker.export_input_tokens = 0
    token_tracker.export_output_tokens = 0
    token_tracker.export_calls = 0

    # 9. Build metadata
    metadata = PageMetadata(
        source_url=page_url,
        page_id=page_id,
        page_title=page_data.title,
        export_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        exporter_version=confluence_exporter.__version__,
        space_key=page_data.space_key,
        labels=page_data.labels,
    )

    # 10. Render Markdown
    logger.info("Rendering Markdown")
    renderer = MarkdownRenderer()
    markdown = renderer.render(nodes, metadata, descriptions)

    # 11. Write output file
    sanitized = _sanitize_title(page_data.title)
    md_filename = f"{sanitized}.md"
    md_path = os.path.join(output_dir, md_filename)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    logger.info("Wrote Markdown to %s", md_path)

    if not quiet:
        click.echo(
            f"Export complete: {images_downloaded} images, "
            f"{descriptions_generated} descriptions",
            err=True,
        )

    return ExportStageResult(
        markdown_path=md_path,
        page_title=page_data.title,
        page_id=page_id,
        space_key=page_data.space_key,
        images_downloaded=images_downloaded,
        descriptions_generated=descriptions_generated,
        warnings=warnings_list,
    )


def _run_evaluate_stage(
    markdown_path: str,
    target_level: int,
    groups: list[str],
    provider: str,
    model: str,
    region: str,
    token_tracker: TokenTracker,
    quiet: bool,
) -> EvaluateStageResult:
    """Execute the Evaluate Stage: run ASPICE gap analysis on exported Markdown.

    Replicates the pipeline logic from ``aspice-eval``'s ``evaluate``
    CLI command but as a callable function.

    Args:
        markdown_path: Path to the exported Markdown file.
        target_level: ASPICE capability level to evaluate against (1–5).
        groups: List of process group codes.
        provider: AI provider name.
        model: AI model name.
        region: AWS region for Bedrock.
        token_tracker: Token tracker to update with eval counts.
        quiet: Suppress progress messages.

    Returns:
        EvaluateStageResult with report content and metrics.
    """
    from aspice_eval.knowledge_base import KnowledgeBase
    from aspice_eval.level_calculator import CapabilityLevelCalculator
    from aspice_eval.models import EvaluationConfig, ModelConfig
    from aspice_eval.providers import create_evaluator
    from aspice_eval.report_generator import ReportGenerator
    from aspice_eval.sdp_ingester import SDPIngester

    if not quiet:
        click.echo("Evaluating against ASPICE criteria (this may take 2–3 minutes)...", err=True)

    # 1. Load KB
    kb_path = _resolve_kb_path()
    logger.info("Loading knowledge base from %s", kb_path)
    kb = KnowledgeBase(kb_path)
    kb.load("aspice")
    kb_metadata = kb.get_metadata()

    # 2. Ingest SDP
    logger.info("Ingesting exported Markdown: %s", markdown_path)
    ingester = SDPIngester()
    sdp_doc = ingester.ingest(markdown_path)

    # 3. Get criteria
    criteria = kb.get_criteria(groups, target_level)
    logger.info("Retrieved %d criteria for groups %s up to level %d",
                len(criteria), groups, target_level)

    # 4. Build config
    config = EvaluationConfig(
        sdp_path=markdown_path,
        target_capability_level=target_level,
        process_groups=groups,
        kb_path=kb_path,
    )

    # 5. Evaluate
    resolved_temperature = float(os.environ.get("ASPICE_EVAL_TEMPERATURE", "0.0"))
    resolved_max_tokens = int(os.environ.get("ASPICE_EVAL_MAX_TOKENS", "4096"))

    model_config = ModelConfig(
        provider=provider,
        model_name=model,
        temperature=resolved_temperature,
        max_tokens=resolved_max_tokens,
        region=region,
    )
    evaluator = create_evaluator(model_config)

    if not quiet:
        click.echo(
            f"Sending {len(criteria)} criteria to AI for evaluation...",
            err=True,
        )

    evaluation = evaluator.evaluate(sdp_doc, criteria, config)

    # 6. Update token tracker
    token_usage = evaluation.token_usage
    token_tracker.eval_input_tokens = token_usage.get("input_tokens", 0)
    token_tracker.eval_output_tokens = token_usage.get("output_tokens", 0)
    token_tracker.eval_calls = token_usage.get("num_batches", 0)

    # 7. Calculate capability levels
    calculator = CapabilityLevelCalculator(target_level)
    levels = calculator.calculate(evaluation.ratings, groups)

    # 8. Generate report (both formats)
    reporter = ReportGenerator()
    report_md = reporter.generate(
        evaluation, levels, config, kb_metadata, output_format="markdown",
    )
    report_html = reporter.generate(
        evaluation, levels, config, kb_metadata, output_format="html",
    )

    # Count gaps and criteria
    total_gaps = sum(len(r.gaps) for r in evaluation.ratings)
    criteria_assessed = len(evaluation.ratings)

    if not quiet:
        click.echo(
            f"Evaluation complete: {criteria_assessed} criteria assessed, "
            f"{total_gaps} gaps identified",
            err=True,
        )

    return EvaluateStageResult(
        report_markdown=report_md,
        report_html=report_html,
        levels=levels,
        total_gaps=total_gaps,
        criteria_assessed=criteria_assessed,
    )


def _run_publish_stage(
    report_html: str,
    page_id: str,
    space_key: str,
    report_title: str,
    base_url: str,
    email: str,
    api_token: str,
    quiet: bool,
) -> str:
    """Execute the Publish Stage: create/update a Confluence child page.

    Converts the report HTML to Confluence storage format and creates
    or updates a child page under the source SDP page.

    Args:
        report_html: HTML report content.
        page_id: Source SDP page ID (parent).
        space_key: Confluence space key.
        report_title: Title for the child page.
        base_url: Confluence base URL.
        email: Confluence account email.
        api_token: Confluence API token.
        quiet: Suppress progress messages.

    Returns:
        URL of the created/updated child page.
    """
    from atlassian import Confluence

    if not quiet:
        click.echo("Publishing report to Confluence...", err=True)

    # Strip emoji that the Fabric editor may reject
    sanitized_html = report_html
    sanitized_html = sanitized_html.replace("⚠️", "[!]")
    sanitized_html = sanitized_html.replace("⚠", "[!]")
    sanitized_html = sanitized_html.replace("✅", "[OK]")
    sanitized_html = sanitized_html.replace("❌", "[X]")
    sanitized_html = sanitized_html.replace("💡", "[TIP]")
    sanitized_html = sanitized_html.replace("ℹ️", "[INFO]")
    sanitized_html = sanitized_html.replace("ℹ", "[INFO]")
    sanitized_html = re.sub(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        r"\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF]",
        "",
        sanitized_html,
    )

    confluence = Confluence(
        url=base_url,
        username=email,
        password=api_token,
        cloud=True,
    )

    # Convert HTML to Confluence storage format
    storage_content = _convert_to_storage(confluence, sanitized_html)

    # Check for existing child page with same title
    try:
        existing = confluence.get_page_by_title(space_key, report_title)
    except Exception:
        existing = None  # Page doesn't exist yet — that's fine

    if existing:
        # Update existing page
        existing_id = existing["id"]
        confluence.update_page(
            page_id=existing_id,
            title=report_title,
            body=storage_content,
            type="page",
            representation="storage",
        )
        page_url = f"{base_url}/spaces/{space_key}/pages/{existing_id}"
        logger.info("Updated existing page: %s", page_url)
    else:
        # Create new child page
        try:
            result = confluence.create_page(
                space=space_key,
                title=report_title,
                body=storage_content,
                parent_id=page_id,
                type="page",
                representation="storage",
            )
        except Exception as exc:
            # atlassian-python-api wraps many errors as "permission" errors
            # Try to give a more helpful message
            error_msg = str(exc)
            if "permission" in error_msg.lower():
                raise RuntimeError(
                    f"Failed to create page '{report_title}' as child of page {page_id} "
                    f"in space {space_key}. This may be a permissions issue, or the "
                    f"page title may contain special characters. "
                    f"Original error: {error_msg}"
                ) from exc
            raise
        new_id = result.get("id", result) if isinstance(result, dict) else "unknown"
        page_url = f"{base_url}/spaces/{space_key}/pages/{new_id}"
        logger.info("Created new page: %s", page_url)

    if not quiet:
        click.echo(f"Published: {page_url}", err=True)

    return page_url


def _convert_to_storage(confluence: Any, html_content: str) -> str:
    """Convert HTML to Confluence storage format using the conversion API.

    Falls back to raw HTML if the conversion endpoint fails.
    """
    session = confluence._session
    base = confluence.url.rstrip("/")
    url = f"{base}/rest/api/contentbody/convert/storage"

    response = session.post(
        url,
        json={
            "value": html_content,
            "representation": "editor",
        },
        headers={"Content-Type": "application/json"},
    )

    if response.status_code == 200:
        data = response.json()
        converted = data.get("value", html_content)
        logger.info("Converted HTML to storage format (%d chars)", len(converted))
        return converted

    # Fallback to raw HTML
    logger.warning(
        "Content conversion failed (HTTP %d), using raw HTML",
        response.status_code,
    )
    return html_content


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


@click.command("aspice-analyze")
@click.argument("page_url")
@click.option(
    "--target-level",
    required=True,
    type=int,
    help="ASPICE capability level to evaluate against (1–5).",
)
@click.option(
    "--groups",
    required=True,
    type=str,
    help="Comma-separated process group codes (e.g., SWE,MAN,SUP).",
)
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
    "--provider",
    envvar="ASPICE_EVAL_PROVIDER",
    default=None,
    help="AI provider: bedrock, openai, anthropic (env: ASPICE_EVAL_PROVIDER). Default: bedrock.",
)
@click.option(
    "--model",
    default=None,
    help="AI model name. Default: us.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock).",
)
@click.option(
    "--region",
    envvar="AWS_DEFAULT_REGION",
    default=None,
    help="AWS region for Bedrock provider (env: AWS_DEFAULT_REGION).",
)
@click.option(
    "--report-title",
    default=None,
    help='Report page title. Default: "ASPICE Gap Analysis L{N} - {page title}".',
)
@click.option(
    "--output-dir",
    default=None,
    type=click.Path(),
    help="Output directory for intermediate artifacts. Default: ./aspice-output/{title}/.",
)
@click.option(
    "--output",
    default=None,
    type=click.Path(),
    help="Local file path for saving the report.",
)
@click.option(
    "--output-format",
    default="markdown",
    type=click.Choice(["markdown", "html"], case_sensitive=False),
    show_default=True,
    help="Report output format for local file.",
)
@click.option(
    "--no-publish",
    is_flag=True,
    default=False,
    help="Skip publishing to Confluence.",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Enable DEBUG-level logging.",
)
@click.option(
    "--quiet",
    is_flag=True,
    default=False,
    help="Suppress progress messages.",
)
def analyze(
    page_url: str,
    target_level: int,
    groups: str,
    email: str | None,
    api_token: str | None,
    provider: str | None,
    model: str | None,
    region: str | None,
    report_title: str | None,
    output_dir: str | None,
    output: str | None,
    output_format: str,
    no_publish: bool,
    verbose: bool,
    quiet: bool,
) -> None:
    """Run a full ASPICE gap analysis pipeline on a Confluence SDP page.

    PAGE_URL is the full Confluence Cloud page URL of the SDP to analyze.
    """
    _configure_logging(verbose, quiet)
    token_tracker = TokenTracker()

    try:
        # --- Parameter validation ---
        resolved_email, resolved_token = _resolve_credentials(email, api_token)
        resolved_provider, resolved_model, resolved_region = _resolve_ai_config(
            provider, model, region,
        )

        process_groups = [g.strip() for g in groups.split(",") if g.strip()]

        # Validate target level
        if target_level < 1 or target_level > 5:
            from aspice_eval.exceptions import InvalidConfigError

            raise InvalidConfigError(
                f"Target level {target_level} is out of range. Must be 1–5.",
                parameter="target_level",
                actual_value=target_level,
                expected_values=[1, 2, 3, 4, 5],
            )

        # Validate process groups against KB metadata
        try:
            kb_path = _resolve_kb_path()
            import yaml as _yaml

            metadata_path = pathlib.Path(kb_path) / "aspice" / "_metadata.yaml"
            if metadata_path.exists():
                with open(metadata_path) as fh:
                    metadata = _yaml.safe_load(fh)
                valid_codes = {
                    pg.get("code", "")
                    for pg in metadata.get("process_groups", [])
                }
                unknown = [g for g in process_groups if g not in valid_codes]
                if unknown:
                    from aspice_eval.exceptions import InvalidConfigError

                    raise InvalidConfigError(
                        f"Unknown process group(s): {', '.join(unknown)}. "
                        f"Valid groups: {', '.join(sorted(valid_codes))}.",
                        parameter="process_groups",
                        actual_value=unknown,
                        expected_values=sorted(valid_codes),
                    )
        except FileNotFoundError:
            pass  # KB validation will catch this later

    except click.UsageError:
        raise  # Let Click handle usage errors
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # --- Export Stage ---
    export_result: ExportStageResult | None = None
    try:
        # Resolve output directory
        # We need to do a preliminary URL parse to get the page title for the
        # default output dir. But we'll get the real title from the export stage.
        if output_dir is None:
            # Use a temporary name; we'll know the real title after export
            output_dir = os.path.join("aspice-output", "pending")

        export_result = _run_export_stage(
            page_url=page_url,
            email=resolved_email,
            api_token=resolved_token,
            provider=resolved_provider,
            model=resolved_model,
            region=resolved_region,
            output_dir=output_dir if output_dir != os.path.join("aspice-output", "pending") else output_dir,
            quiet=quiet,
            token_tracker=token_tracker,
        )

        # If we used a temporary output dir, rename to the real one
        if output_dir == os.path.join("aspice-output", "pending"):
            real_dir = os.path.join(
                "aspice-output", _sanitize_title(export_result.page_title),
            )
            if real_dir != output_dir and not os.path.exists(real_dir):
                os.rename(output_dir, real_dir)
                output_dir = real_dir
                # Update markdown path
                export_result = ExportStageResult(
                    markdown_path=os.path.join(
                        real_dir,
                        os.path.basename(export_result.markdown_path),
                    ),
                    page_title=export_result.page_title,
                    page_id=export_result.page_id,
                    space_key=export_result.space_key,
                    images_downloaded=export_result.images_downloaded,
                    descriptions_generated=export_result.descriptions_generated,
                    warnings=export_result.warnings,
                )
            else:
                output_dir = real_dir if os.path.exists(real_dir) else output_dir

    except click.UsageError:
        raise
    except Exception as exc:
        _handle_stage_error("Export", exc)

    assert export_result is not None

    # --- Evaluate Stage ---
    eval_result: EvaluateStageResult | None = None
    try:
        eval_result = _run_evaluate_stage(
            markdown_path=export_result.markdown_path,
            target_level=target_level,
            groups=process_groups,
            provider=resolved_provider,
            model=resolved_model,
            region=resolved_region,
            token_tracker=token_tracker,
            quiet=quiet,
        )
    except Exception as exc:
        _handle_stage_error("Evaluation", exc)

    assert eval_result is not None

    # --- Local output ---
    if output:
        report_content = (
            eval_result.report_html
            if output_format == "html"
            else eval_result.report_markdown
        )
        pathlib.Path(output).write_text(report_content, encoding="utf-8")
        if not quiet:
            click.echo(f"Report written to {output}", err=True)

    # Also write report to output directory
    report_path = os.path.join(output_dir, f"report_L{target_level}.md")
    pathlib.Path(report_path).write_text(
        eval_result.report_markdown, encoding="utf-8",
    )

    # --- Publish Stage ---
    page_url_result: str | None = None
    if not no_publish:
        try:
            # Resolve report title
            resolved_title = report_title or f"ASPICE Gap Analysis L{target_level} - {export_result.page_title}"

            # Get base URL from the page URL
            from confluence_exporter.url_parser import URLParser

            parsed_url = URLParser().parse(page_url)

            page_url_result = _run_publish_stage(
                report_html=eval_result.report_html,
                page_id=export_result.page_id,
                space_key=export_result.space_key,
                report_title=resolved_title,
                base_url=parsed_url.base_url,
                email=resolved_email,
                api_token=resolved_token,
                quiet=quiet,
            )
        except Exception as exc:
            _handle_stage_error("Publishing", exc)
    else:
        # --no-publish: if no --output, print report to stdout
        if not output:
            report_content = (
                eval_result.report_html
                if output_format == "html"
                else eval_result.report_markdown
            )
            click.echo(report_content)

    # --- Summary ---
    summary = _format_summary(
        page_url=page_url_result,
        levels=eval_result.levels,
        total_gaps=eval_result.total_gaps,
        output_dir=output_dir,
        token_tracker=token_tracker,
        provider=resolved_provider,
        model=resolved_model,
        region=resolved_region,
    )
    click.echo(summary)


def _handle_stage_error(stage: str, exc: Exception) -> None:
    """Map a stage exception to a user-friendly error message and exit.

    Args:
        stage: Stage name (``"Export"``, ``"Evaluation"``, ``"Publishing"``).
        exc: The caught exception.
    """
    # Determine exit code by stage
    exit_codes = {
        "Export": 2,
        "Evaluation": 3,
        "Publishing": 4,
    }
    exit_code = exit_codes.get(stage, 1)

    # Check for AWS credential errors
    try:
        import botocore.exceptions  # type: ignore[import-untyped]

        if isinstance(exc, botocore.exceptions.ClientError):
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in (
                "ExpiredTokenException",
                "UnrecognizedClientException",
                "InvalidIdentityToken",
            ):
                click.echo(
                    f"{stage} failed: AWS session expired. "
                    "Run 'aws sso login' or refresh your credentials.",
                    err=True,
                )
                sys.exit(exit_code)
    except ImportError:
        pass

    # Check for HTTP errors (Publish Stage)
    try:
        from requests.exceptions import HTTPError

        if isinstance(exc, HTTPError):
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 403:
                click.echo(
                    f"{stage} failed: Permission denied. "
                    "Check that your account has create/edit permissions.",
                    err=True,
                )
            else:
                click.echo(
                    f"{stage} failed: Confluence API error (HTTP {status}).",
                    err=True,
                )
            sys.exit(exit_code)
    except ImportError:
        pass

    # Check for connection errors
    try:
        from requests.exceptions import ConnectionError as ReqConnectionError

        if isinstance(exc, (ReqConnectionError, ConnectionError)):
            click.echo(
                f"{stage} failed: Could not connect to the service.",
                err=True,
            )
            sys.exit(exit_code)
    except ImportError:
        pass

    # Generic error message with stage identification
    click.echo(f"{stage} failed: {exc}", err=True)
    sys.exit(exit_code)
