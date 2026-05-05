# Requirements Document

## Introduction

This specification defines the public API surface and package architecture for a three-package monorepo: `confluence-ai` (general-purpose AI-powered Confluence toolkit), `aspice-eval` (standalone ASPICE evaluation engine), and `aspice-check` (orchestrator composing both). The goal is clean separation of concerns — each package has standalone value, clear extension points, and a library-first identity.

## Glossary

- **Confluence_AI_Package**: The `confluence-ai` Python package (PyPI: `confluence-ai`, import: `confluence_ai`) providing AI-powered Confluence page export, publishing, and image transcription. It is domain-agnostic and does not reference ASPICE.
- **Aspice_Eval_Package**: The `aspice-eval` Python package (PyPI: `aspice-eval`, import: `aspice_eval`) providing ASPICE evaluation capabilities: KB loading, SDP evaluation, capability level calculation, and report generation. It has no Confluence dependencies.
- **Aspice_Check_Package**: The `aspice-check` Python package (PyPI: `aspice-check`, import: `aspice_check`) providing the orchestrator: the `aspice-analyze` CLI pipeline and the `aspice-mcp` MCP server. It depends on both `confluence-ai` and `aspice-eval`.
- **Public_API**: The set of symbols exported from a package's top-level `__init__.py` module, accessible via `from package_name import symbol`.
- **Convenience_Function**: A high-level function that orchestrates multiple internal components into a single callable for common workflows.
- **Factory_Function**: A function that creates and returns an instance of a class based on configuration parameters.
- **Extension_Point**: A documented interface (abstract base class or registry) that allows users to plug in custom implementations.
- **Provider_Registry**: A dictionary mapping provider names to fully-qualified class paths, supporting lazy imports and user registration.
- **KnowledgeBase**: The class that loads, validates, and queries criteria from YAML files for any supported standard.
- **GapAnalysisEvaluator**: The base class for AI-powered evaluators that assess SDP compliance against KB criteria.
- **ImageDescriber**: The abstract base class for AI-powered image description providers.
- **ReportRenderer**: An abstract base class for rendering evaluation results into output formats.
- **OutputRenderer**: An abstract base class for rendering Confluence page content into output formats (Markdown, JSON, etc.).
- **MCP_Server**: A Model Context Protocol server that exposes programmatic capabilities as tools callable by AI assistants.
- **MCP_Tool**: A single callable operation exposed by the MCP server, with a defined input schema and output format.
- **KB_Standard**: A set of criteria files under a named subdirectory of the knowledge base (e.g., `aspice/`, `iso26262/`).
- **Type_Annotation**: Python type hints on function signatures that enable IDE autocomplete and static analysis.
- **Re-export**: Making an internal symbol available from a higher-level module via explicit import in `__init__.py` and inclusion in `__all__`.

## Requirements

### Requirement 1: Three-Package Architecture Boundaries

**User Story:** As a maintainer, I want clear package boundaries with enforced dependency rules, so that each package can evolve independently and retain standalone value.

#### Acceptance Criteria

1. THE Confluence_AI_Package SHALL have zero import-time dependencies on the Aspice_Eval_Package.
2. THE Confluence_AI_Package SHALL have zero import-time dependencies on the Aspice_Check_Package.
3. THE Aspice_Eval_Package SHALL have zero import-time dependencies on the Confluence_AI_Package.
4. THE Aspice_Eval_Package SHALL have zero import-time dependencies on the Aspice_Check_Package.
5. THE Aspice_Check_Package SHALL declare both `confluence-ai` and `aspice-eval` as core dependencies in its `pyproject.toml`.
6. THE Aspice_Eval_Package SHALL NOT list `confluence-ai`, `atlassian-python-api`, or any Confluence client library in its dependencies or optional extras.
7. THE Aspice_Eval_Package SHALL NOT define an `[analyze]` optional extra.

### Requirement 2: Package Naming and Identity

**User Story:** As a developer discovering these packages, I want each package to have a clear, self-contained identity, so that I understand what each one does without needing to know the others exist.

#### Acceptance Criteria

