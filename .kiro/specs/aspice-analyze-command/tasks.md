# Implementation Plan: Single-Command ASPICE Analysis Pipeline (`aspice-analyze`)

## Overview

This plan implements the `aspice-analyze` CLI command — an orchestration layer that composes existing `confluence-exporter` and `aspice-eval` components into a single three-stage pipeline: Export → Evaluate → Publish. The implementation lives in a single new module (`aspice-eval/src/aspice_eval/analyze.py`) with supporting changes to `pyproject.toml` for the new entry point and dependencies.

Implementation proceeds bottom-up: data models and pure helper functions first, then stage orchestration functions, CLI wiring, error handling, and finally packaging. Each step builds on the previous, ensuring no orphaned code.

**Language:** Python (matching the existing codebase)
**Base path:** `aspice-eval/`
**New files:** `aspice-eval/src/aspice_eval/analyze.py`, test files in `aspice-eval/tests/`
**Modified files:** `aspice-eval/pyproject.toml`

## Tasks

- [x] 1. Define data models and pure helper functions
  - [x] 1.1 Create `analyze.py` module with dataclasses and helpers
    - Create `aspice-eval/src/aspice_eval/analyze.py` with module docstring
    - Define `TokenTracker` dataclass with fields: `export_input_tokens`, `export_output_tokens`, `export_calls`, `eval_input_tokens`, `eval_output_tokens`, `eval_calls`, and computed properties `total_input_tokens`, `total_output_tokens`, `total_tokens`, `total_calls`
    - Define `ExportStageResult` dataclass with fields: `markdown_path`, `page_title`, `page_id`, `space_key`, `images_downloaded`, `descriptions_generated`, `warnings`
    - Define `EvaluateStageResult` dataclass with fields: `report_markdown`, `report_html`, `levels`, `total_gaps`, `criteria_assessed`
    - Implement `_sanitize_title(title: str) -> str` that produces strings containing only alphanumeric characters, underscores, and hyphens
    - Implement `_resolve_credentials(email, api_token) -> tuple[str, str]` that resolves CLI options vs environment variables, raising `click.UsageError` when missing
    - Implement `_resolve_ai_config(provider, model, region) -> tuple[str, str, str]` that resolves AI settings with defaults (bedrock, Sonnet model, region from env)
    - Implement `_format_summary(page_url, levels, total_gaps, output_dir, token_tracker, provider, model, region) -> str` that formats the final pipeline summary
    - Implement `_configure_logging(verbose, quiet)` that sets up logging to stderr
    - _Requirements: 1.3, 1.5, 2.5, 3.1, 3.2, 3.3, 3.4, 12.1, 12.2, 12.3, 12.4, 12.5, 13.1, 13.3, 13.4_

  - [x]* 1.2 Write property test for title sanitization (Property 1)
    - **Property 1: Output directory path is correctly derived from page title**
    - For any page title string (including spaces, special characters, unicode, empty strings), `_sanitize_title()` produces a string containing only alphanumeric characters, underscores, and hyphens
    - **Validates: Requirements 1.3**

  - [x]* 1.3 Write property test for token tracker accumulation (Property 7)
    - **Property 7: Token tracker accumulation is correct**
    - For any combination of export-stage and evaluate-stage token counts, `TokenTracker` reports correct totals: `total_input_tokens == export_input + eval_input`, `total_output_tokens == export_output + eval_output`, `total_tokens == total_input + total_output`, `total_calls == export_calls + eval_calls`
    - **Validates: Requirements 13.1, 13.3**

  - [x]* 1.4 Write property test for credential resolution precedence (Property 3)
    - **Property 3: CLI option takes precedence over environment variable**
    - For any credential parameter where both CLI and env var are provided, resolved value equals CLI value. When only env var is set, resolved value equals env var value.
    - **Validates: Requirements 2.5, 12.1, 12.2, 12.3, 12.4, 12.5**

  - [x]* 1.5 Write property test for summary format completeness (Property 2)
    - **Property 2: Pipeline summary contains all required fields**
    - For any combination of page URL, capability levels, gap counts, output directory, and token usage, the formatted summary contains all required fields
    - **Validates: Requirements 1.5, 13.4**

