# Implementation Plan: ASPICE Knowledge Base & Agent Workflow

## Overview

This plan implements a Python CLI tool (`aspice-eval`) that pairs a structured YAML knowledge base of ASPICE evaluation criteria with an AI-powered agent workflow for SDP gap analysis. Implementation proceeds bottom-up: data models and schema first, then KB loading/validation, SDP ingestion, the AI evaluator, capability level calculation, report generation, and finally CLI wiring. Each step builds on the previous, ensuring no orphaned code.

**Base path:** All files are created under `aspice-eval/` at the workspace root (e.g., `aspice-eval/src/aspice_eval/`, `aspice-eval/knowledge_base/`, `aspice-eval/tests/`, etc.).

## Tasks

- [x] 1. Set up project structure, dependencies, and data models
  - [x] 1.1 Create Python package structure and configuration
    - Create `src/aspice_eval/` package directory with `__init__.py`
    - Create `pyproject.toml` with project metadata, dependencies (`pyyaml`, `jsonschema`, `click`, `hypothesis`), and entry point for `aspice-eval` CLI
    - Create `knowledge_base/schema/` and `knowledge_base/aspice/` directories
    - Create `tests/conftest.py` with Hypothesis settings profiles (ci: 100 examples, dev: 50)
    - _Requirements: 9.3, 9.4_

  - [x] 1.2 Define core data model classes
    - Create `src/aspice_eval/models.py` with dataclasses: `CriteriaEntry`, `CriteriaRating`, `CapabilityLevelResult`, `EvaluationResult`, `EvaluationConfig`, `ValidationResult`, `SDPDocument`, `KBMetadata`, `ModelConfig`, `CompletenessReport`
    - `EvaluationConfig` must default `target_capability_level` to 3 and `process_groups` to `["SWE", "SYS", "MAN", "SUP"]`
    - `CriteriaRating.rating` must be constrained to the four ASPICE rating values
    - _Requirements: 1.1, 1.2, 4.2, 7.1, 7.3_

  - [x] 1.3 Write property test for configuration validation (Property 15)
    - **Property 15: Configuration accepts all valid parameter combinations**
    - Generate random target levels (1–5) and non-empty subsets of supported process groups; verify `EvaluationConfig` accepts without error. Verify default target level is 3 when unspecified.
    - **Validates: Requirements 7.1, 7.3**

  - [x] 1.4 Write property test for rating value constraint (Property 5)
    - **Property 5: Rating values are constrained to the ASPICE rating scale**
    - Generate random `CriteriaRating` objects; verify `rating` field is one of "Fully achieved", "Largely achieved", "Partially achieved", "Not achieved".
    - **Validates: Requirements 4.2**

- [x] 2. Implement JSON Schema and Knowledge Base structure
  - [x] 2.1 Create JSON Schema for KB criteria files
    - Create `knowledge_base/schema/criteria_schema.json` matching the design specification
    - Schema must enforce required fields: `process_group` (with `code` and `name`), `criteria` array with required fields per entry (`process_id`, `process_name`, `capability_level`, `process_attribute`, `criteria_id`, `description`, `expected_evidence`, `evaluation_guidance`)
    - `expected_evidence` items must have `type` and `description` fields
    - _Requirements: 1.2, 1.5, 1.6_

  - [x] 2.2 Create KB metadata file
    - Create `knowledge_base/aspice/_metadata.yaml` with standard name, version (4.0), release date, source references, license note, process groups (SWE, SYS, MAN, SUP with their process IDs), capability levels (0–5 with process attributes), and rating scale
    - Include attribution references to publicly available ASPICE summaries
    - _Requirements: 2.3, 8.3, 9.1, 9.2_

  - [x] 2.3 Create SWE process group criteria file
    - Create `knowledge_base/aspice/swe.yaml` with criteria entries for SWE.1 through SWE.6 covering capability levels 1–5 and all applicable process attributes (PA 1.1 through PA 5.2)
    - Each entry must include: `process_id`, `process_name`, `capability_level`, `process_attribute`, `process_attribute_name`, `criteria_id`, `description`, `expected_evidence`, `evaluation_guidance`, `example_evidence`
    - Evidence descriptions must use ASPICE 4.0 "Information Items" terminology
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6_

  - [x] 2.4 Create SYS, MAN, and SUP process group criteria files
    - Create `knowledge_base/aspice/sys.yaml` for SYS.1–SYS.5
    - Create `knowledge_base/aspice/man.yaml` for MAN.3
    - Create `knowledge_base/aspice/sup.yaml` for SUP.1, SUP.8, SUP.9, SUP.10
    - All files follow the same schema and structure as `swe.yaml`
    - _Requirements: 1.1, 1.3, 1.4, 1.6_

