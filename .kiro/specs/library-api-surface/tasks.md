# Implementation Plan: Library API Surface

## Overview

This plan converts the three-package architecture design into incremental coding tasks. Each step builds on previous steps and ends with wiring things together, avoiding orphaned code.

The migration proceeds bottom-up through three axes:
1. **Package restructure** — rename `confluence-exporter` → `confluence-ai`, carve out `aspice-check` as a new package, move Confluence I/O out of `aspice_eval.analyze`.
2. **API surface** — populate `__init__.py` files, add convenience functions, extension registries, and ABCs for each package.
3. **Orchestration & MCP** — wire `aspice-check` to call only top-level APIs, add the `aspice-mcp` server.

Property-based tests sit alongside the features they validate. All property test sub-tasks are optional (prefixed with `*`). The implementation language is **Python 3.10+** as used throughout the existing codebase.

## Tasks

- [x] 1. Property test infrastructure (shared)
  - [x] 1.1 Ensure Hypothesis profiles exist in `confluence-ai/tests/conftest.py` and a new `aspice-check/tests/conftest.py`
    - Mirror existing `aspice-eval/tests/conftest.py` profiles (`ci=100`, `dev=50`)
    - Provide shared strategies for valid/invalid provider names, class types, paths
    - _Requirements: supports Testing Strategy in design_

- [x] 2. Rename `confluence-exporter` package to `confluence-ai`
  - [x] 2.1 Rename directory `confluence-exporter/` → `confluence-ai/` and rename source package `src/confluence_exporter/` → `src/confluence_ai/`
    - Update all intra-package imports from `confluence_exporter` to `confluence_ai`
    - Update `pyproject.toml`: `name = "confluence-ai"`, description updated to remove ASPICE framing and describe general-purpose AI-powered Confluence toolkit
    - Update `[project.scripts]` entry point to reference `confluence_ai.cli:main`
    - Add `"Typing :: Typed"` classifier
    - _Requirements: 2.1, 2.2, 21.2, 21.5_

  - [x] 2.2 Add `py.typed` marker file at `confluence-ai/src/confluence_ai/py.typed`
    - Empty file, include via `[tool.setuptools.package-data]`
    - _Requirements: 21.2_

  - [x] 2.3 Update all test imports in `confluence-ai/tests/` from `confluence_exporter` to `confluence_ai`
    - Run `pytest` to confirm no test breaks from the rename
    - _Requirements: 2.1_

- [x] 3. Create new `aspice-check/` package skeleton
  - [x] 3.1 Create `aspice-check/` directory with `pyproject.toml`, `README.md`, `src/aspice_check/__init__.py`, `src/aspice_check/py.typed`, and `tests/` subdirectories
    - `pyproject.toml` declares `name = "aspice-check"`, description as orchestrator, dependencies on `confluence-ai` and `aspice-eval`, `"Typing :: Typed"` classifier
    - Leave `__init__.py` with version only — this package has no re-export surface
    - _Requirements: 1.5, 2.5, 2.6, 21.3, 21.6_

  - [x] 3.2 Add `[project.scripts]` entries for `aspice-analyze = "aspice_check.pipeline:analyze"` and `aspice-mcp = "aspice_check.mcp_server:main"`
    - Stub out `pipeline.py` and `mcp_server.py` with `def analyze(): ...` / `def main(): ...` placeholders that raise `NotImplementedError`
    - _Requirements: 17.1, 19.3_

- [x] 4. confluence-ai — extension point ABCs and registries
  - [x] 4.1 Promote `ImageDescriber` to a proper ABC in `confluence_ai/describer.py`
    - Ensure class inherits `abc.ABC` and `describe()` is decorated `@abstractmethod`
    - Provide a default sequential `describe_batch()` implementation
    - _Requirements: 9.3_

  - [x] 4.2 Create `confluence_ai/output_renderer.py` with `OutputRenderer` ABC and `register_renderer()` registry
    - Module-level `_RENDERERS: dict[str, type[OutputRenderer]]`
    - `register_renderer(format_name, cls)` validates `issubclass(cls, OutputRenderer)` and raises `TypeError` otherwise; logs warning on overwrite
    - `get_renderer(format_name)` helper raises a clear error listing registered formats
    - _Requirements: 8.1, 8.3, 8.4, 8.5_

  - [x] 4.3 Refactor `confluence_ai/renderer.py` so `MarkdownRenderer` subclasses `OutputRenderer`
    - Register as `"markdown"` at import time
    - _Requirements: 8.1_

  - [x] 4.4 Add built-in `confluence_ai/json_renderer.py` with `JSONRenderer(OutputRenderer)`
    - Outputs IR node tree as structured JSON
    - Register as `"json"` at import time
    - _Requirements: 8.2_

  - [x] 4.5 Write property test `test_prop11_renderer_type.py`
    - **Property 11: OutputRenderer Type Validation**
    - **Validates: Requirements 8.4**

  - [x] 4.6 Write property test `test_prop12_unregistered_format.py`
    - **Property 12: Unregistered Format Error Lists Available Formats**
    - **Validates: Requirements 8.5**