1. THE Confluence_AI_Package SHALL use `confluence-ai` as its PyPI distribution name and `confluence_ai` as its Python import name.
2. THE Confluence_AI_Package description in `pyproject.toml` SHALL describe general-purpose AI-powered Confluence page export, publishing, and image transcription without mentioning ASPICE.
3. THE Confluence_AI_Package README SHALL present itself as a general-purpose AI-powered Confluence toolkit without mentioning ASPICE in its introduction or primary description.
4. THE Aspice_Eval_Package SHALL use `aspice-eval` as its PyPI distribution name and `aspice_eval` as its Python import name.
5. THE Aspice_Check_Package SHALL use `aspice-check` as its PyPI distribution name and `aspice_check` as its Python import name.
6. THE Aspice_Check_Package description in `pyproject.toml` SHALL describe itself as an orchestrator composing Confluence AI and ASPICE evaluation into a pipeline CLI and MCP server.

### Requirement 3: Interface Contracts Between Packages

**User Story:** As a developer using the orchestrator, I want clean, documented interfaces between the three packages, so that I can understand the integration boundaries.

#### Acceptance Criteria

1. THE Aspice_Check_Package SHALL call `confluence_ai.export_page()` for Confluence page export operations.
2. THE Aspice_Check_Package SHALL call `confluence_ai.publish_page()` for Confluence page publishing operations.
3. THE Aspice_Check_Package SHALL call `aspice_eval.evaluate_sdp()` for SDP evaluation operations.
4. THE Aspice_Check_Package SHALL NOT import any internal modules from `confluence_ai` other than the top-level Public_API symbols.
5. THE Aspice_Check_Package SHALL NOT import any internal modules from `aspice_eval` other than the top-level Public_API symbols.
6. ALL Confluence I/O (reading pages, downloading attachments, publishing pages) SHALL be owned by the Confluence_AI_Package — the Aspice_Check_Package SHALL NOT directly use `atlassian-python-api` or any other Confluence client library.

### Requirement 4: confluence-ai Public API Re-exports

**User Story:** As a developer integrating confluence-ai as a library, I want to import key classes and functions directly from `confluence_ai`, so that I do not need to know the internal module structure.

#### Acceptance Criteria

1. THE Confluence_AI_Package SHALL export the following symbols from its top-level `__init__.py`: `ConfluenceClient`, `StorageFormatParser`, `MarkdownRenderer`, `AssetDownloader`, `ImageDescriber`, `create_describer`, `register_describer`, `export_page`, `publish_page`, `URLParser`, `ImageDescriberConfig`, `PageMetadata`, `ExportResult`.
2. THE Confluence_AI_Package SHALL export all custom exception classes (`ExporterError`, `InvalidURLError`, `AuthenticationError`, `ConfluenceConnectionError`, `PageNotFoundError`, `ParseError`, `DownloadError`, `ImageDescriptionError`, `FileSystemError`) from its top-level `__init__.py`.
3. THE Confluence_AI_Package SHALL define an `__all__` list in its top-level `__init__.py` that enumerates every public symbol.
4. WHEN a developer imports a symbol from `confluence_ai` that is listed in `__all__`, THE Confluence_AI_Package SHALL resolve the import without raising `ImportError`.

### Requirement 5: aspice-eval Public API Re-exports

**User Story:** As a developer integrating aspice-eval as a library, I want to import key classes and functions directly from `aspice_eval`, so that I do not need to know the internal module structure.

#### Acceptance Criteria

1. THE Aspice_Eval_Package SHALL export the following symbols from its top-level `__init__.py`: `KnowledgeBase`, `GapAnalysisEvaluator`, `ReportRenderer`, `create_evaluator`, `register_evaluator`, `register_renderer`, `evaluate_sdp`, `validate_kb`, `ModelConfig`, `EvaluationConfig`, `EvaluationResult`, `CriteriaEntry`, `CriteriaRating`, `SDPDocument`, `CapabilityLevelResult`, `ValidationResult`.
2. THE Aspice_Eval_Package SHALL export all custom exception classes (`KBValidationError`, `UnsupportedFormatError`, `InvalidConfigError`, `AIModelError`, `AIResponseParseError`) from its top-level `__init__.py`.
3. THE Aspice_Eval_Package SHALL define an `__all__` list in its top-level `__init__.py` that enumerates every public symbol.
4. WHEN a developer imports a symbol from `aspice_eval` that is listed in `__all__`, THE Aspice_Eval_Package SHALL resolve the import without raising `ImportError`.

### Requirement 6: Convenience Function — export_page

**User Story:** As a developer, I want a single function call to export a Confluence page to a chosen output format, so that I do not need to manually wire together URLParser, ConfluenceClient, StorageFormatParser, AssetDownloader, ImageDescriber, and OutputRenderer.