- [x] 2. Checkpoint — Verify data models and helpers
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Implement stage orchestration functions
  - [x] 3.1 Implement `_resolve_kb_path()` function
    - Use `importlib.resources` to locate the `knowledge_base/` directory from installed package data
    - Fall back to relative filesystem path from `__file__` for development mode
    - Raise `FileNotFoundError` if KB not found in any candidate location
    - _Requirements: 6.1, 11.5_

  - [x] 3.2 Implement `_run_export_stage()` function
    - Accept parameters: `page_url`, `email`, `api_token`, `provider`, `model`, `region`, `output_dir`, `quiet`, `token_tracker`
    - Use `URLParser.parse()` to extract base URL and page ID from the Confluence URL
    - Create `ConfluenceClient` with credentials and retrieve page content and attachments
    - Use `StorageFormatParser.parse()` to parse storage format XHTML
    - Use `AssetDownloader.download_assets()` to download images to output directory
    - Use `ImageDescriber.describe_batch()` (via `create_describer` factory) for AI image descriptions
    - Use `MarkdownRenderer.render()` to produce Markdown output
    - Write Markdown to `{output_dir}/{sanitized_title}.md`
    - Update `token_tracker` with export-stage token counts from the image describer
    - Return `ExportStageResult` with page metadata and counts
    - Print progress messages to stderr (unless `quiet`)
    - _Requirements: 1.2, 5.1, 5.2, 5.3, 5.4, 5.5, 9.1, 9.2_

  - [x] 3.3 Implement `_run_evaluate_stage()` function
    - Accept parameters: `markdown_path`, `target_level`, `groups`, `provider`, `model`, `region`, `token_tracker`, `quiet`
    - Load ASPICE KB using `_resolve_kb_path()` and `KnowledgeBase.load()`
    - Ingest exported Markdown using `SDPIngester.ingest()`
    - Get criteria using `KnowledgeBase.get_criteria()`
    - Create evaluator using `create_evaluator()` factory with `ModelConfig`
    - Run evaluation using `GapAnalysisEvaluator.evaluate()`
    - Calculate capability levels using `CapabilityLevelCalculator.calculate()`
    - Generate report (both Markdown and HTML) using `ReportGenerator.generate()`
    - Update `token_tracker` with evaluate-stage token counts
    - Return `EvaluateStageResult` with report content, levels, and metrics
    - Print progress messages to stderr (unless `quiet`)
    - _Requirements: 1.2, 6.1, 6.2, 6.3, 6.4, 9.1, 9.2, 13.1_

  - [x] 3.4 Implement `_run_publish_stage()` function
    - Accept parameters: `report_html`, `page_id`, `space_key`, `report_title`, `base_url`, `email`, `api_token`, `quiet`
    - Create `atlassian-python-api` `Confluence` client with credentials
    - Convert report HTML to Confluence storage format via `/rest/api/contentbody/convert/storage` endpoint
    - Strip emoji characters that the Confluence Fabric editor rejects
    - Search for existing child page with same title under source page
    - If found: update existing page; if not found: create new child page
    - Return the URL of the created/updated page
    - Print progress messages to stderr (unless `quiet`)
    - _Requirements: 1.2, 7.1, 7.2, 7.3, 7.4, 7.5, 9.1, 9.2, 10.6_

  - [x]* 3.5 Write property test for target-level validation (Property 4)
    - **Property 4: Invalid target-level values are rejected**
    - For any integer outside range 1–5, parameter validation rejects the value with an error message identifying the valid range
    - **Validates: Requirements 4.6**

  - [x]* 3.6 Write property test for group code validation (Property 5)
    - **Property 5: Invalid process group codes are rejected**
    - For any string not in the valid process group code set, validation rejects with an error listing valid codes
    - **Validates: Requirements 4.7**