- [x] 5. confluence-ai — describer registration and factory
  - [x] 5.1 Add `register_describer()` to `confluence_ai/providers/__init__.py`
    - Accepts class or fully-qualified path string
    - Validates `issubclass(..., ImageDescriber)` when a class object is provided and raises `TypeError` naming `ImageDescriber`
    - Logs warning when overwriting a built-in provider
    - _Requirements: 9.1, 9.2, 9.5, 9.6, 20.5_

  - [x] 5.2 Update `create_describer()` in `confluence_ai/providers/__init__.py` with explicit return type annotation `-> ImageDescriber`
    - Raise `ImageDescriptionError` listing all registered provider names (including custom) on unknown provider
    - _Requirements: 10.1, 10.2, 20.3_

  - [x] 5.3 Write property test `test_prop07_describer_roundtrip.py`
    - **Property 7: Describer Registration Round-Trip**
    - **Validates: Requirements 9.2, 9.4**

  - [x] 5.4 Write property test `test_prop08_describer_type.py`
    - **Property 8: Describer Type Validation**
    - **Validates: Requirements 9.6, 20.5**

  - [x] 5.5 Write property test `test_prop18_describer_error.py`
    - **Property 18: Unknown Describer Provider Error Message**
    - **Validates: Requirements 20.3**

- [x] 6. confluence-ai — `export_page` convenience function
  - [x] 6.1 Add `ExportResult` and ensure `ImageContext`, `PageMetadata`, `ImageDescriberConfig` dataclasses exist in `confluence_ai/models.py`
    - Add `ParsedURL` if not already present
    - _Requirements: 4.1, 6.3_

  - [x] 6.2 Create `confluence_ai/url_parser.py` with `URLParser` class and `parse()` method returning `ParsedURL`
    - Raise `InvalidURLError` for strings not matching Confluence Cloud URL pattern
    - _Requirements: 6.7_

  - [x] 6.3 Create `confluence_ai/export.py` with `export_page()` convenience function
    - Full type annotations on parameters and return type
    - Validates credentials up front and raises `AuthenticationError` naming the missing field
    - Validates URL via `URLParser` and raises `InvalidURLError` on failure
    - Looks up renderer via `register_renderer` registry; raises listing formats on unknown
    - Orchestrates `ConfluenceClient` → `StorageFormatParser` → `AssetDownloader` → optional `ImageDescriber` → `OutputRenderer`
    - Resolves user-mention account IDs to display names; falls back to account ID and appends a warning to `ExportResult` on API failure
    - Returns `ExportResult`
    - Docstring includes a complete "Examples" section
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 22.6, 23.1, 23.2_

  - [x] 6.4 Write property test `test_prop05_credential_validation.py` (export side)
    - **Property 5: Credential Validation**
    - **Validates: Requirements 6.6, 6.7, 7.7**

  - [x] 6.5 Write property test `test_prop06_invalid_url.py`
    - **Property 6: Invalid URL Rejection**
    - **Validates: Requirements 6.7**

- [x] 7. confluence-ai — `publish_page` convenience function
  - [x] 7.1 Move publish logic out of `aspice_eval/analyze.py` into `confluence_ai/publish.py`
    - Extract HTML-to-storage-format conversion (Confluence conversion API)
    - Extract emoji sanitization helper
    - Extract title-based page deduplication (update vs create)
    - _Requirements: 3.6, 7.2, 7.3, 7.4_

  - [x] 7.2 Define `publish_page()` public function in `confluence_ai/publish.py`
    - Full type annotations on all parameters and return type `str`
    - Validates credentials up front and raises `AuthenticationError`
    - Returns URL of created/updated page
    - Docstring includes a complete "Examples" section
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.7, 22.6_

  - [x] 7.3 Write unit tests for `publish_page` in `tests/unit/test_publish.py`
    - Test credential validation, emoji sanitization, dedup-by-title (with mocked Confluence client)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.7_

