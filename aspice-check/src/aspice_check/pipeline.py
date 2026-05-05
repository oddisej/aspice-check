"""Pipeline CLI for aspice-check — orchestrates export → evaluate → publish.

Provides the ``aspice-analyze`` CLI command that composes
``confluence_ai.export_page()``, ``aspice_eval.evaluate_sdp()``, and
``confluence_ai.publish_page()`` into a single pipeline.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 17.1, 17.2, 17.3, 17.4
"""

from __future__ import annotations

import logging
import os
import sys

import click

import aspice_eval
import confluence_ai

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_ai_config(
    provider: str | None,
    model: str | None,
    region: str | None,
) -> tuple[str, str, str]:
    """Resolve AI provider, model, and region with sensible defaults."""
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


def _resolve_credentials(
    email: str | None,
    api_token: str | None,
) -> tuple[str, str]:
    """Resolve Confluence credentials from CLI options or environment."""
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


def _handle_stage_error(stage: str, exc: Exception) -> None:
    """Translate exceptions into stage-labelled CLI error output and exit.

    Identifies which stage (Export, Evaluate, Publish) raised the error,
    shows the error, and provides a resolution suggestion.
    No custom exception classes are defined in aspice_check.

    Requirements: 17.6
    """
    exit_codes = {
        "Export": 2,
        "Evaluate": 3,
        "Publish": 4,
    }
    exit_code = exit_codes.get(stage, 1)

    # Provide resolution suggestions based on exception type
    suggestion = ""

    if isinstance(exc, confluence_ai.AuthenticationError):
        suggestion = " Suggestion: check --email and --api-token values."
    elif isinstance(exc, confluence_ai.InvalidURLError):
        suggestion = " Suggestion: verify the page URL is a valid Confluence Cloud URL."
    elif isinstance(exc, confluence_ai.ConfluenceConnectionError):
        suggestion = " Suggestion: check network connection and Confluence base URL."
    elif isinstance(exc, confluence_ai.PageNotFoundError):
        suggestion = " Suggestion: verify the page exists and you have access."
    elif isinstance(exc, aspice_eval.InvalidConfigError):
        suggestion = " Suggestion: check --target-level (1–5) and --groups values."
    elif isinstance(exc, aspice_eval.AIModelError):
        suggestion = " Suggestion: check AI provider credentials and model availability."
    elif isinstance(exc, FileNotFoundError):
        suggestion = " Suggestion: verify the file path exists."

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
                suggestion = " Suggestion: run 'aws sso login' or refresh credentials."
    except ImportError:
        pass

    click.echo(f"[{stage}] Error: {exc}{suggestion}", err=True)
    sys.exit(exit_code)


