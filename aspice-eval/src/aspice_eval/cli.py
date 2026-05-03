"""Click-based CLI entry point for the ASPICE evaluation tool.

Provides three commands:

- ``evaluate`` — Run a gap analysis of an SDP document against the KB.
- ``validate-kb`` — Validate the knowledge base schema and completeness.
- ``version`` — Print the package version.

The entry point is ``aspice_eval.cli:main`` (configured in pyproject.toml).

Requirements: 3.3, 7.1, 7.2, 7.3, 9.3
"""

from __future__ import annotations

import os
import pathlib
import sys

import click
import yaml

from aspice_eval import __version__
from aspice_eval.exceptions import (
    AIModelError,
    AIResponseParseError,
    InvalidConfigError,
    KBValidationError,
    UnsupportedFormatError,
)


def _validate_config(
    target_level: int,
    groups: list[str],
    kb_path: str,
) -> None:
    """Validate configuration parameters early (fail fast).

    Raises
    ------
    InvalidConfigError
        If *target_level* is outside 1–5 or *groups* contains unknown codes.
    FileNotFoundError
        If *kb_path* does not exist.
    """
    # Validate target level
    if target_level < 1 or target_level > 5:
        raise InvalidConfigError(
            f"Target level {target_level} is out of range. Must be 1–5.",
            parameter="target_level",
            actual_value=target_level,
            expected_values=[1, 2, 3, 4, 5],
        )

    # Validate KB path exists
    kb = pathlib.Path(kb_path)
    if not kb.exists():
        raise FileNotFoundError(
            f"Knowledge base path does not exist: {kb_path}"
        )

    # Load metadata to get valid process group codes
    metadata_path = kb / "aspice" / "_metadata.yaml"
    if metadata_path.exists():
        with open(metadata_path) as fh:
            metadata = yaml.safe_load(fh)
        valid_codes = {
            pg.get("code", "")
            for pg in metadata.get("process_groups", [])
        }
        unknown = [g for g in groups if g not in valid_codes]
        if unknown:
            raise InvalidConfigError(
                f"Unknown process group(s): {', '.join(unknown)}. "
                f"Valid groups: {', '.join(sorted(valid_codes))}.",
                parameter="process_groups",
                actual_value=unknown,
                expected_values=sorted(valid_codes),
            )


@click.group()
def main() -> None:
    """ASPICE evaluation tool for SDP gap analysis."""


