# Requirements Document — Single-Command ASPICE Analysis Pipeline

## Introduction

This spec defines a **single CLI command** `aspice-analyze` that orchestrates the full ASPICE gap analysis pipeline in one step: export a Confluence SDP page to Markdown, evaluate it against the ASPICE knowledge base, and publish the gap analysis report back to Confluence as a child page. The command is an orchestration layer that composes existing functionality from the `confluence-exporter` and `aspice-eval` packages into a seamless, minimal-parameter workflow.

### Motivation

- Running the full ASPICE analysis pipeline currently requires three separate manual steps: (1) export the Confluence page with `confluence-export`, (2) evaluate the exported Markdown with `aspice-eval evaluate`, and (3) publish the report with `publish_to_confluence.py`
- Each step requires its own set of parameters, temporary file management, and error handling — creating friction for users who want a quick gap analysis
- A single command with sensible defaults (Bedrock provider, Sonnet model, capability level 3) reduces the workflow to one invocation with just a URL and credentials
- The command should be pip-installable from a GitLab URL so users can run it without cloning the repository

### Key Integration Points

- **Confluence Export:** Uses `confluence-exporter` library components (URLParser, ConfluenceClient, StorageFormatParser, AssetDownloader, MarkdownRenderer) to export the SDP page
- **ASPICE Evaluation:** Uses `aspice-eval` library components (KnowledgeBase, SDPIngester, Evaluator, CapabilityLevelCalculator, ReportGenerator) to perform gap analysis
- **Confluence Publishing:** Uses the Confluence REST API (via `atlassian-python-api`) to create the report as a child page of the source SDP page
- **AI Providers:** Uses Amazon Bedrock with Claude Sonnet as the default for both image description and gap analysis evaluation

## Glossary

- **Pipeline**: The three-stage orchestration workflow: Export → Evaluate → Publish
- **Analyze_Command**: The `aspice-analyze` CLI command that executes the full Pipeline
- **SDP_Page**: The source Confluence page containing the Software Development Process document to be analyzed
- **Export_Stage**: The first Pipeline stage that retrieves the SDP_Page from Confluence, downloads images, generates AI image descriptions, and produces a Markdown file
- **Evaluate_Stage**: The second Pipeline stage that runs the ASPICE gap analysis on the exported Markdown using the Knowledge_Base
- **Publish_Stage**: The third Pipeline stage that converts the Gap_Analysis_Report to Confluence storage format and creates it as a child page of the SDP_Page
- **Gap_Analysis_Report**: The structured Markdown report produced by the Evaluate_Stage, containing per-process-group ratings, gaps, and remediation recommendations
- **Knowledge_Base**: The structured YAML collection of ASPICE criteria used by the Evaluate_Stage (bundled with the aspice-eval package)
- **Bedrock_Provider**: The Amazon Bedrock AI service used as the default provider for both image descriptions and gap analysis evaluation
- **Confluence_Credentials**: The combination of email address and API token required to authenticate with the Confluence Cloud REST API
- **Progress_Reporter**: The component that displays real-time status updates to the user as each Pipeline stage executes
- **Output_Directory**: The local directory where intermediate artifacts (exported Markdown, images, raw report) are stored for user inspection; defaults to `./aspice-output/{sanitized_page_title}/`
- **AI_Cost_Summary**: A section in the Gap_Analysis_Report that tracks and reports token usage and AI model call counts across all Pipeline stages

## Requirements

### Requirement 1: Single Command Entry Point

**User Story:** As a user, I want to run a single command with just a Confluence URL to get a full ASPICE gap analysis, so that I do not have to manually orchestrate multiple tools.

#### Acceptance Criteria

1. THE Analyze_Command SHALL provide a CLI command `aspice-analyze` that accepts a Confluence page URL as its primary positional argument.
2. WHEN invoked with a valid SDP_Page URL, valid Confluence_Credentials, target level, and process groups, THE Analyze_Command SHALL execute the full Pipeline (Export_Stage → Evaluate_Stage → Publish_Stage) without requiring user interaction between stages.
3. THE Analyze_Command SHALL store all intermediate artifacts (exported Markdown, downloaded images, AI descriptions) in a local Output_Directory with a relative path based on the SDP page title (e.g., `./aspice-output/{sanitized_page_title}/`).
4. THE Analyze_Command SHALL preserve the Output_Directory and all intermediate files after the Pipeline completes, so that the user can inspect exported content, images, and the raw report.
5. WHEN the Pipeline completes successfully, THE Analyze_Command SHALL print a summary including: the URL of the published child page, the achieved capability levels per process group, the total number of gaps identified, and the path to the local Output_Directory.
6. THE Analyze_Command SHALL return exit code 0 on success and a non-zero exit code on failure.

