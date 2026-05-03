# Implementation Plan: Confluence Page Exporter

## Overview

This plan implements a Python CLI tool (`confluence-export`) that exports Confluence Cloud pages to self-contained Markdown files with locally downloaded images and AI-generated image descriptions. Implementation proceeds bottom-up: data models and exceptions first, then URL parsing, Confluence client, XHTML-to-IR parser, asset downloader, image describer, Markdown renderer, and finally CLI wiring. Each step builds on the previous, ensuring no orphaned code.

**Base path:** All files are created under `confluence-exporter/` at the workspace root (e.g., `confluence-exporter/src/confluence_exporter/`, `confluence-exporter/tests/`, etc.).

## Tasks

- [x] 1. Set up project structure, dependencies, and data models
  - [x] 1.1 Create Python package structure and configuration
    - Create `confluence-exporter/` directory with `pyproject.toml`
    - Configure `setuptools` with PEP 621 metadata, src layout, entry point `confluence-export` → `confluence_exporter.cli:main`
    - Runtime dependencies: `click >=8.1.0`, `atlassian-python-api >=3.41.0`, `pyyaml >=6.0`, `requests >=2.31.0`
    - Optional dependencies: `anthropic` under `[anthropic]`, `openai` under `[openai]`
    - Dev dependencies: `pytest >=7.4.0`, `hypothesis >=6.90.0`, `pytest-mock`
    - Create `src/confluence_exporter/__init__.py` with version string
    - Create `tests/conftest.py` with Hypothesis profiles (ci: 100, dev: 50)
    - Create `tests/property/`, `tests/unit/`, `tests/integration/` directories with `__init__.py`
    - _Requirements: 7.1, 7.6_

  - [x] 1.2 Define all data model classes
    - Create `src/confluence_exporter/models.py` with all dataclasses from the design:
    - **IR nodes:** `ContentNode`, `HeadingNode`, `ParagraphNode`, `InlineNode`, `TextNode`, `LinkNode`, `ListNode`, `ListItemNode`, `TableNode`, `ImageNode`, `GliffyNode`, `CodeBlockNode`, `HorizontalRuleNode`, `MacroNode`
    - **API models:** `ParsedURL`, `PageData`, `AttachmentData`, `PageMetadata`
    - **Config models:** `ImageDescriberConfig`, `ImageContext`
    - **Result models:** `ExportResult`
    - Use `from __future__ import annotations`, type hints throughout, `field(default_factory=...)` for mutable defaults
    - _Requirements: 2.1, 3.1, 3.2, 4.3, 5.3, 8.5_

  - [x] 1.3 Define custom exception classes
    - Create `src/confluence_exporter/exceptions.py` with: `InvalidURLError`, `AuthenticationError`, `ConnectionError`, `PageNotFoundError`, `ParseError`, `DownloadError`, `ImageDescriptionError`, `FileSystemError`
    - Each exception carries structured context (URL, status code, filename, etc.)
    - _Requirements: 1.2, 1.3, 2.3, 2.4, 9.3_

- [x] 2. Implement URL parser and credential resolution
  - [x] 2.1 Implement URL parser
    - Create `src/confluence_exporter/url_parser.py` with `URLParser` class
    - `parse(url: str) -> ParsedURL`: extract base URL and numeric page ID from Confluence Cloud URL patterns
    - Regex: `^(https://[^/]+\.atlassian\.net/wiki)/spaces/[^/]+/pages/(\d+)`
    - Raise `InvalidURLError` with descriptive message for non-matching URLs
    - _Requirements: 2.1, 2.3_

  - [x]* 2.2 Write property test for URL parsing (Property 2)
    - **Property 2: URL parser extracts correct page ID from valid URLs and rejects invalid URLs**
    - Generate random valid Confluence Cloud URLs with varying domains, spaces, page IDs, and optional titles; verify correct extraction
    - Generate random invalid strings; verify `InvalidURLError` is raised
    - **Validates: Requirements 2.1, 2.3**

  - [x]* 2.3 Write property test for credential precedence (Property 1)
    - **Property 1: Credential resolution follows precedence order**
    - Generate random credential values across CLI/env/config sources with random presence; verify CLI > env > config precedence
    - **Validates: Requirements 1.4**