#### Acceptance Criteria

1. THE Confluence_AI_Package SHALL provide a Convenience_Function named `export_page` that accepts a Confluence page URL, an output directory path, Confluence credentials (email and API token), and optional AI description configuration.
2. THE `export_page` function SHALL accept an optional `output_format` parameter defaulting to `"markdown"`.
3. WHEN `export_page` is called with valid parameters, THE Confluence_AI_Package SHALL return an `ExportResult` containing the output file path, image count, description count, and any warnings.
4. THE `export_page` function SHALL have complete Type_Annotations on all parameters and the return type.
5. THE `export_page` function SHALL be exported from the top-level `confluence_ai` module.
6. IF Confluence credentials are missing or empty, THEN THE `export_page` function SHALL raise `AuthenticationError` with a message indicating which credential is missing.
7. IF the page URL is invalid, THEN THE `export_page` function SHALL raise `InvalidURLError`.

### Requirement 7: Convenience Function — publish_page

**User Story:** As a developer, I want a single function call to publish content to Confluence, so that I do not need to manage authentication, format conversion, and page deduplication manually.

#### Acceptance Criteria

1. THE Confluence_AI_Package SHALL provide a Convenience_Function named `publish_page` that accepts HTML content, Confluence credentials, a space key, a page title, and an optional parent page ID, and returns the URL of the created or updated page.
2. THE `publish_page` function SHALL handle HTML-to-storage-format conversion internally using the Confluence conversion API.
3. THE `publish_page` function SHALL handle emoji sanitization (stripping unsupported Unicode characters) before publishing.
4. THE `publish_page` function SHALL detect existing pages by title and update them rather than creating duplicates.
5. THE `publish_page` function SHALL have complete Type_Annotations on all parameters and the return type.
6. THE `publish_page` function SHALL be exported from the top-level `confluence_ai` module and included in `__all__`.
7. IF Confluence credentials are missing or empty, THEN THE `publish_page` function SHALL raise `AuthenticationError` with a message indicating which credential is missing.

### Requirement 8: Pluggable Output Renderers for confluence-ai

**User Story:** As a developer, I want to export Confluence pages to formats beyond Markdown (e.g., JSON IR, reStructuredText), so that I can integrate with different documentation pipelines.

#### Acceptance Criteria

1. THE Confluence_AI_Package SHALL support pluggable output renderers via a registry pattern, with Markdown as the default renderer.
2. THE Confluence_AI_Package SHALL provide a built-in `"json"` renderer that outputs the IR node tree as structured JSON, enabling programmatic consumption without Markdown parsing.
3. THE Confluence_AI_Package SHALL provide a `register_renderer` function for registering custom OutputRenderer implementations.
4. THE `register_renderer` function SHALL validate that the provided class is a subclass of `OutputRenderer` and raise `TypeError` if not.
5. WHEN an unregistered format name is passed to `export_page`, THE Confluence_AI_Package SHALL raise an error listing all available format names.

### Requirement 9: Custom Image Describer Extension Point

**User Story:** As a developer, I want to plug in my own image description provider (e.g., a local model or a proprietary vision API), so that I can use custom AI services for diagram transcription.

#### Acceptance Criteria

1. THE Confluence_AI_Package SHALL provide a `register_describer` function that accepts a provider name string and a fully-qualified class path or class object.
2. WHEN `register_describer` is called with a valid provider name and class, THE Provider_Registry SHALL include the new provider so that `create_describer` can instantiate it.
3. THE `ImageDescriber` abstract base class SHALL document the `describe` method as the single override point for custom providers.
4. WHEN a custom describer is registered and an `ImageDescriberConfig` with that provider name is passed to `create_describer`, THE Factory_Function SHALL instantiate the custom describer class.
5. IF a provider name is registered that conflicts with a built-in provider, THEN THE `register_describer` function SHALL overwrite the built-in entry and log a warning.
6. THE `register_describer` function SHALL validate that the provided class is a subclass of `ImageDescriber` and raise `TypeError` if not.

### Requirement 10: Factory Return Type Annotations for confluence-ai

**User Story:** As a developer using an IDE, I want factory functions to have explicit return type annotations, so that I get autocomplete and type checking on the returned objects.

#### Acceptance Criteria