def _generate_html_report(evaluation: aspice_eval.EvaluationResult) -> str:
    """Generate a simple HTML report from evaluation results.

    Uses only top-level aspice_eval API objects.
    """
    total_gaps = sum(len(r.gaps) for r in evaluation.ratings)
    criteria_count = len(evaluation.ratings)

    lines = [
        "<h1>ASPICE Gap Analysis Report</h1>",
        f"<p>Criteria assessed: {criteria_count}, Gaps identified: {total_gaps}</p>",
        "<h2>Findings</h2>",
        "<table><thead><tr><th>Criteria ID</th><th>Rating</th>"
        "<th>Gaps</th><th>Recommendations</th></tr></thead><tbody>",
    ]
    for r in evaluation.ratings:
        gaps = "; ".join(r.gaps) if r.gaps else "—"
        recs = "; ".join(r.recommendations) if r.recommendations else "—"
        lines.append(
            f"<tr><td>{r.criteria_id}</td><td>{r.rating}</td>"
            f"<td>{gaps}</td><td>{recs}</td></tr>"
        )
    lines.append("</tbody></table>")
    return "\n".join(lines)


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
    help="AI provider: bedrock, openai, anthropic. Default: bedrock.",
)
@click.option(
    "--model",
    default=None,
    help="AI model name. Default depends on provider.",
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
    help="Output directory for intermediate artifacts.",
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
    no_publish: bool,
    verbose: bool,
    quiet: bool,
) -> None:
    """Run a full ASPICE gap analysis pipeline on a Confluence SDP page.

    PAGE_URL is the full Confluence Cloud page URL of the SDP to analyze.
    """
    # --- Configure logging ---
    _configure_logging(verbose, quiet)

    # --- Resolve parameters ---
    try:
        resolved_email, resolved_token = _resolve_credentials(email, api_token)
        resolved_provider, resolved_model, resolved_region = _resolve_ai_config(
            provider, model, region,
        )
    except click.UsageError:
        raise

    process_groups = [g.strip() for g in groups.split(",") if g.strip()]

    # Default output directory
    if output_dir is None:
        output_dir = os.path.join("aspice-output", "pipeline")
    os.makedirs(output_dir, exist_ok=True)

    # --- Export Stage ---
    if not quiet:
        click.echo("Stage 1/3: Exporting Confluence page...", err=True)

    try:
        ai_config = confluence_ai.ImageDescriberConfig(
            provider=resolved_provider,
            model=resolved_model,
            region=resolved_region,
        )
        export_result = confluence_ai.export_page(
            page_url,
            output_dir,
            email=resolved_email,
            api_token=resolved_token,
            ai_config=ai_config,
        )
    except click.UsageError:
        raise
    except Exception as exc:
        _handle_stage_error("Export", exc)
        return  # unreachable, but satisfies type checker

    if not quiet:
        click.echo(
            f"  Export complete: {export_result.images_downloaded} images, "
            f"{export_result.descriptions_generated} descriptions",
            err=True,
        )

    # --- Evaluate Stage ---
    if not quiet:
        click.echo("Stage 2/3: Evaluating against ASPICE criteria...", err=True)

    try:
        model_config = aspice_eval.ModelConfig(
            provider=resolved_provider,
            model_name=resolved_model,
            temperature=float(os.environ.get("ASPICE_EVAL_TEMPERATURE", "0.0")),
            max_tokens=int(os.environ.get("ASPICE_EVAL_MAX_TOKENS", "4096")),
            region=resolved_region,
        )
        evaluation = aspice_eval.evaluate_sdp(
            export_result.markdown_path,
            model_config,
            target_level=target_level,
            process_groups=process_groups,
        )
    except Exception as exc:
        _handle_stage_error("Evaluate", exc)
        return

    total_gaps = sum(len(r.gaps) for r in evaluation.ratings)

    if not quiet:
        click.echo(
            f"  Evaluation complete: {len(evaluation.ratings)} criteria assessed, "
            f"{total_gaps} gaps identified",
            err=True,
        )

    # --- Publish Stage ---
    if not no_publish:
        if not quiet:
            click.echo("Stage 3/3: Publishing report to Confluence...", err=True)

        report_html = _generate_html_report(evaluation)

        # Resolve report title
        resolved_title = report_title or f"ASPICE Gap Analysis L{target_level}"

        # Extract base URL from page URL for publishing
        parsed = confluence_ai.URLParser().parse(page_url)

        try:
            page_result_url = confluence_ai.publish_page(
                report_html,
                email=resolved_email,
                api_token=resolved_token,
                base_url=parsed.base_url,
                space_key=parsed.space_key if hasattr(parsed, "space_key") else "",
                title=resolved_title,
                parent_page_id=parsed.page_id,
            )
        except Exception as exc:
            _handle_stage_error("Publish", exc)
            return

        if not quiet:
            click.echo(f"  Published: {page_result_url}", err=True)
    else:
        if not quiet:
            click.echo("Stage 3/3: Skipped (--no-publish)", err=True)

    # --- Summary ---
    click.echo("Pipeline complete.", err=True)
    click.echo(f"  Criteria assessed: {len(evaluation.ratings)}", err=True)
    click.echo(f"  Gaps identified: {total_gaps}", err=True)
    click.echo(f"  Output directory: {output_dir}", err=True)


def _configure_logging(verbose: bool, quiet: bool) -> None:
    """Configure logging to stderr with appropriate level."""
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

    for pkg_name in ("aspice_eval", "confluence_ai", "aspice_check"):
        pkg_logger = logging.getLogger(pkg_name)
        pkg_logger.setLevel(level)
        pkg_logger.handlers.clear()
        pkg_logger.addHandler(handler)