- [x] 3. Implement KB Loader and Validator
  - [x] 3.1 Implement KB Validator
    - Create `src/aspice_eval/kb_validator.py` with `KBValidator` class
    - `validate_schema()`: validate a parsed YAML dict against `criteria_schema.json` using `jsonschema`; return list of `ValidationError`
    - `validate_completeness()`: check that every (process_group, capability_level, process_attribute) tuple has at least one criteria entry; return `CompletenessReport` listing gaps
    - Raise `KBValidationError` on schema failures
    - _Requirements: 8.1, 8.2_

  - [x] 3.2 Implement KnowledgeBase loader
    - Create `src/aspice_eval/knowledge_base.py` with `KnowledgeBase` class
    - `__init__(kb_path)`: store path, raise `FileNotFoundError` if path doesn't exist
    - `load(standard)`: load all YAML files for the standard directory, parse with PyYAML, validate each against schema
    - `validate()`: run schema + completeness validation, return `ValidationResult`
    - `get_criteria(process_groups, max_capability_level)`: filter and return matching `CriteriaEntry` objects
    - `get_metadata()`: load and return `_metadata.yaml` as `KBMetadata`
    - Include version metadata from `_metadata.yaml` (`kb_version` field)
    - _Requirements: 1.1, 1.5, 2.1, 2.2, 8.3_

  - [x] 3.3 Write property test for criteria filtering (Property 1)
    - **Property 1: Criteria filtering returns exactly matching entries**
    - Generate random criteria sets and filters (process groups, max level); verify `get_criteria` returns exactly entries matching both conditions.
    - **Validates: Requirements 1.1, 4.1**

  - [x] 3.4 Write property test for schema validation (Property 2)
    - **Property 2: Schema validation accepts complete entries and rejects incomplete entries**
    - Generate random criteria dicts with varying field presence; verify schema validation accepts complete entries and rejects incomplete ones.
    - **Validates: Requirements 1.2, 2.2**

  - [x] 3.5 Write property test for KB completeness validation (Property 14)
    - **Property 14: KB completeness validator identifies all missing criteria tuples**
    - Generate random criteria sets with deliberate gaps; verify validator reports exactly the missing (group, level, PA) tuples.
    - **Validates: Requirements 8.1, 8.2**

- [x] 4. Checkpoint — Verify KB and validation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement SDP Ingester
  - [x] 5.1 Implement SDPIngester class
    - Create `src/aspice_eval/sdp_ingester.py` with `SDPIngester` class
    - `ingest(sdp_path)`: read file, check extension is `.md`, return `SDPDocument` with raw content and structural metadata (extracted section headers)
    - Raise `UnsupportedFormatError` with descriptive message for non-Markdown files (`.docx`, `.pdf`, `.xlsx`, etc.)
    - Raise `FileNotFoundError` if file doesn't exist
    - Create custom exception `UnsupportedFormatError` in `src/aspice_eval/exceptions.py`
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 5.2 Write property test for Markdown acceptance (Property 3)
    - **Property 3: SDP ingester accepts any valid Markdown content**
    - Generate random Markdown strings; verify ingester accepts and returns `SDPDocument` with non-empty content.
    - **Validates: Requirements 3.1**

  - [x] 5.3 Write property test for unsupported format rejection (Property 4)
    - **Property 4: SDP ingester rejects unsupported formats with descriptive error**
    - Generate random non-Markdown file extensions; verify ingester raises `UnsupportedFormatError` with message identifying expected format.
    - **Validates: Requirements 3.3**