1. THE `create_describer` Factory_Function SHALL declare its return type as `ImageDescriber`.
2. WHEN a developer calls `create_describer` in an IDE with type checking enabled, THE IDE SHALL resolve the return type to `ImageDescriber` and provide method autocomplete.

### Requirement 11: Convenience Function — evaluate_sdp

**User Story:** As a developer, I want a single function call to evaluate an SDP document against criteria, so that I do not need to manually wire together KnowledgeBase, SDPIngester, create_evaluator, CapabilityLevelCalculator, and ReportGenerator.

#### Acceptance Criteria

1. THE Aspice_Eval_Package SHALL provide a Convenience_Function named `evaluate_sdp` that accepts an SDP file path, a `ModelConfig`, and optional evaluation parameters (target level, process groups, knowledge base path, standard).
2. WHEN `evaluate_sdp` is called with valid parameters, THE Aspice_Eval_Package SHALL return an `EvaluationResult` containing per-criteria ratings, capability level results, and token usage metadata.
3. THE `evaluate_sdp` function SHALL have complete Type_Annotations on all parameters and the return type.
4. THE `evaluate_sdp` function SHALL be exported from the top-level `aspice_eval` module.
5. IF the SDP file path does not exist, THEN THE `evaluate_sdp` function SHALL raise `FileNotFoundError` with a message identifying the missing path.
6. IF the knowledge base path does not exist, THEN THE `evaluate_sdp` function SHALL raise `FileNotFoundError` with a message identifying the missing path.

### Requirement 12: Convenience Function — validate_kb

**User Story:** As a developer, I want a single function call to validate a knowledge base directory, so that I can check custom KB files programmatically without invoking the CLI.

#### Acceptance Criteria

1. THE Aspice_Eval_Package SHALL provide a Convenience_Function named `validate_kb` that accepts a knowledge base path and an optional standard name.
2. WHEN `validate_kb` is called with a valid KB path, THE Aspice_Eval_Package SHALL return a `ValidationResult` containing schema errors, completeness gaps, and warnings.
3. THE `validate_kb` function SHALL have complete Type_Annotations on all parameters and the return type.
4. THE `validate_kb` function SHALL be exported from the top-level `aspice_eval` module.
5. IF the knowledge base path does not exist, THEN THE `validate_kb` function SHALL raise `FileNotFoundError`.

### Requirement 13: Custom Evaluator Extension Point

**User Story:** As a developer, I want to plug in my own LLM provider or rule-based evaluator by subclassing `GapAnalysisEvaluator`, so that I can use proprietary models or deterministic evaluation logic.

#### Acceptance Criteria

1. THE Aspice_Eval_Package SHALL provide a `register_evaluator` function that accepts a provider name string and a fully-qualified class path or class object.
2. WHEN `register_evaluator` is called with a valid provider name and class, THE Provider_Registry SHALL include the new provider so that `create_evaluator` can instantiate it.
3. THE `GapAnalysisEvaluator` base class SHALL document the `_call_model` method as the single override point for custom providers.
4. WHEN a custom evaluator is registered and a `ModelConfig` with that provider name is passed to `create_evaluator`, THE Factory_Function SHALL instantiate the custom evaluator class.
5. IF a provider name is registered that conflicts with a built-in provider, THEN THE `register_evaluator` function SHALL overwrite the built-in entry and log a warning.
6. THE `register_evaluator` function SHALL validate that the provided class is a subclass of `GapAnalysisEvaluator` and raise `TypeError` if not.

### Requirement 14: Custom Knowledge Base Standards

**User Story:** As a developer, I want to use the evaluation engine with standards beyond ASPICE (ISO 26262, CMMI, etc.), so that I can reuse the gap analysis infrastructure for different compliance frameworks.

#### Acceptance Criteria

1. THE KnowledgeBase class SHALL load criteria from any subdirectory under the KB root path, treating the subdirectory name as the KB_Standard identifier.
2. THE KnowledgeBase class SHALL validate criteria files against the same JSON Schema regardless of the standard name.
3. THE KnowledgeBase class SHALL provide an alternative constructor named `from_dict` that accepts pre-loaded criteria data as a Python dictionary, enabling in-memory KB construction without filesystem access.
4. WHEN `KnowledgeBase.from_dict` is called with a valid criteria dictionary, THE KnowledgeBase SHALL be usable for querying criteria without requiring any filesystem path.
5. IF the provided dictionary fails schema validation, THEN THE KnowledgeBase SHALL raise `KBValidationError` with details about the validation failure.
6. THE `_metadata.yaml` schema SHALL support arbitrary standard names, versions, and process group definitions without ASPICE-specific assumptions.