- [x] 8. confluence-ai — populate public API `__init__.py`
  - [x] 8.1 Replace `confluence_ai/__init__.py` with full re-exports and `__all__`
    - Re-export: `ConfluenceClient`, `StorageFormatParser`, `MarkdownRenderer`, `AssetDownloader`, `ImageDescriber`, `URLParser`, `OutputRenderer`, `create_describer`, `register_describer`, `register_renderer`, `export_page`, `publish_page`, `ImageDescriberConfig`, `ImageContext`, `PageMetadata`, `ExportResult`
    - Re-export all exception classes from `confluence_ai.exceptions`
    - Define complete `__all__` list enumerating every public symbol
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 6.5, 7.6_

  - [x] 8.2 Write property test `test_prop02_api_completeness.py`
    - **Property 2: confluence-ai Public API Completeness**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

- [x] 9. Checkpoint — confluence-ai is self-contained
  - Ensure all tests pass, ask the user if questions arise.
  - _Verifies: Requirements 1.1, 1.2, 2.1, 2.2, 4.*, 6.*, 7.*, 8.*, 9.*, 10.*, 21.2, 21.5_

- [x] 10. aspice-eval — `KnowledgeBase.from_dict` and metadata flexibility
  - [x] 10.1 Add `KnowledgeBase.from_dict(data, *, standard="custom")` classmethod in `aspice_eval/knowledge_base.py`
    - Validates `data` against the criteria JSON Schema; raises `KBValidationError` on failure
    - Populates instance state so `get_criteria()` works without any filesystem access
    - Docstring includes an "Examples" section
    - _Requirements: 14.3, 14.4, 14.5, 22.6_

  - [x] 10.2 Ensure `KnowledgeBase` loads any subdirectory under `kb_path/` as a standard and that `_metadata.yaml` schema does not hard-code ASPICE-specific assumptions
    - Verify existing loader accepts arbitrary `standard` identifiers
    - _Requirements: 14.1, 14.2, 14.6_

  - [x] 10.3 Add `register_kb_loader(standard_name, loader_class)` for Level-3 KB extensibility
    - Stored in a module-level registry consulted by the convenience layer when a custom loader is registered for a standard
    - _Requirements: Design "KnowledgeBase Extensibility" Level 3_

  - [x] 10.4 Write property test `test_prop14_kb_from_dict.py`
    - **Property 14: KnowledgeBase.from_dict Round-Trip**
    - **Validates: Requirements 14.3, 14.4, 14.5**

- [x] 11. aspice-eval — `GapAnalysisEvaluator` ABC-ish + registration
  - [x] 11.1 Ensure `GapAnalysisEvaluator` in `aspice_eval/evaluator.py` documents `_call_model()` as the single override point and raises `NotImplementedError` in the base implementation
    - Keep `evaluate()` orchestration in the base class
    - _Requirements: 13.3_

  - [x] 11.2 Add `register_evaluator()` to `aspice_eval/providers/__init__.py`
    - Accepts class or fully-qualified path string
    - Validates `issubclass(..., GapAnalysisEvaluator)` when a class object is provided and raises `TypeError` naming `GapAnalysisEvaluator`
    - Logs warning when overwriting a built-in provider
    - _Requirements: 13.1, 13.2, 13.5, 13.6, 20.4_

  - [x] 11.3 Update `create_evaluator()` in `aspice_eval/providers/__init__.py` with explicit return type annotation `-> GapAnalysisEvaluator`
    - Raise `InvalidConfigError` listing all registered provider names (including custom) on unknown provider
    - _Requirements: 16.1, 16.2, 20.2_

  - [x] 11.4 Write property test `test_prop09_evaluator_roundtrip.py`
    - **Property 9: Evaluator Registration Round-Trip**
    - **Validates: Requirements 13.2, 13.4**

  - [x] 11.5 Write property test `test_prop10_evaluator_type.py`
    - **Property 10: Evaluator Type Validation**
    - **Validates: Requirements 13.6, 20.4**

  - [x] 11.6 Write property test `test_prop17_unknown_provider.py`
    - **Property 17: Unknown Evaluator Provider Error Message**
    - **Validates: Requirements 20.2**

- [x] 12. aspice-eval — `ReportRenderer` ABC and renderer-backed `ReportGenerator`
  - [x] 12.1 Create `aspice_eval/report_renderer.py` with `ReportRenderer` ABC and `register_renderer()` registry
    - `render()` signature: `(evaluation, levels, config, kb_metadata) -> str`
    - `register_renderer()` validates subclass and raises `TypeError` on mismatch
    - _Requirements: 15.1, 15.2, 15.6_

  - [x] 12.2 Refactor `aspice_eval/report_generator.py` so Markdown and HTML renderers are `ReportRenderer` subclasses registered by default
    - `ReportGenerator.generate(..., output_format=name)` delegates to the registered renderer
    - Raise `UnsupportedFormatError` listing registered formats for unknown name
    - _Requirements: 15.3, 15.4, 15.5_

  - [x] 12.3 Write property test `test_prop15_renderer_delegation.py`
    - **Property 15: Report Renderer Delegation**
    - **Validates: Requirements 15.3, 15.5**