- [x] 6. Implement Gap Analysis Evaluator (AI Agent)
  - [x] 6.1 Implement GapAnalysisEvaluator class
    - Create `src/aspice_eval/evaluator.py` with `GapAnalysisEvaluator` class
    - `__init__(model_config)`: configure AI model provider and parameters
    - `evaluate(sdp, criteria, config)`: construct prompt with SDP content + KB criteria as context, send to AI model, parse response into `CriteriaRating` objects
    - Prompt must instruct the AI to: rate each criteria using the ASPICE rating scale, cite specific SDP sections as evidence, identify gaps, and provide remediation recommendations
    - Implement retry with exponential backoff (3 attempts) for `AIModelError`
    - Handle `AIResponseParseError` for malformed responses; allow partial results
    - Each `CriteriaRating` must have non-empty `recommendations` when `gaps` is non-empty
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 6.3_

  - [x] 6.2 Write property test for group coverage (Property 6)
    - **Property 6: Evaluation produces ratings for exactly the requested process groups**
    - Generate random group subsets and mock evaluation results; verify ratings cover every requested group and no unrequested groups.
    - **Validates: Requirements 4.4**

  - [x] 6.3 Write property test for gap-recommendation invariant (Property 10)
    - **Property 10: Ratings with gaps always have non-empty recommendations**
    - Generate random `CriteriaRating` objects with non-empty `gaps`; verify `recommendations` is also non-empty.
    - **Validates: Requirements 6.3**

- [x] 7. Implement Capability Level Calculator
  - [x] 7.1 Implement CapabilityLevelCalculator class
    - Create `src/aspice_eval/level_calculator.py` with `CapabilityLevelCalculator` class
    - `calculate(ratings, process_groups)`: aggregate per-criteria ratings into per-process-attribute ratings, then determine highest achieved level per group
    - Apply ASPICE cumulative rules: level N achieved only when ALL PAs at level N are "Largely achieved" or "Fully achieved" AND all lower levels are also achieved
    - Populate `blocking_attributes` with exactly those PAs at `achieved_level + 1` that are "Partially achieved" or "Not achieved"
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 7.2 Write property test for capability level calculation (Property 7)
    - **Property 7: Capability level calculation follows ASPICE cumulative achievement rules**
    - Generate random attribute rating maps; verify calculated level satisfies: all PAs at achieved level and below are L/F, and if below target, at least one PA at next level is P/N.
    - **Validates: Requirements 5.1, 5.2**

  - [x] 7.3 Write property test for blocking attributes (Property 8)
    - **Property 8: Blocking attributes are exactly the underachieving PAs at the next level**
    - Generate random below-target results; verify `blocking_attributes` contains exactly the PAs at `achieved_level + 1` rated P or N.
    - **Validates: Requirements 5.3**

- [x] 8. Checkpoint — Verify core evaluation pipeline
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement Report Generator
  - [x] 9.1 Implement ReportGenerator class
    - Create `src/aspice_eval/report_generator.py` with `ReportGenerator` class
    - `generate(evaluation, levels, config, kb_metadata)`: produce complete Markdown report
    - Report must include sections: Metadata, Executive Summary, Capability Level Summary (table), Detailed Findings (per-group, per-level, per-PA with ratings/evidence/gaps/recommendations), Remediation Roadmap, Traceability Matrix
    - Metadata section must include: SDP document path, target capability level, KB version, evaluation timestamp
    - Traceability Matrix must reference every `criteria_id` from the evaluation results
    - Detailed Findings must contain subsections only for the specified process groups
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.2_

  - [x] 9.2 Write property test for required report sections (Property 9)
    - **Property 9: Generated report contains all required sections**
    - Generate random evaluation results; verify report contains headers for "Executive Summary", "Capability Level Summary", "Detailed Findings", "Remediation Roadmap", "Traceability Matrix".
    - **Validates: Requirements 6.1, 6.2**

  - [x] 9.3 Write property test for traceability completeness (Property 11)
    - **Property 11: Traceability section references all evaluated criteria**
    - Generate random evaluation results; verify every `criteria_id` appears in the traceability section.
    - **Validates: Requirements 6.4**

  - [x] 9.4 Write property test for report metadata (Property 12)
    - **Property 12: Report metadata contains all required identification fields**
    - Generate random configs and metadata; verify report metadata includes SDP path, target level, KB version, and timestamp.
    - **Validates: Requirements 6.5**

  - [x] 9.5 Write property test for process group scoping in report (Property 13)
    - **Property 13: Report contains sections only for specified process groups**
    - Generate random group subsets; verify Detailed Findings contains only those groups.
    - **Validates: Requirements 7.2**