### Requirement 15: Custom Report Renderer Extension Point

**User Story:** As a developer, I want to register custom report renderers (JSON, SARIF, CSV, etc.) beyond the built-in Markdown and HTML, so that I can integrate evaluation results into my existing toolchain.

#### Acceptance Criteria

1. THE Aspice_Eval_Package SHALL define a `ReportRenderer` abstract base class with a `render` method that accepts an `EvaluationResult`, capability levels, config, and KB metadata, and returns a string.
2. THE Aspice_Eval_Package SHALL provide a `register_renderer` function that accepts a format name string and a `ReportRenderer` subclass or factory callable.
3. WHEN a custom renderer is registered and the corresponding format name is passed to `ReportGenerator.generate`, THE ReportGenerator SHALL delegate rendering to the custom renderer.
4. THE built-in Markdown and HTML renderers SHALL be implemented as `ReportRenderer` subclasses registered by default.
5. IF an unregistered format name is passed to `ReportGenerator.generate`, THEN THE ReportGenerator SHALL raise `UnsupportedFormatError` listing all registered format names.
6. THE `ReportRenderer` base class SHALL be exported from the top-level `aspice_eval` module.

### Requirement 16: Factory Return Type Annotations for aspice-eval

**User Story:** As a developer using an IDE, I want factory functions to have explicit return type annotations, so that I get autocomplete and type checking on the returned objects.

#### Acceptance Criteria

1. THE `create_evaluator` Factory_Function SHALL declare its return type as `GapAnalysisEvaluator`.
2. WHEN a developer calls `create_evaluator` in an IDE with type checking enabled, THE IDE SHALL resolve the return type to `GapAnalysisEvaluator` and provide method autocomplete.

### Requirement 17: aspice-check Pipeline CLI

**User Story:** As a user, I want a single CLI command that exports a Confluence SDP page, evaluates it against ASPICE criteria, and publishes the report back to Confluence, so that I can run the full pipeline without scripting multiple tools.

#### Acceptance Criteria

1. THE Aspice_Check_Package SHALL provide a CLI entry point named `aspice-analyze` that orchestrates the full pipeline: export, evaluate, publish.
2. THE `aspice-analyze` command SHALL call `confluence_ai.export_page()` for the export stage.
3. THE `aspice-analyze` command SHALL call `aspice_eval.evaluate_sdp()` for the evaluation stage.
4. THE `aspice-analyze` command SHALL call `confluence_ai.publish_page()` for the publish stage.
5. THE `aspice-analyze` command SHALL accept Confluence page URL, credentials, AI model configuration, and optional evaluation parameters as CLI arguments or environment variables.
6. IF any pipeline stage fails, THEN THE `aspice-analyze` command SHALL report the failure with the stage name, error details, and a suggestion for resolution.

### Requirement 18: aspice-check MCP Server — Tool Exposure

**User Story:** As an AI assistant developer, I want to call ASPICE evaluation and Confluence export capabilities as MCP tools, so that AI agents can perform gap analysis without CLI invocation.

#### Acceptance Criteria

1. THE Aspice_Check_Package SHALL provide an MCP server that exposes tools from both the Confluence_AI_Package and the Aspice_Eval_Package.
2. THE MCP_Server SHALL expose an `evaluate_sdp` tool that accepts SDP content (as text or file path), model configuration, and evaluation parameters, and returns structured evaluation results.
3. THE MCP_Server SHALL expose a `validate_kb` tool that accepts a knowledge base path and returns validation results.
4. THE MCP_Server SHALL expose a `list_standards` tool that returns available KB standards and their process groups.
5. THE MCP_Server SHALL expose an `export_page` tool that accepts a Confluence page URL, credentials, and optional AI description configuration, and returns the exported content or file path.
6. THE MCP_Server SHALL expose a `describe_image` tool that accepts an image file path and context, and returns the AI-generated description text.
7. WHEN an MCP tool is called with invalid parameters, THE MCP_Server SHALL return a structured error response with actionable details.

### Requirement 19: aspice-check MCP Server — Configuration and Transport

**User Story:** As a developer deploying the MCP server, I want standard MCP transport support and clear configuration, so that I can integrate it with any MCP-compatible client.