- [x] 3. Implement Confluence client
  - [x] 3.1 Implement ConfluenceClient class
    - Create `src/confluence_exporter/client.py` with `ConfluenceClient` class
    - `__init__(base_url, email, api_token)`: initialize `atlassian-python-api` `Confluence` instance with Basic Auth
    - `get_page(page_id) -> PageData`: retrieve page with `expand=body.storage,metadata.labels,version`, map to `PageData`
    - `get_attachments(page_id) -> list[AttachmentData]`: retrieve attachment list, map to `AttachmentData`
    - `download_attachment(download_url, dest_path)`: download binary content to local file
    - Map HTTP errors: 401 → `AuthenticationError`, 404 → `PageNotFoundError`, 403 → `PageNotFoundError`, connection errors → `ConnectionError`
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.4_

  - [x]* 3.2 Write unit tests for client error handling
    - Test `AuthenticationError` on 401 response
    - Test `PageNotFoundError` on 404 and 403 responses
    - Test `ConnectionError` on unreachable URL
    - Mock `atlassian-python-api` calls
    - _Requirements: 1.2, 1.3, 2.4_

- [x] 4. Checkpoint — Verify project setup and client
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement storage format parser (XHTML → IR)
  - [x] 5.1 Implement StorageFormatParser class
    - Create `src/confluence_exporter/parser.py` with `StorageFormatParser` class
    - `parse(xhtml: str) -> list[ContentNode]`: parse XHTML using `xml.etree.ElementTree`
    - Handle Confluence namespaces: `ac:` (http://atlassian.com/content), `ri:` (http://atlassian.com/resource/identifier)
    - Map elements to IR nodes per the design table: headings, paragraphs, text formatting (bold/italic/underline/code), lists (ordered/unordered), tables, images (`ac:image` with `ri:attachment` or `ri:url`), Gliffy macros, links, code blocks, horizontal rules
    - Unknown `ac:structured-macro` elements → `MacroNode` with name, params, body text
    - Raise `ParseError` for malformed XHTML
    - _Requirements: 3.1, 3.2, 3.4_

  - [x]* 5.2 Write unit tests for parser edge cases
    - Test nested lists, empty tables, code blocks with language attribute
    - Test Gliffy macro extraction with name and diagram ID
    - Test unknown macro fallback to `MacroNode`
    - Test malformed XHTML raises `ParseError`
    - _Requirements: 3.1, 3.2, 3.4_

- [x] 6. Implement Markdown renderer (IR → Markdown)
  - [x] 6.1 Implement MarkdownRenderer class
    - Create `src/confluence_exporter/renderer.py` with `MarkdownRenderer` class
    - `render(nodes, metadata, descriptions) -> str`: produce complete Markdown with YAML front-matter
    - `_render_front_matter(metadata) -> str`: YAML block with source_url, page_id, page_title, export_timestamp, exporter_version, space_key, labels
    - `_render_node(node) -> str`: dispatch to type-specific renderers
    - Heading: `# ` prefix matching level (1–6)
    - Paragraph: inline children with bold (`**`), italic (`*`), underline (rendered as italic), code (`` ` ``), links (`[text](href)`)
    - Lists: `-` for unordered, `1.` for ordered, with nesting support
    - Tables: pipe-delimited with header separator row
    - Code blocks: fenced with language
    - Images/Gliffy with local_path: `![alt](images/filename)` followed by optional blockquote description `> **Image Description:** ...`
    - Images/Gliffy with local_path=None: placeholder text (no image reference)
    - MacroNode: body as plain text + HTML comment `<!-- confluence macro: {name} -->`
    - Horizontal rule: `---`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.3, 5.3, 5.4, 6.3, 8.5_

  - [x]* 6.2 Write property test for heading compatibility (Property 4)
    - **Property 4: Rendered headings are compatible with SDPIngester header extraction**
    - Generate random `HeadingNode` with level 1–6 and non-empty text; verify rendered line matches `^(#{1,6})[ \t]+(\S.*)` regex
    - **Validates: Requirements 3.3**

  - [x]* 6.3 Write property test for unknown macro rendering (Property 5)
    - **Property 5: Unknown macros render as plain text with identifying comment**
    - Generate random `MacroNode` with non-empty name and body; verify rendered output contains body text and HTML comment with macro name
    - **Validates: Requirements 3.4**

  - [x]* 6.4 Write property test for image rendering (Property 6)
    - **Property 6: Image and Gliffy nodes with local paths render as Markdown image references with correct alt-text**
    - Generate random `ImageNode`/`GliffyNode` with non-null local_path; verify Markdown image reference `![alt](images/...)` format
    - For `GliffyNode`, verify alt-text equals diagram name
    - **Validates: Requirements 4.3, 5.3, 5.4**

  - [x]* 6.5 Write property test for failed download placeholders (Property 7)
    - **Property 7: Failed asset downloads produce placeholder text in rendered Markdown**
    - Generate random `ImageNode`/`GliffyNode` with local_path=None; verify placeholder text present and no Markdown image reference
    - **Validates: Requirements 4.5, 5.5**

  - [x]* 6.6 Write property test for image description format (Property 8)
    - **Property 8: Image descriptions are embedded as blockquotes with correct prefix**
    - Generate random image nodes with non-empty descriptions; verify blockquote line `> **Image Description:** ...` follows image reference
    - **Validates: Requirements 6.3**

  - [x]* 6.7 Write property test for YAML front-matter (Property 13)
    - **Property 13: YAML front-matter contains all required metadata fields**
    - Generate random `PageMetadata` instances; verify rendered YAML block contains source_url, page_id, page_title, export_timestamp, exporter_version
    - **Validates: Requirements 8.5**

  - [ ]* 6.8 Write property test for IR round-trip (Property 3)
    - **Property 3: IR-to-Markdown round-trip preserves semantic structure**
    - Generate random `ContentNode` IR trees; render to Markdown; parse back; verify structural equivalence (headings, lists, tables, text content)
    - **Validates: Requirements 3.1, 3.2, 3.5**

- [x] 7. Checkpoint — Verify parser and renderer
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement asset downloader
  - [x] 8.1 Implement AssetDownloader class
    - Create `src/confluence_exporter/downloader.py` with `AssetDownloader` class
    - `__init__(client, output_dir)`: store client reference, create `output_dir/images/` directory
    - `download_assets(nodes, attachments) -> list[ContentNode]`: iterate nodes, download images and Gliffy PNGs, update `local_path`
    - For `ImageNode` with source_type="attachment": find matching attachment by filename, download via client
    - For `ImageNode` with source_type="external": download via `requests.get`
    - For `GliffyNode`: use `_resolve_gliffy_attachment()` to find PNG preview, download via client
    - `_resolve_gliffy_attachment(node, attachments) -> AttachmentData | None`: search by exact name match, partial match, or media type with "gliffy" in filename
    - `_sanitize_filename(name) -> str`: spaces → underscores, remove special chars, preserve extension, numeric suffix for collisions
    - On download failure: log WARNING, set `local_path=None`, continue processing
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3, 5.5, 8.2, 8.3_

  - [x]* 8.2 Write property test for filename sanitization (Property 10)
    - **Property 10: Filename sanitization preserves extensions and produces unique names**
    - Generate random filename lists with duplicates, spaces, special characters; verify extension preservation, space→underscore, special char removal, uniqueness
    - **Validates: Requirements 4.6, 8.1, 8.3**

  - [x]* 8.3 Write property test for Gliffy attachment resolution (Property 11)
    - **Property 11: Gliffy attachment resolver finds matching PNG preview**
    - Generate random `GliffyNode` names and attachment lists with/without matching PNGs; verify correct match or None
    - **Validates: Requirements 5.1**

- [x] 9. Implement image describer with AI providers
  - [x] 9.1 Implement base ImageDescriber and prompt construction
    - Create `src/confluence_exporter/describer.py` with `ImageDescriber` base class
    - `describe(image_path, context) -> str`: abstract method for single image description
    - `describe_batch(images) -> dict[str, str]`: iterate and call `describe()`, catch `ImageDescriptionError` per image, use placeholder "Image description unavailable" on failure
    - `_build_prompt(context) -> str`: return general image prompt or Gliffy-specific prompt based on `context.is_gliffy`
    - General prompt: describe image type, key elements, relationships, text labels, purpose
    - Gliffy prompt: focus on diagram type, activities, decision points, swimlanes, inputs/outputs, transitions, flow direction, text labels
    - _Requirements: 6.1, 6.2, 6.4, 6.5_

  - [x] 9.2 Implement Anthropic image describer provider
    - Create `src/confluence_exporter/providers/__init__.py` with provider factory function
    - Create `src/confluence_exporter/providers/anthropic_describer.py` with `AnthropicImageDescriber`
    - Override `describe()`: read image as base64, send via Anthropic Messages API with image content block
    - Retry transient errors (429, 5xx, timeouts) up to 3 attempts with exponential backoff (1s, 2s)
    - Non-retryable errors (401, 403, invalid model): raise `ImageDescriptionError` immediately
    - _Requirements: 6.1, 6.5_

  - [x] 9.3 Implement OpenAI image describer provider
    - Create `src/confluence_exporter/providers/openai_describer.py` with `OpenAIImageDescriber`
    - Override `describe()`: read image as base64 data URL, send via Chat Completions API with `image_url` content part
    - Same retry strategy as Anthropic provider
    - _Requirements: 6.1, 6.5_

  - [x]* 9.4 Write property test for Gliffy prompt keywords (Property 9)
    - **Property 9: Gliffy diagram prompts include process flow instructions**
    - Generate random `ImageContext` with `is_gliffy=True`; verify prompt contains "activities", "decision points", "swimlanes", "transitions"
    - **Validates: Requirements 6.4**

  - [x]* 9.5 Write unit tests for AI provider error handling
    - Test placeholder description on provider failure
    - Test retry on transient errors (mock API)
    - Test `--no-ai` flag skips description generation entirely
    - _Requirements: 6.5, 6.6_

- [x] 10. Checkpoint — Verify downloader and describer
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement CLI entry point and wire pipeline together
  - [x] 11.1 Implement Click CLI
    - Create `src/confluence_exporter/cli.py` with Click-based CLI
    - `confluence-export` command with arguments: `page_url` (required), `output_dir` (required)
    - Options: `--email` (env: `CONFLUENCE_EMAIL`), `--api-token` (env: `CONFLUENCE_API_TOKEN`), `--confluence-url` (override base URL), `--ai-provider` (env: `CONFLUENCE_EXPORT_AI_PROVIDER`), `--ai-model` (env: `CONFLUENCE_EXPORT_AI_MODEL`), `--ai-api-key` (env: provider-specific), `--no-ai` flag, `--verbose` flag
    - Wire pipeline: URLParser → ConfluenceClient → get_page + get_attachments → StorageFormatParser → AssetDownloader → ImageDescriber (unless --no-ai) → MarkdownRenderer → write output
    - Create output directory and `images/` subdirectory if they don't exist
    - Write Markdown to `{sanitized_page_title}.md` in output directory
    - Print `ExportResult` summary to stdout
    - Log to stderr, INFO by default, DEBUG with `--verbose`
    - Exit 0 on success, non-zero on fatal errors
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.4, 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x]* 11.2 Write property test for export summary (Property 12)
    - **Property 12: Export summary contains all required information**
    - Generate random `ExportResult` instances; verify formatted summary contains markdown path, image count, description count, and all warnings
    - **Validates: Requirements 7.4**

  - [x]* 11.3 Write unit tests for CLI
    - Test required argument validation and usage message on missing args
    - Test `--no-ai` flag skips AI description
    - Test `--verbose` sets DEBUG logging
    - Test exit code 0 on success, non-zero on failure
    - Test environment variable fallback for credentials and AI config
    - _Requirements: 7.1, 7.2, 7.5, 7.6, 9.4_

- [x] 12. Checkpoint — Verify full pipeline
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Integration tests and final wiring
  - [x]* 13.1 Write end-to-end integration test
    - Mock Confluence API responses (page content with XHTML, attachment list)
    - Mock AI provider responses
    - Run full pipeline; verify output Markdown file exists with correct front-matter, headings, image references, and descriptions
    - Verify `images/` directory contains downloaded files
    - _Requirements: 3.1, 4.3, 5.3, 6.3, 8.1, 8.2, 8.5_

  - [x]* 13.2 Write Gliffy diagram integration test
    - Mock page with Gliffy macro and matching PNG attachment
    - Verify Gliffy diagram appears as image reference in output with diagram name as alt-text
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x]* 13.3 Write partial failure integration test
    - Mock one image download failure and one AI description failure
    - Verify export completes with placeholders for failed items and warnings in summary
    - _Requirements: 4.5, 5.5, 6.5, 9.2_

  - [x] 13.4 Create README with setup and usage instructions
    - Write `confluence-exporter/README.md` with: project overview, installation, usage examples, environment variable reference, AI provider configuration, example output
    - _Requirements: 7.1, 7.2_

- [x] 14. Final checkpoint — Full verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The storage format parser (task 5.1) is the most complex component — it must handle all Confluence XHTML elements and namespaces
- The AI describer (tasks 9.1–9.3) mirrors the `aspice-eval` provider pattern for consistency
- Shared environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) avoid duplicate credential configuration with `aspice-eval`