- [x] 10. Implement CLI entry point and wire components together
  - [x] 10.1 Implement CLI with Click
    - Create `src/aspice_eval/cli.py` with Click-based CLI
    - `evaluate` command: accepts `--sdp`, `--target-level` (default 3), `--groups` (default SWE,SYS,MAN,SUP), `--output`, `--kb-path` (default `knowledge_base`), `--model` (AI model name)
    - `validate-kb` command: accepts `--kb-path`, runs schema + completeness validation, prints results
    - `version` command: prints package version
    - Wire all components: KB Loader → SDP Ingester → Evaluator → Level Calculator → Report Generator
    - Validate inputs early (fail fast): check paths exist, validate config params before AI calls
    - Handle all error types from the design (FileNotFoundError, UnsupportedFormatError, KBValidationError, InvalidConfigError, AIModelError, AIResponseParseError) with user-friendly messages
    - _Requirements: 3.3, 7.1, 7.2, 7.3, 9.3_

  - [x] 10.2 Create exceptions module
    - Create `src/aspice_eval/exceptions.py` (if not already created in 5.1) with all custom exceptions: `KBValidationError`, `UnsupportedFormatError`, `InvalidConfigError`, `AIModelError`, `AIResponseParseError`
    - Each exception must carry structured context (file paths, field names, expected vs actual values)
    - _Requirements: 3.3_

  - [x] 10.3 Write unit tests for error handling
    - Test `FileNotFoundError` for missing SDP and KB paths
    - Test `UnsupportedFormatError` message content
    - Test `InvalidConfigError` for out-of-range target levels and unknown process groups
    - Test `KBValidationError` for malformed YAML
    - _Requirements: 3.3, 7.1_

- [x] 11. Create documentation and open-source distribution files
  - [x] 11.1 Create README with setup and usage instructions
    - Write `README.md` with: project overview, installation instructions (`pip install`), usage examples for `evaluate`, `validate-kb`, and `version` commands, configuration options, contribution guidelines
    - Include example output showing a sample gap analysis report snippet
    - _Requirements: 9.3_

  - [x] 11.2 Create sample SDP document for testing
    - Create `examples/sample_sdp.md` with a realistic SDP document covering process steps, roles, work products, metrics, quality gates, and traceability references
    - This serves as both a test fixture and a usage example
    - _Requirements: 3.1, 3.2_