### Requirement 2: Minimal Required Parameters

**User Story:** As a user, I want to provide only the essential parameters, so that I can run the analysis with minimal setup while retaining control over scope.

#### Acceptance Criteria

1. THE Analyze_Command SHALL require the Confluence page URL as a positional argument.
2. THE Analyze_Command SHALL require a `--target-level` option specifying the ASPICE capability level to evaluate against (valid range: 1 through 5).
3. THE Analyze_Command SHALL require a `--groups` option specifying the comma-separated list of process group codes to evaluate (e.g., `SWE,MAN,SUP`).
4. THE Analyze_Command SHALL accept Confluence_Credentials via `--email` and `--api-token` CLI options.
5. THE Analyze_Command SHALL accept Confluence_Credentials via the environment variables `CONFLUENCE_EMAIL` and `CONFLUENCE_API_TOKEN`, with CLI options taking precedence over environment variables.
6. IF Confluence_Credentials are not provided via CLI options or environment variables, THEN THE Analyze_Command SHALL display a descriptive error message identifying which credential is missing and how to provide it.
7. THE Analyze_Command SHALL derive the Confluence base URL and space key from the provided page URL, requiring no additional Confluence configuration.
8. IF `--target-level` or `--groups` is not provided, THEN THE Analyze_Command SHALL display a descriptive error message identifying the missing required parameter.

### Requirement 3: Sensible Defaults

**User Story:** As a user, I want the command to use sensible defaults for AI provider and model, so that I do not need to configure AI settings for a standard analysis.

#### Acceptance Criteria

1. THE Analyze_Command SHALL default to Amazon Bedrock as the AI provider for both the Export_Stage (image descriptions) and the Evaluate_Stage (gap analysis).
2. THE Analyze_Command SHALL default to the Claude Sonnet model (`us.anthropic.claude-sonnet-4-20250514-v1:0`) for both the Export_Stage and the Evaluate_Stage.
3. THE Analyze_Command SHALL read the `AWS_DEFAULT_REGION` environment variable as the default value for the AWS region when using the Bedrock_Provider.
4. IF the `AWS_DEFAULT_REGION` environment variable is not set and no `--region` CLI option is provided, THEN THE Analyze_Command SHALL display a descriptive error message requesting the user to set the region via the environment variable or CLI option.

### Requirement 4: Configurable Parameters

**User Story:** As a user, I want to override defaults for AI provider and other settings, so that I can customize the analysis for specific needs.

#### Acceptance Criteria

1. THE Analyze_Command SHALL accept a `--provider` option to override the default AI provider (valid values: bedrock, openai, anthropic).
2. THE Analyze_Command SHALL accept a `--model` option to override the default AI model name.
3. THE Analyze_Command SHALL accept a `--region` option to override the AWS region from the environment variable for the Bedrock_Provider.
4. THE Analyze_Command SHALL accept a `--report-title` option to override the default child page title (default: "ASPICE Gap Analysis — {SDP page title}").
5. THE Analyze_Command SHALL accept an `--output-dir` option to override the default Output_Directory path.
6. IF an invalid value is provided for `--target-level`, THEN THE Analyze_Command SHALL display a descriptive error message identifying the valid range (1 through 5).
7. IF an unknown process group code is provided for `--groups`, THEN THE Analyze_Command SHALL display a descriptive error message listing the valid group codes.

### Requirement 5: Export Stage Execution

**User Story:** As a user, I want the command to export my Confluence SDP page to Markdown with images and AI descriptions, so that the evaluation has complete content including visual process flows.

#### Acceptance Criteria