- [x] 13. aspice-eval — convenience functions
  - [x] 13.1 Create `aspice_eval/convenience.py` with `evaluate_sdp()` function
    - Full type annotations on parameters and return type `EvaluationResult`
    - Validates `sdp_path` and `kb_path` exist; raises `FileNotFoundError` identifying the missing path
    - Orchestrates `SDPIngester` → `KnowledgeBase.load(standard)` → `get_criteria` → `create_evaluator` → `evaluate` → `CapabilityLevelCalculator`
    - Consults `register_kb_loader` registry when a custom loader is registered for `standard`
    - Docstring includes a complete "Examples" section
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 22.6_

  - [x] 13.2 Add `validate_kb()` function to `aspice_eval/convenience.py`
    - Full type annotations on parameters and return type `ValidationResult`
    - Raises `FileNotFoundError` when `kb_path` does not exist
    - Docstring includes a complete "Examples" section
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 22.6_

  - [x] 13.3 Ensure `sdp_ingester.py` raises `UnsupportedFormatError` with actual extension, list of supported formats, and conversion suggestion
    - _Requirements: 20.1_

  - [x] 13.4 Write property test `test_prop13_path_not_found.py`
    - **Property 13: Non-Existent Path Raises FileNotFoundError**
    - **Validates: Requirements 11.5, 11.6, 12.5**

  - [x] 13.5 Write property test `test_prop16_unsupported_format.py`
    - **Property 16: Unsupported File Format Error Message**
    - **Validates: Requirements 20.1**

- [x] 14. aspice-eval — populate public API `__init__.py`
  - [x] 14.1 Replace `aspice_eval/__init__.py` with full re-exports and `__all__`
    - Re-export: `KnowledgeBase`, `GapAnalysisEvaluator`, `ReportRenderer`, `create_evaluator`, `register_evaluator`, `register_renderer`, `register_kb_loader`, `evaluate_sdp`, `validate_kb`, `ModelConfig`, `EvaluationConfig`, `EvaluationResult`, `CriteriaEntry`, `CriteriaRating`, `SDPDocument`, `CapabilityLevelResult`, `ValidationResult`
    - Re-export all exception classes from `aspice_eval.exceptions`
    - Define complete `__all__` list enumerating every public symbol
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 11.4, 12.4, 15.6_

  - [x] 14.2 Add `py.typed` marker at `aspice-eval/src/aspice_eval/py.typed` and `"Typing :: Typed"` classifier in `pyproject.toml`
    - _Requirements: 21.1, 21.4_

  - [x] 14.3 Remove the `[analyze]` optional extra and `confluence-exporter` / `atlassian-python-api` / `requests` entries from `aspice-eval/pyproject.toml` dependencies
    - Retain only dependencies needed for evaluation (pyyaml, jsonschema, click for CLI)
    - _Requirements: 1.6, 1.7_

  - [x] 14.4 Write property test `test_prop03_api_completeness.py`
    - **Property 3: aspice-eval Public API Completeness**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

- [x] 15. Checkpoint — aspice-eval is standalone (no Confluence deps)
  - Ensure all tests pass, ask the user if questions arise.
  - _Verifies: Requirements 1.3, 1.4, 1.6, 1.7, 5.*, 11.*, 12.*, 13.*, 14.*, 15.*, 16.*, 20.1, 20.2, 21.1, 21.4_

- [x] 16. aspice-check — move `analyze.py` into pipeline CLI
  - [x] 16.1 Move `aspice-eval/src/aspice_eval/analyze.py` to `aspice-check/src/aspice_check/pipeline.py`
    - Strip out the re-implemented publish logic (now in `confluence_ai.publish_page`)
    - Replace direct Confluence client usage with `confluence_ai.export_page()` and `confluence_ai.publish_page()`
    - Replace direct evaluator wiring with `aspice_eval.evaluate_sdp()`
    - Use only top-level imports: `import confluence_ai`, `import aspice_eval` (never submodule imports)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 17.1, 17.2, 17.3, 17.4_

  - [x] 16.2 Translate `confluence_ai` and `aspice_eval` exceptions into stage-labelled CLI error output
    - Identify which stage (export, evaluate, publish) raised, show error and a resolution suggestion
    - No custom exception classes in `aspice_check`
    - _Requirements: 17.6_

  - [x] 16.3 Wire `aspice-analyze` CLI entry point in `aspice-check/pyproject.toml` to `aspice_check.pipeline:analyze`
    - Accept page URL, credentials, AI model config, optional evaluation parameters as CLI args / env vars
    - _Requirements: 17.1, 17.5_

  - [x] 16.4 Remove the `aspice-analyze` script entry from `aspice-eval/pyproject.toml` and delete the old `aspice_eval/analyze.py`
    - _Requirements: 1.6, 17.1_

  - [x] 16.5 Write property test `test_prop04_top_level_imports.py`
    - **Property 4: aspice-check Uses Only Top-Level Imports**
    - **Validates: Requirements 3.4, 3.5**

  - [x] 16.6 Write property test `test_prop01_package_isolation.py`
    - **Property 1: Package Isolation**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4**