@main.command()
@click.option(
    "--sdp",
    required=True,
    type=click.Path(),
    help="Path to the SDP Markdown document.",
)
@click.option(
    "--target-level",
    default=3,
    type=int,
    show_default=True,
    help="Target ASPICE capability level (1–5).",
)
@click.option(
    "--groups",
    default="SWE,SYS,MAN,SUP",
    show_default=True,
    help="Comma-separated process group codes to evaluate.",
)
@click.option(
    "--output",
    default=None,
    type=click.Path(),
    help="Output file path for the report. Defaults to stdout.",
)
@click.option(
    "--kb-path",
    default="knowledge_base",
    show_default=True,
    type=click.Path(),
    help="Path to the knowledge base directory.",
)
@click.option(
    "--model",
    default=None,
    type=str,
    help="AI model name (provider-specific model identifier).",
)
@click.option(
    "--provider",
    default=None,
    type=str,
    help="AI provider name: bedrock, openai, anthropic, mock. "
    "Defaults to ASPICE_EVAL_PROVIDER env var, then 'mock'.",
)
@click.option(
    "--region",
    default=None,
    type=str,
    help="AWS region for Bedrock provider (default us-east-1).",
)
@click.option(
    "--output-format",
    "output_format",
    default="markdown",
    type=click.Choice(["markdown", "html"], case_sensitive=False),
    show_default=True,
    help="Report output format.",
)
def evaluate(
    sdp: str,
    target_level: int,
    groups: str,
    output: str | None,
    kb_path: str,
    model: str | None,
    provider: str | None,
    region: str | None,
    output_format: str,
) -> None:
    """Evaluate an SDP document against ASPICE criteria."""
    process_groups = [g.strip() for g in groups.split(",") if g.strip()]

    # Resolve provider: CLI flag > env var > default "mock"
    resolved_provider = (
        provider
        or os.environ.get("ASPICE_EVAL_PROVIDER")
        or "mock"
    )

    # Resolve model: CLI flag > env var > provider default
    _model_defaults: dict[str, str] = {
        "bedrock": "us.anthropic.claude-sonnet-4-20250514-v1:0",
        "openai": "gpt-4o",
        "anthropic": "claude-sonnet-4-20250514",
        "mock": "",
    }
    resolved_model = (
        model
        or os.environ.get("ASPICE_EVAL_MODEL")
        or _model_defaults.get(resolved_provider, "")
    )

    # Resolve temperature: env var (CLI doesn't expose this directly)
    resolved_temperature = float(
        os.environ.get("ASPICE_EVAL_TEMPERATURE", "0.0")
    )

    # Resolve max_tokens: env var
    resolved_max_tokens = int(
        os.environ.get("ASPICE_EVAL_MAX_TOKENS", "4096")
    )

    # Resolve region: CLI flag > env var > default ""
    resolved_region = (
        region
        or os.environ.get("AWS_REGION")
        or ""
    )

    try:
        # --- Fail-fast validation ---
        _validate_config(target_level, process_groups, kb_path)

        # Check SDP path exists before doing anything else
        sdp_path = pathlib.Path(sdp)
        if not sdp_path.exists():
            raise FileNotFoundError(f"SDP document not found: {sdp}")

        # --- Wire components ---
        from aspice_eval.knowledge_base import KnowledgeBase
        from aspice_eval.level_calculator import CapabilityLevelCalculator
        from aspice_eval.models import EvaluationConfig, ModelConfig
        from aspice_eval.providers import create_evaluator
        from aspice_eval.report_generator import ReportGenerator
        from aspice_eval.sdp_ingester import SDPIngester

        # 1. Load KB
        kb = KnowledgeBase(kb_path)
        kb.load("aspice")
        kb_metadata = kb.get_metadata()

        # 2. Ingest SDP
        ingester = SDPIngester()
        sdp_doc = ingester.ingest(sdp)

        # 3. Get criteria for requested groups and level
        criteria = kb.get_criteria(process_groups, target_level)

        # 4. Build config
        config = EvaluationConfig(
            sdp_path=sdp,
            target_capability_level=target_level,
            process_groups=process_groups,
            kb_path=kb_path,
            output_path=output,
        )

        # 5. Evaluate using provider factory
        model_config = ModelConfig(
            provider=resolved_provider,
            model_name=resolved_model,
            temperature=resolved_temperature,
            max_tokens=resolved_max_tokens,
            region=resolved_region,
        )
        evaluator = create_evaluator(model_config)
        evaluation = evaluator.evaluate(sdp_doc, criteria, config)

        # 6. Calculate capability levels
        calculator = CapabilityLevelCalculator(target_level)
        levels = calculator.calculate(evaluation.ratings, process_groups)

        # 7. Generate report
        reporter = ReportGenerator()
        report = reporter.generate(evaluation, levels, config, kb_metadata, output_format=output_format)

        # 8. Output
        if output:
            pathlib.Path(output).write_text(report, encoding="utf-8")
            click.echo(f"Report written to {output}")
        else:
            click.echo(report)

    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except UnsupportedFormatError as exc:
        click.echo(
            f"Error: {exc}",
            err=True,
        )
        sys.exit(1)
    except KBValidationError as exc:
        click.echo(f"KB validation error: {exc}", err=True)
        sys.exit(1)
    except InvalidConfigError as exc:
        click.echo(f"Configuration error: {exc}", err=True)
        sys.exit(1)
    except AIModelError as exc:
        click.echo(f"AI model error: {exc}", err=True)
        sys.exit(1)
    except AIResponseParseError as exc:
        click.echo(f"AI response parse error: {exc}", err=True)
        sys.exit(1)


@main.command("validate-kb")
@click.option(
    "--kb-path",
    default="knowledge_base",
    show_default=True,
    type=click.Path(),
    help="Path to the knowledge base directory.",
)
def validate_kb(kb_path: str) -> None:
    """Validate the knowledge base schema and completeness."""
    try:
        kb_dir = pathlib.Path(kb_path)
        if not kb_dir.exists():
            raise FileNotFoundError(
                f"Knowledge base path does not exist: {kb_path}"
            )

        from aspice_eval.knowledge_base import KnowledgeBase

        kb = KnowledgeBase(kb_path)
        kb.load("aspice")
        result = kb.validate()

        if result.is_valid:
            click.echo("Knowledge base validation passed.")
        else:
            click.echo("Knowledge base validation FAILED.", err=True)

        if result.schema_errors:
            click.echo("\nSchema errors:", err=True)
            for err in result.schema_errors:
                click.echo(f"  - {err}", err=True)

        if result.completeness_gaps:
            click.echo("\nCompleteness gaps:", err=True)
            for gap in result.completeness_gaps:
                click.echo(f"  - {gap}", err=True)

        if result.warnings:
            click.echo("\nWarnings:")
            for warn in result.warnings:
                click.echo(f"  - {warn}")

        if not result.is_valid:
            sys.exit(1)

    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except KBValidationError as exc:
        click.echo(f"KB validation error: {exc}", err=True)
        sys.exit(1)


@main.command()
def version() -> None:
    """Print the package version."""
    click.echo(f"aspice-eval {__version__}")
