# Requirements Document

## Introduction

Replace the hand-rolled `_markdown_to_html` method in `ReportGenerator` with the Python `markdown` library. The current implementation (~100 lines) only handles headings, tables, lists, bold, and paragraphs. It fails on fenced code blocks, blockquotes, Mermaid diagrams, and other standard Markdown features. This causes breakage when `publish_to_confluence.py` is used to publish arbitrary Markdown files (e.g., Kiro spec documents with Mermaid diagrams).

The `markdown` library is a pure-Python, well-maintained package that handles all standard Markdown features and supports extensions for tables, fenced code blocks, and more.

## Glossary

- **Markdown_Library**: The Python `markdown` package (pypi: `markdown`), a pure-Python Markdown-to-HTML converter supporting CommonMark and extensions.
- **Report_Generator**: The `ReportGenerator` class in `aspice-eval/src/aspice_eval/report_generator.py` that produces gap analysis reports in Markdown and HTML formats.
- **Publish_Script**: The `publish_to_confluence.py` script in `aspice-eval/scripts/` that converts arbitrary Markdown files to HTML and publishes them to Confluence.
- **MD_To_HTML_Script**: The `md_to_html.py` script in `aspice-eval/scripts/` that converts a Markdown file to an HTML file using the report generator's converter.
- **Analyze_Pipeline**: The `aspice-analyze` CLI command that orchestrates export, evaluate, and publish stages, using `ReportGenerator.generate(output_format="html")` for the Publish Stage.
- **Extensions**: Pluggable modules for the Markdown_Library that add support for non-core syntax (tables, fenced code blocks, etc.).
- **Confluence_Storage_Format**: The XHTML-based format that Confluence uses internally to store page content.

## Requirements

### Requirement 1: Replace hand-rolled converter with markdown library

**User Story:** As a developer, I want the Markdown-to-HTML conversion to use a well-maintained library, so that all standard Markdown features are correctly converted without maintaining custom parsing code.

#### Acceptance Criteria

1. THE Report_Generator SHALL use the Markdown_Library to convert Markdown content to HTML instead of the hand-rolled `_markdown_to_html` implementation.
2. THE Report_Generator SHALL enable the `tables` extension so that pipe-delimited Markdown tables are converted to HTML `<table>` elements.
3. THE Report_Generator SHALL enable the `fenced_code` extension so that fenced code blocks (triple backticks) are converted to HTML `<pre><code>` elements.
4. WHEN Markdown content contains headings (levels 1–6), THE Markdown_Library SHALL convert them to corresponding `<h1>` through `<h6>` HTML elements.
5. WHEN Markdown content contains unordered or ordered lists, THE Markdown_Library SHALL convert them to `<ul>/<li>` or `<ol>/<li>` HTML elements.
6. WHEN Markdown content contains bold text (`**text**`), THE Markdown_Library SHALL convert it to `<strong>` HTML elements.

### Requirement 2: Support extended Markdown features

**User Story:** As a user publishing arbitrary Markdown files to Confluence, I want code blocks, blockquotes, and other standard Markdown features to render correctly, so that my documentation is not corrupted during publishing.

#### Acceptance Criteria

1. WHEN Markdown content contains fenced code blocks with a language identifier (e.g., ` ```python `), THE Report_Generator SHALL produce HTML with the language class on the `<code>` element.
2. WHEN Markdown content contains Mermaid diagram blocks (` ```mermaid `), THE Report_Generator SHALL preserve them as fenced code blocks in the HTML output rather than stripping or corrupting them.
3. WHEN Markdown content contains blockquotes (lines prefixed with `>`), THE Report_Generator SHALL convert them to `<blockquote>` HTML elements.
4. WHEN Markdown content contains inline code (backtick-delimited), THE Report_Generator SHALL convert it to `<code>` HTML elements.

### Requirement 3: Maintain backward compatibility for gap analysis reports

**User Story:** As a user of the aspice-eval tool, I want my gap analysis reports to continue rendering correctly in HTML format, so that the migration does not break existing functionality.

#### Acceptance Criteria

1. WHEN `ReportGenerator.generate()` is called with `output_format="html"`, THE Report_Generator SHALL produce valid HTML containing all report sections (Metadata, Executive Summary, Capability Level Summary, Detailed Findings, Remediation Roadmap, Traceability Matrix).
2. THE Report_Generator SHALL produce HTML where Markdown tables in the report (Capability Level Summary, Traceability Matrix) are rendered as HTML `<table>` elements with `<thead>` and `<tbody>` sections.
3. THE Report_Generator SHALL produce HTML where nested list items in the Detailed Findings section are rendered as nested `<ul>` or `<ol>` elements.
4. WHEN the Analyze_Pipeline executes the Publish Stage, THE Report_Generator SHALL produce HTML that the Confluence content conversion API accepts without error.

### Requirement 4: Update dependency configuration

**User Story:** As a developer, I want the `markdown` library declared as a project dependency, so that it is automatically installed when the package is installed.

#### Acceptance Criteria

1. THE `pyproject.toml` for `aspice-eval` SHALL declare `markdown>=3.5.0` in the `dependencies` list.
2. THE `pyproject.toml` SHALL NOT remove any existing dependencies.
3. WHEN `aspice-eval` is installed via `pip install`, THE Markdown_Library SHALL be available for import without additional installation steps.

### Requirement 5: Maintain public interface compatibility

**User Story:** As a maintainer of scripts that call `_markdown_to_html`, I want the method signature and return type to remain unchanged, so that existing callers do not need modification.

#### Acceptance Criteria

1. THE Report_Generator SHALL continue to expose `_markdown_to_html` as a static method accepting a single `str` argument and returning a `str`.
2. WHEN the Publish_Script calls `ReportGenerator._markdown_to_html(md_content)`, THE method SHALL return valid HTML without raising exceptions for any well-formed Markdown input.
3. WHEN the MD_To_HTML_Script calls `ReportGenerator._markdown_to_html(md_content)`, THE method SHALL return valid HTML without raising exceptions for any well-formed Markdown input.
4. THE `_markdown_to_html` method SHALL accept arbitrary Markdown content (not just the specific patterns used in gap analysis reports).

### Requirement 6: Remove hand-rolled implementation

**User Story:** As a developer, I want the custom Markdown parsing code removed, so that the codebase is simpler and easier to maintain.

#### Acceptance Criteria

1. THE Report_Generator module SHALL NOT contain the hand-rolled regex-based Markdown parsing logic (the `_close_lists_to`, `_close_all_lists` closures, table state machine, and line-by-line parser loop).
2. THE module-level `_html_inline` helper function SHALL be removed since inline formatting is handled by the Markdown_Library.
3. THE Report_Generator module SHALL have fewer lines of code dedicated to Markdown-to-HTML conversion than the current implementation.