- [x] 4. Implement CLI command and error handling
  - [x] 4.1 Implement the `analyze` Click command
    - Define `@click.command("aspice-analyze")` with all CLI options from the design:
      - `page_url` (positional argument)
      - `--target-level` (required, int)
      - `--groups` (required, str)
      - `--email` (envvar `CONFLUENCE_EMAIL`)
      - `--api-token` (envvar `CONFLUENCE_API_TOKEN`)
      - `--provider` (envvar `ASPICE_EVAL_PROVIDER`, default None → resolved to "bedrock")
      - `--model` (default None → resolved to Sonnet)
      - `--region` (envvar `AWS_DEFAULT_REGION`)
      - `--report-title` (default None → "ASPICE Gap Analysis — {page title}")
      - `--output-dir` (default None → `./aspice-output/{sanitized_title}/`)
      - `--output` (file path for local report)
      - `--output-format` (markdown/html, default markdown)
      - `--no-publish` (flag)
      - `--verbose` (flag)
      - `--quiet` (flag)
    - Wire the three stages in sequence: validate params → export → evaluate → publish (unless `--no-publish`)
    - Handle `--output` flag: write report to specified path
    - Handle `--no-publish` without `--output`: print report to stdout
    - Handle both `--output` and publish: save locally AND publish
    - Print final summary to stdout on success
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.3, 9.4, 9.5_

  - [x] 4.2 Implement error handling with stage identification and exit codes
    - Wrap each stage in try/except that catches stage-specific exceptions
    - Map Export Stage errors: `InvalidURLError` → exit 2, `AuthenticationError` → exit 2, `ConfluenceConnectionError` → exit 2, `PageNotFoundError` → exit 2, `botocore.ClientError` → exit 2 with AWS session message
    - Map Evaluate Stage errors: `FileNotFoundError` → exit 3, `KBValidationError` → exit 3, `AIModelError` → exit 3, `AIResponseParseError` → exit 3
    - Map Publish Stage errors: `HTTPError` (403) → exit 4 with permission message, other `HTTPError` → exit 4, `ConnectionError` → exit 4
    - Map parameter validation errors → exit 1
    - All error messages identify which stage failed and include the reason
    - _Requirements: 1.6, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x]* 4.3 Write property test for stage failure identification (Property 6)
    - **Property 6: Stage failure identification in error messages**
    - For any pipeline stage that raises an exception, the error output identifies which stage failed, and the command exits with a non-zero exit code
    - **Validates: Requirements 10.5, 1.6**

  - [x]* 4.4 Write unit tests for CLI options and error mapping
    - Test all CLI options are registered with correct types and defaults
    - Test `--no-publish` skips Publish Stage
    - Test `--output` writes report to file
    - Test `--quiet` suppresses progress messages
    - Test `--verbose` sets DEBUG logging
    - Test each error type maps to correct exit code (1–4)
    - Test missing credentials produce descriptive error messages
    - _Requirements: 1.6, 2.6, 4.6, 4.7, 8.4, 8.5, 9.4, 9.5, 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 5. Checkpoint — Verify CLI and error handling
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Update packaging and entry points
  - [x] 6.1 Update `pyproject.toml` with new entry point and dependencies
    - Add `aspice-analyze = "aspice_eval.analyze:analyze"` to `[project.scripts]`
    - Add `confluence-exporter` to dependencies (or optional dependencies)
    - Add `atlassian-python-api` to dependencies
    - Add `knowledge_base` directory to package data via `[tool.setuptools.package-data]`
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x]* 6.2 Write unit tests for packaging
    - Test that `aspice-analyze` entry point is resolvable after install
    - Test that `knowledge_base/` files are included in package data
    - Test that `confluence-exporter` and `atlassian-python-api` are declared as dependencies
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 7. Final checkpoint — Full integration verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (Properties 1–7)
- The implementation is purely orchestration code — all business logic lives in existing `confluence-exporter` and `aspice-eval` components
- The `analyze.py` module is intentionally a single file since it contains only glue code, no new business logic
- Test files follow existing naming conventions: `tests/property/test_prop{NN}_*.py` for property tests, `tests/unit/test_*.py` for unit tests