1. WHEN the Export_Stage begins, THE Analyze_Command SHALL connect to Confluence using the provided Confluence_Credentials and retrieve the SDP_Page content in storage format.
2. WHEN the SDP_Page is retrieved, THE Analyze_Command SHALL parse the storage format XHTML, download all embedded images and Gliffy diagrams, and generate AI-powered image descriptions using the configured provider.
3. WHEN the export is complete, THE Analyze_Command SHALL produce a self-contained Markdown file with all images referenced via relative paths and AI-generated descriptions embedded as blockquotes.
4. IF the SDP_Page URL is invalid or the page does not exist, THEN THE Analyze_Command SHALL display a descriptive error message and exit without proceeding to subsequent stages.
5. IF image download or AI description generation fails for individual images, THEN THE Analyze_Command SHALL log a warning and continue processing the remaining content.

### Requirement 6: Evaluate Stage Execution

**User Story:** As a user, I want the exported SDP evaluated against ASPICE criteria, so that I get a comprehensive gap analysis report.

#### Acceptance Criteria

1. WHEN the Evaluate_Stage begins, THE Analyze_Command SHALL load the ASPICE Knowledge_Base bundled with the aspice-eval package.
2. WHEN the Knowledge_Base is loaded, THE Analyze_Command SHALL ingest the exported Markdown file and evaluate it against all criteria up to and including the target capability level for the specified process groups.
3. WHEN the evaluation is complete, THE Analyze_Command SHALL generate a Gap_Analysis_Report in Markdown format containing: executive summary, capability level summary, detailed findings, remediation roadmap, traceability matrix, and AI cost summary.
4. IF the Knowledge_Base fails to load or validate, THEN THE Analyze_Command SHALL display a descriptive error message and exit without proceeding to the Publish_Stage.

### Requirement 7: Publish Stage Execution

**User Story:** As a user, I want the gap analysis report automatically published as a child page of my SDP page, so that the results are immediately accessible to my team in Confluence.

#### Acceptance Criteria

1. WHEN the Publish_Stage begins, THE Analyze_Command SHALL convert the Gap_Analysis_Report from Markdown to Confluence storage format (XHTML).
2. THE Analyze_Command SHALL create a new Confluence page as a child of the source SDP_Page, using the report title as the page title.
3. WHEN the child page is created, THE Analyze_Command SHALL print the URL of the newly created page to stdout.
4. IF a child page with the same title already exists under the SDP_Page, THEN THE Analyze_Command SHALL update the existing page with the new report content instead of creating a duplicate.
5. IF the Confluence API rejects the page creation due to permissions or other errors, THEN THE Analyze_Command SHALL display a descriptive error message identifying the failure reason.

### Requirement 8: Local Output Option

**User Story:** As a user, I want to save the report locally instead of or in addition to publishing to Confluence, so that I can review it offline or use it in other workflows.

#### Acceptance Criteria

1. THE Analyze_Command SHALL accept an `--output` option specifying a local file path for saving the Gap_Analysis_Report.
2. WHEN `--output` is provided, THE Analyze_Command SHALL write the Gap_Analysis_Report to the specified file path in Markdown format.
3. THE Analyze_Command SHALL accept an `--output-format` option with values `markdown` or `html` (default: `markdown`) to control the local output format.
4. THE Analyze_Command SHALL accept a `--no-publish` flag that skips the Publish_Stage entirely.
5. WHEN `--no-publish` is specified without `--output`, THE Analyze_Command SHALL print the Gap_Analysis_Report to stdout.
6. WHEN both `--output` and publishing are active, THE Analyze_Command SHALL both save the report locally and publish it to Confluence.

### Requirement 9: Progress Feedback

**User Story:** As a user, I want to see progress updates as the command runs through each pipeline stage, so that I know the analysis is progressing and can estimate completion time.

#### Acceptance Criteria

1. WHEN each Pipeline stage begins, THE Progress_Reporter SHALL display a status message identifying the current stage (e.g., "Exporting Confluence page...", "Evaluating against ASPICE criteria...", "Publishing report to Confluence...").
2. WHEN a stage completes, THE Progress_Reporter SHALL display a completion message with key metrics (e.g., "Export complete: 12 images, 10 descriptions", "Evaluation complete: 45 criteria assessed").
3. THE Progress_Reporter SHALL write progress messages to stderr so that stdout remains clean for structured output and piping.
4. THE Analyze_Command SHALL accept a `--verbose` flag that increases log output to DEBUG level, including API request details and intermediate processing steps.
5. THE Analyze_Command SHALL accept a `--quiet` flag that suppresses progress messages, outputting only the final summary or errors.