- [x] 12. Final checkpoint — Full integration verification
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Implement AI provider integration
  - [x] 13.1 Create provider package and factory
    - Create `src/aspice_eval/providers/__init__.py` with `create_evaluator(config: ModelConfig) -> GapAnalysisEvaluator` factory function
    - Factory uses lazy imports to resolve provider class from `config.provider` string ("bedrock", "openai", "anthropic", "mock")
    - Raise `InvalidConfigError` for unknown provider names
    - _Requirements: 4.1, 4.5, 9.4_

  - [x] 13.2 Implement Amazon Bedrock provider
    - Create `src/aspice_eval/providers/bedrock.py` with `BedrockEvaluator` class
    - Override `_call_model(prompt)` using `boto3` Bedrock Runtime Converse API
    - Support `config.region` for AWS region selection (default `us-east-1`)
    - Map `AIModelError` from boto3 `ClientError` exceptions (throttling, access denied, model not found)
    - Add `boto3` as an optional dependency in `pyproject.toml` under `[project.optional-dependencies.bedrock]`
    - _Requirements: 4.1, 4.5_

  - [x] 13.3 Implement OpenAI provider
    - Create `src/aspice_eval/providers/openai.py` with `OpenAIEvaluator` class
    - Override `_call_model(prompt)` using `openai` Chat Completions API with `response_format={"type": "json_object"}`
    - Support `config.api_key` or `OPENAI_API_KEY` environment variable
    - Map `AIModelError` from `openai.APIError`, `openai.RateLimitError`, `openai.AuthenticationError`
    - Add `openai` as an optional dependency under `[project.optional-dependencies.openai]`
    - _Requirements: 4.1, 4.5_

  - [x] 13.4 Implement Anthropic provider
    - Create `src/aspice_eval/providers/anthropic.py` with `AnthropicEvaluator` class
    - Override `_call_model(prompt)` using `anthropic` Messages API
    - Support `config.api_key` or `ANTHROPIC_API_KEY` environment variable
    - Map `AIModelError` from `anthropic.APIError`, `anthropic.RateLimitError`, `anthropic.AuthenticationError`
    - Add `anthropic` as an optional dependency under `[project.optional-dependencies.anthropic]`
    - _Requirements: 4.1, 4.5_

  - [x] 13.5 Update CLI to use provider factory
    - Add `--provider` flag to the `evaluate` command (default from `ASPICE_EVAL_PROVIDER` env var, fallback to "mock")
    - Add `--region` flag for Bedrock AWS region
    - Replace hardcoded `MockEvaluator` with `create_evaluator(model_config)` factory call
    - Support environment variables: `ASPICE_EVAL_PROVIDER`, `ASPICE_EVAL_MODEL`, `ASPICE_EVAL_TEMPERATURE`, `ASPICE_EVAL_MAX_TOKENS`
    - CLI flags override environment variables, environment variables override defaults
    - _Requirements: 7.1, 9.3_

  - [x] 13.6 Write unit tests for provider factory and error mapping
    - Test factory resolves correct class for each provider name
    - Test factory raises `InvalidConfigError` for unknown providers
    - Test each provider maps API errors to `AIModelError` correctly (mock the API clients)
    - Test environment variable fallback for API keys and provider selection
    - _Requirements: 4.1_

  - [x] 13.7 Write integration test with mock server
    - Create a test that uses `MockEvaluator` through the full CLI pipeline (end-to-end)
    - Verify the evaluate command produces a valid report when run against the sample SDP
    - _Requirements: 4.1, 6.1_

- [x] 14. Implement prompt chunking for large documents
  - [x] 14.1 Add token estimation and chunking logic
    - Add `_estimate_tokens(text: str) -> int` method to `GapAnalysisEvaluator` using 4 chars/token heuristic
    - Add `_chunk_criteria(criteria, sdp, max_context_tokens)` method that splits criteria into batches by process group when the combined prompt exceeds the context window
    - Add `_merge_results(batch_results: list[EvaluationResult]) -> EvaluationResult` to combine results from multiple batches
    - Default `max_context_tokens` to 100,000 (configurable via `ModelConfig`)
    - _Requirements: 4.1, 4.4_

  - [x] 14.2 Write unit tests for chunking
    - Test that small documents are not chunked (single batch)
    - Test that large criteria sets are split by process group
    - Test that merged results contain all ratings from all batches
    - _Requirements: 4.1, 4.4_

- [x] 15. Final checkpoint — Verify AI provider integration
  - Run all tests including new provider tests
  - Verify `aspice-eval evaluate --provider mock --sdp examples/sample_sdp.md` produces a valid report
  - Ensure all existing 167+ tests still pass

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The KB criteria files (tasks 2.3, 2.4) are the most content-heavy tasks — they require authoring ASPICE criteria entries derived from publicly available summaries only
- The AI evaluator (task 6.1) is the core integration point — prompt engineering quality directly impacts evaluation accuracy