- [x] 17. aspice-check — MCP server
  - [x] 17.1 Create `aspice_check/mcp_tools.py` with JSON Schema declarations for all five tools
    - `EVALUATE_SDP_SCHEMA`, `VALIDATE_KB_SCHEMA`, `LIST_STANDARDS_SCHEMA`, `EXPORT_PAGE_SCHEMA`, `DESCRIBE_IMAGE_SCHEMA`
    - Follow the schemas verbatim from the design
    - _Requirements: 18.2, 18.3, 18.4, 18.5, 18.6, 19.4_

  - [x] 17.2 Create `aspice_check/mcp_server.py` with `AspiceMCPServer` class implementing stdio JSON-RPC transport
    - Tool router dispatches to `_handle_evaluate_sdp`, `_handle_validate_kb`, `_handle_list_standards`, `_handle_export_page`, `_handle_describe_image`
    - Handlers call only top-level `confluence_ai` / `aspice_eval` APIs
    - Log available tools and transport on startup
    - _Requirements: 18.1, 19.1, 19.2, 19.5_

  - [x] 17.3 Validate MCP tool parameters against declared JSON Schemas and return structured `{"error": {"code": -32602, ...}}` responses on validation failure or unknown provider
    - Error `data` field includes `tool`, `parameter`, `actual_value`, `valid_values`, and `suggestion` where applicable
    - _Requirements: 18.7_

  - [x] 17.4 Wire `aspice-mcp` CLI entry point to `aspice_check.mcp_server:main`
    - `main()` parses args and starts `AspiceMCPServer().run()`
    - _Requirements: 19.3_

  - [x] 17.5 Write property test `test_prop19_mcp_errors.py`
    - **Property 19: MCP Invalid Parameter Error Response**
    - **Validates: Requirements 18.7**

- [x] 18. Documentation — library-first READMEs
  - [x] 18.1 Rewrite `confluence-ai/README.md`
    - Lead with "Library Usage" section with `export_page` / `publish_page` examples before any CLI section
    - Add "Extension Points" section covering custom `ImageDescriber` and custom `OutputRenderer` registration
    - Remove all ASPICE references from the introduction/primary description
    - _Requirements: 2.3, 22.1, 22.3_

  - [x] 18.2 Rewrite `aspice-eval/README.md`
    - Lead with "Library Usage" section with `evaluate_sdp` / `validate_kb` examples before any CLI section
    - Add "Extension Points" section covering custom evaluators, custom KB standards (all three levels), and custom report renderers
    - _Requirements: 22.2, 22.4_

  - [x] 18.3 Write `aspice-check/README.md`
    - Document `aspice-analyze` pipeline CLI usage
    - Document `aspice-mcp` server configuration, transport, and tool inventory
    - _Requirements: 22.5_

- [x] 19. Final checkpoint — run all tests across all three packages
  - Run `pytest` from each package root
  - Confirm no cross-package import-time dependencies in `confluence_ai` or `aspice_eval`
  - Confirm `aspice_check` imports only `confluence_ai` and `aspice_eval` (top-level)
  - Ensure all tests pass, ask the user if questions arise.
  - _Verifies: Requirements 1.*, 3.*, 17.*, 18.*, 19.*, 22.*_

## Notes

- Sub-tasks marked with `*` are optional property / unit tests and can be skipped for a faster MVP.
- Each task references specific requirements for traceability.
- Property-based test sub-tasks sit next to the feature they validate so regressions surface early.
- Checkpoints (tasks 9, 15, 19) are natural review points — each corresponds to one package becoming self-contained.
- The migration order is deliberate: `confluence-ai` first (it has no cross-package deps), then `aspice-eval` (same), then `aspice-check` (which depends on both).
- All 19 correctness properties from the design document are covered, each in its own optional sub-task annotated with property number and validated requirements.