### Requirement 10: Error Handling

**User Story:** As a user, I want clear error messages for common failure scenarios, so that I can quickly diagnose and fix issues.

#### Acceptance Criteria

1. IF AWS credentials are expired or invalid for the Bedrock_Provider, THEN THE Analyze_Command SHALL display a descriptive error message suggesting the user refresh their AWS session (e.g., "AWS session expired. Run 'aws sso login' or refresh your credentials.").
2. IF the Confluence page URL does not match the expected Confluence Cloud URL pattern, THEN THE Analyze_Command SHALL display a descriptive error message showing the expected URL format.
3. IF a network connection to Confluence or the AI provider fails, THEN THE Analyze_Command SHALL display a descriptive error message identifying which service is unreachable.
4. IF the Confluence API returns a permission error during page retrieval or publishing, THEN THE Analyze_Command SHALL display a descriptive error message identifying the permission issue.
5. WHEN a fatal error occurs at any Pipeline stage, THE Analyze_Command SHALL exit with a non-zero exit code and display which stage failed and why.
6. THE Analyze_Command SHALL not leave partial or corrupted child pages in Confluence when the Publish_Stage fails mid-operation.

### Requirement 11: Pip-Installable Package

**User Story:** As a user, I want to install the tool via `pip install` from a GitLab URL without cloning the repository, so that setup is quick and straightforward.

#### Acceptance Criteria

1. THE aspice-eval package SHALL declare `confluence-exporter` as a dependency so that `pip install` pulls in both packages automatically.
2. THE aspice-eval package SHALL register the `aspice-analyze` command as an additional entry point in `pyproject.toml`, alongside the existing `aspice-eval` entry point.
3. THE aspice-eval package SHALL declare `atlassian-python-api` as a dependency for the Confluence publishing functionality.
4. WHEN a user runs `pip install "aspice-eval[all] @ git+https://github.com/oddisej/aspice-check.git"`, THE installation SHALL provide both the `aspice-eval` and `aspice-analyze` commands.
5. THE aspice-eval package SHALL include the Knowledge_Base YAML files as package data so they are available after installation without requiring a separate download.

### Requirement 12: Environment Variable Support

**User Story:** As a user, I want to configure credentials via environment variables, so that I do not need to pass them on every invocation and can avoid exposing secrets in shell history.

#### Acceptance Criteria

1. THE Analyze_Command SHALL read the `CONFLUENCE_EMAIL` environment variable as the default value for the `--email` option.
2. THE Analyze_Command SHALL read the `CONFLUENCE_API_TOKEN` environment variable as the default value for the `--api-token` option.
3. THE Analyze_Command SHALL read the `AWS_DEFAULT_REGION` environment variable as the default value for the `--region` option when using the Bedrock_Provider.
4. THE Analyze_Command SHALL read the `ASPICE_EVAL_PROVIDER` environment variable as the default value for the `--provider` option.
5. WHEN both a CLI option and its corresponding environment variable are set, THE Analyze_Command SHALL use the CLI option value.

### Requirement 13: AI Cost Summary in Report

**User Story:** As a user, I want to see the total AI costs incurred during the analysis, so that I can track and budget for the agentic AI usage across export and evaluation stages.

#### Acceptance Criteria

1. THE Analyze_Command SHALL track token usage (input tokens, output tokens, total tokens) for all AI model calls across both the Export_Stage (image descriptions) and the Evaluate_Stage (gap analysis evaluation).
2. WHEN the Gap_Analysis_Report is generated, THE Analyze_Command SHALL include an "AI Cost Summary" section containing: total input tokens, total output tokens, total tokens, number of AI model calls, the AI provider and model used, and the AWS region (when using Bedrock_Provider).
3. THE AI Cost Summary section SHALL report token usage separately for the Export_Stage and the Evaluate_Stage, as well as a combined total.
4. WHEN the Pipeline completes, THE Analyze_Command SHALL include the total token usage in the final summary printed to stdout.