#### Acceptance Criteria

1. THE MCP_Server SHALL support the stdio transport for local process communication.
2. THE MCP_Server SHALL be provided by the Aspice_Check_Package as a core capability (not an optional extra).
3. THE Aspice_Check_Package SHALL provide a CLI entry point named `aspice-mcp` for starting the MCP server.
4. THE MCP_Server SHALL declare tool schemas using the MCP protocol's JSON Schema format for parameter validation.
5. WHEN the MCP server starts, THE MCP_Server SHALL log its available tools and transport configuration.

### Requirement 20: Actionable Error Messages

**User Story:** As a developer, I want error messages to tell me what went wrong, what formats or values are valid, and how to fix the issue, so that I can resolve problems without searching documentation.

#### Acceptance Criteria

1. WHEN an unsupported file format is provided to the SDP ingester, THE Aspice_Eval_Package SHALL raise `UnsupportedFormatError` with a message that includes the actual file extension, the list of supported formats, and a suggestion for how to convert the document.
2. WHEN an unknown provider name is passed to `create_evaluator`, THE Aspice_Eval_Package SHALL raise `InvalidConfigError` with a message that lists all valid provider names including any registered custom providers.
3. WHEN an unknown provider name is passed to `create_describer`, THE Confluence_AI_Package SHALL raise `ImageDescriptionError` with a message that lists all valid provider names including any registered custom providers.
4. WHEN a custom evaluator class does not subclass `GapAnalysisEvaluator`, THE `register_evaluator` function SHALL raise `TypeError` with a message naming the expected base class.
5. WHEN a custom describer class does not subclass `ImageDescriber`, THE `register_describer` function SHALL raise `TypeError` with a message naming the expected base class.

### Requirement 21: Package Discoverability Metadata

**User Story:** As a developer evaluating whether to adopt these packages, I want the package metadata to clearly indicate that programmatic library use is supported, so that I can find the packages when searching for Confluence export or ASPICE evaluation libraries.

#### Acceptance Criteria

1. THE Aspice_Eval_Package SHALL include a `py.typed` marker file in its source directory to indicate PEP 561 type stub support.
2. THE Confluence_AI_Package SHALL include a `py.typed` marker file in its source directory to indicate PEP 561 type stub support.
3. THE Aspice_Check_Package SHALL include a `py.typed` marker file in its source directory to indicate PEP 561 type stub support.
4. THE Aspice_Eval_Package SHALL include `"Typing :: Typed"` in its PyPI classifiers in `pyproject.toml`.
5. THE Confluence_AI_Package SHALL include `"Typing :: Typed"` in its PyPI classifiers in `pyproject.toml`.
6. THE Aspice_Check_Package SHALL include `"Typing :: Typed"` in its PyPI classifiers in `pyproject.toml`.

### Requirement 22: Documentation — Library-First READMEs

**User Story:** As a developer adopting these packages, I want clear usage examples in the README and docstrings, so that I can get started quickly without reading source code.

#### Acceptance Criteria

1. THE Confluence_AI_Package README SHALL lead with a "Library Usage" section (programmatic API examples) before any "CLI Usage" section, establishing its primary identity as a library.
2. THE Aspice_Eval_Package README SHALL lead with a "Library Usage" section (programmatic API examples) before any "CLI Usage" section, establishing its primary identity as a library.
3. THE Confluence_AI_Package README SHALL include an "Extension Points" section documenting how to create custom image describers and custom output renderers.
4. THE Aspice_Eval_Package README SHALL include an "Extension Points" section documenting how to create custom evaluators, custom KB standards, and custom report renderers.
5. THE Aspice_Check_Package README SHALL document the pipeline CLI usage and MCP server configuration.
6. WHEN a Convenience_Function is called, THE function's docstring SHALL include a complete usage example in the "Examples" section.

### Requirement 23: User Mention Resolution

**User Story:** As a developer exporting Confluence pages, I want user mentions in page content to be resolved to display names, so that exported documents are readable without Confluence access.

#### Acceptance Criteria

1. WHEN a Confluence page contains user mentions (account ID references), THE Confluence_AI_Package SHALL resolve them to human-readable display names in the exported output.
2. IF a user mention cannot be resolved (API failure or unknown account), THEN THE Confluence_AI_Package SHALL fall back to the raw account ID and add a warning to the `ExportResult`.
