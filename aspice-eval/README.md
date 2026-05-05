# aspice-eval

An ASPICE (Automotive SPICE) evaluation tool that pairs a structured YAML knowledge base of ASPICE v4.0 criteria with an AI-powered agent workflow for Software Development Process (SDP) gap analysis.

## Overview

`aspice-eval` evaluates your organization's Software Development Process documentation against the Automotive SPICE v4.0 Process Assessment Model (PAM). It identifies compliance gaps, rates process attributes using the ASPICE four-point scale, determines achieved capability levels, and generates actionable remediation recommendations.

### Key Features

- **Structured Knowledge Base** — ASPICE criteria organized by process group, capability level, and process attribute in machine-readable YAML
- **AI-Powered Gap Analysis** — Qualitative evaluation that mirrors human assessor reasoning
- **Capability Level Determination** — Automatic calculation following ASPICE cumulative achievement rules (levels 0–5)
- **Markdown Reports** — Structured gap analysis reports with executive summary, detailed findings, remediation roadmap, and traceability matrix
- **KB Validation** — Schema and completeness checks to ensure knowledge base integrity
- **Extensible Design** — Schema-first approach supports adding new standards (CMMI, ISO 26262, IEC 62304)

### Supported Process Groups

| Code | Name | Processes |
|------|------|-----------|
| SWE | Software Engineering | SWE.1–SWE.6 |
| SYS | System Engineering | SYS.1–SYS.5 |
| MAN | Project Management | MAN.3 |
| SUP | Support Processes | SUP.1, SUP.8–SUP.10 |

## Installation

### Requirements

- Python 3.10 or later

### Install from source

```bash
# Clone the repository
git clone https://github.com/oddisej/aspice-check.git
cd aspice-check/aspice-eval

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

### Install runtime only

```bash
cd aspice-eval
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

### Install with full pipeline support (aspice-analyze)

To use the single-command `aspice-analyze` pipeline that exports from Confluence, evaluates, and publishes back:

```bash
# From source (editable mode)
pip install -e ".[analyze,bedrock,dev]"

# From GitHub via HTTPS (no clone needed) — install both packages
pip install "confluence-exporter[bedrock] @ git+https://github.com/oddisej/aspice-check.git#subdirectory=confluence-exporter"
pip install "aspice-eval[analyze,bedrock] @ git+https://github.com/oddisej/aspice-check.git#subdirectory=aspice-eval"

# Or from GitHub via SSH
pip install "confluence-exporter[bedrock] @ git+ssh://git@github.com/oddisej/aspice-check.git#subdirectory=confluence-exporter"
pip install "aspice-eval[analyze,bedrock] @ git+ssh://git@github.com/oddisej/aspice-check.git#subdirectory=aspice-eval"
```

You may also need the CRT dependency for AWS SSO credentials:

```bash
pip install "botocore[crt]"
```

## Quick Start — Single-Command Analysis

The fastest way to run an ASPICE gap analysis on a Confluence SDP page:

```bash
# Set credentials once (add to your .bashrc/.zshrc)
export CONFLUENCE_EMAIL="your.email@company.com"
export CONFLUENCE_API_TOKEN="your-confluence-api-token"
export AWS_DEFAULT_REGION="eu-west-1"

# Run the full pipeline: export → evaluate → publish
aspice-analyze \
  "https://your-instance.atlassian.net/wiki/spaces/SPACE/pages/12345/Your+SDP+Page" \
  --target-level 1 \
  --groups SWE
```

This single command will:
1. Export the Confluence page to Markdown (with images and AI-generated diagram descriptions)
2. Evaluate the SDP against ASPICE criteria using Amazon Bedrock (Claude Sonnet)
3. Publish the gap analysis report as a child page under your SDP page

### aspice-analyze options

| Option | Env Variable | Default | Description |
|--------|-------------|---------|-------------|
| `PAGE_URL` | — | *(required)* | Confluence Cloud page URL |
| `--target-level` | — | *(required)* | ASPICE capability level (1–5) |
| `--groups` | — | *(required)* | Comma-separated process groups (e.g., `SWE,MAN,SUP`) |
| `--email` | `CONFLUENCE_EMAIL` | — | Confluence account email |
| `--api-token` | `CONFLUENCE_API_TOKEN` | — | Confluence API token |
| `--provider` | `ASPICE_EVAL_PROVIDER` | `bedrock` | AI provider: bedrock, openai, anthropic |
| `--model` | — | Sonnet (per provider) | AI model name |
| `--region` | `AWS_DEFAULT_REGION` | — | AWS region (required for Bedrock) |
| `--report-title` | — | "ASPICE Gap Analysis — {title}" | Confluence child page title |
| `--output-dir` | — | `./aspice-output/{title}/` | Local directory for artifacts |
| `--output` | — | — | Save report to local file |
| `--output-format` | — | `markdown` | Local output format: markdown or html |
| `--no-publish` | — | — | Skip publishing to Confluence |
| `--verbose` | — | — | DEBUG-level logging |
| `--quiet` | — | — | Suppress progress messages |

### Examples

```bash
# Evaluate SWE and MAN at level 3, publish to Confluence
aspice-analyze "https://..." --target-level 3 --groups SWE,MAN

# Save report locally without publishing
aspice-analyze "https://..." --target-level 1 --groups SWE --no-publish --output report.md

# Use OpenAI instead of Bedrock
aspice-analyze "https://..." --target-level 2 --groups SWE \
  --provider openai --model gpt-4o

# Custom report title
aspice-analyze "https://..." --target-level 1 --groups SWE \
  --report-title "Q2 2026 ASPICE Assessment — SWE"

# HTML output
aspice-analyze "https://..." --target-level 1 --groups SWE \
  --no-publish --output report.html --output-format html
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Parameter validation error |
| 2 | Export stage failure (Confluence/AI) |
| 3 | Evaluation stage failure (KB/AI) |
| 4 | Publish stage failure (Confluence) |

---

## Usage — Individual Commands

The tool also provides individual CLI commands for more granular control: `evaluate`, `validate-kb`, and `version`.

### Evaluate an SDP document

Run a gap analysis of an SDP document against the ASPICE knowledge base. All commands assume the virtual environment is activated (`source .venv/bin/activate`):

```bash
# Activate the virtual environment first
source .venv/bin/activate
# Basic evaluation (defaults: target level 3, all process groups, mock provider)
aspice-eval evaluate --sdp path/to/your_sdp.md

# Specify target capability level and process groups
aspice-eval evaluate --sdp path/to/your_sdp.md --target-level 2 --groups SWE,MAN

# Write report to a file
aspice-eval evaluate --sdp path/to/your_sdp.md --output report.md

# Use a custom knowledge base path
aspice-eval evaluate --sdp path/to/your_sdp.md --kb-path /path/to/knowledge_base

# Use a real AI provider (see AI Providers section below)
aspice-eval evaluate --sdp path/to/your_sdp.md --provider bedrock --model anthropic.claude-3-5-sonnet-20241022-v2:0
```

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--sdp` | *(required)* | Path to the SDP Markdown document |
| `--target-level` | `3` | Target ASPICE capability level (1–5) |
| `--groups` | `SWE,SYS,MAN,SUP` | Comma-separated process group codes to evaluate |
| `--output` | stdout | Output file path for the report |
| `--kb-path` | `knowledge_base` | Path to the knowledge base directory |
| `--provider` | `mock` | AI provider: `bedrock`, `openai`, `anthropic`, or `mock` |
| `--model` | *(none)* | Provider-specific model identifier |
| `--region` | `us-east-1` | AWS region (Bedrock provider only) |

### Validate the knowledge base

Check the knowledge base for schema correctness and completeness:

```bash
# Validate the default knowledge base
aspice-eval validate-kb

# Validate a custom knowledge base
aspice-eval validate-kb --kb-path /path/to/knowledge_base
```

### Check the version

```bash
aspice-eval version
```

Output:

```
aspice-eval 0.1.0
```

## AI Providers

By default, `aspice-eval` uses a **mock provider** that returns deterministic ratings without calling any AI service. To get real AI-powered gap analysis, configure one of the supported providers.

### Supported Providers

| Provider | `--provider` value | Install command | Auth |
|----------|-------------------|-----------------|------|
| Amazon Bedrock | `bedrock` | `pip install "aspice-eval[bedrock]"` | AWS credentials (IAM, SSO, env vars) |
| OpenAI | `openai` | `pip install "aspice-eval[openai]"` | `OPENAI_API_KEY` env var or `--model` config |
| Anthropic | `anthropic` | `pip install "aspice-eval[anthropic]"` | `ANTHROPIC_API_KEY` env var |
| Mock (testing) | `mock` | *(included)* | None required |

Install all providers at once with `pip install "aspice-eval[all]"`.

### Amazon Bedrock

Uses the Bedrock Converse API. No API key needed — Bedrock uses your AWS credentials, which `boto3` picks up automatically from the standard credential chain.

**Prerequisites:**

1. **Enable model access** — In the AWS Console, go to Bedrock → Model access → Request access for the models you want (e.g., Claude). This is a one-time setup per region.

2. **Authenticate** — Use one of these methods:

```bash
# Option A: AWS SSO (most common in enterprise environments)
aws sso login --profile your-profile-name
export AWS_PROFILE=your-profile-name

# Option B: IAM credentials
aws configure
# Enter your Access Key ID, Secret Access Key, and default region

# Option C: EC2/ECS with IAM role — no login needed, credentials are automatic
```

**Usage:**

```bash
# Install the Bedrock provider
pip install "aspice-eval[bedrock]"

# You may also need the CRT dependency for SSO login credentials
pip install "botocore[crt]"

# Run with Claude 3.5 Haiku (fast, cost-effective)
aspice-eval evaluate \
  --sdp path/to/sdp.md \
  --provider bedrock \
  --model us.anthropic.claude-3-5-haiku-20241022-v1:0 \
  --region us-east-1

# Run with Claude Sonnet 4 (higher quality analysis)
ASPICE_EVAL_MAX_TOKENS=16384 aspice-eval evaluate \
  --sdp path/to/sdp.md \
  --provider bedrock \
  --model us.anthropic.claude-sonnet-4-6 \
  --output report.md
```

If you have access to Amazon Q Developer, you likely already have AWS credentials that work with Bedrock.

### OpenAI

Uses the Chat Completions API with JSON response mode.

```bash
# Install the OpenAI provider
pip install "aspice-eval[openai]"

# Set your API key
export OPENAI_API_KEY="sk-..."

# Run with GPT-4o
aspice-eval evaluate \
  --sdp path/to/sdp.md \
  --provider openai \
  --model gpt-4o

# Use a cheaper model
aspice-eval evaluate \
  --sdp path/to/sdp.md \
  --provider openai \
  --model gpt-4o-mini
```

### Anthropic (Direct API)

Uses the Anthropic Messages API directly (not through Bedrock).

```bash
# Install the Anthropic provider
pip install "aspice-eval[anthropic]"

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Run with Claude
aspice-eval evaluate \
  --sdp path/to/sdp.md \
  --provider anthropic \
  --model claude-sonnet-4-20250514
```

### Environment Variables

All settings can be configured via environment variables. CLI flags take precedence over env vars.

| Variable | Description | Example |
|----------|-------------|---------|
| `ASPICE_EVAL_PROVIDER` | Default provider | `bedrock` |
| `ASPICE_EVAL_MODEL` | Default model name | `us.anthropic.claude-3-5-haiku-20241022-v1:0` |
| `ASPICE_EVAL_TEMPERATURE` | Model temperature (0.0–1.0) | `0.0` |
| `ASPICE_EVAL_MAX_TOKENS` | Max response tokens | `8192` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` |
| `AWS_REGION` | AWS region for Bedrock | `us-east-1` |

Example using env vars instead of CLI flags:

```bash
export ASPICE_EVAL_PROVIDER=bedrock
export ASPICE_EVAL_MODEL=us.anthropic.claude-3-5-haiku-20241022-v1:0
export AWS_REGION=us-west-2

# Now just specify the SDP — provider config comes from env
aspice-eval evaluate --sdp path/to/sdp.md --output report.md
```

### Large Document Handling

When the SDP document and criteria together exceed the model's context window (default 100,000 tokens), the evaluator automatically splits criteria into batches by process group and evaluates each batch separately. Results are merged into a single report. This is transparent — no configuration needed.

## Example Output

Below is a snippet from a sample gap analysis report:

```markdown
# ASPICE Gap Analysis Report

## Metadata
- **SDP Document:** examples/sample_sdp.md
- **Target Capability Level:** 3
- **Process Groups Evaluated:** SWE, SYS, MAN, SUP
- **Knowledge Base Version:** 1.0.0
- **Evaluation Date:** 2025-01-15T10:30:00

## Executive Summary
This evaluation assessed **4** process group(s) against a target capability
level of **3**.

**2** group(s) meet the target level; **2** group(s) are below target.

A total of **12** gap(s) were identified across all criteria.

## Capability Level Summary
| Process Group | Target Level | Achieved Level | Status |
|---|---|---|---|
| MAN | 3 | 3 | ✅ Meets target |
| SUP | 3 | 2 | ⚠️ Below target |
| SWE | 3 | 2 | ⚠️ Below target |
| SYS | 3 | 3 | ✅ Meets target |

## Detailed Findings

### SWE

#### Capability Level 1 — Performed
##### PA 1.1

- **Criteria ID:** SWE.1-PA1.1-001
- **Rating:** Fully achieved
- **Evidence:** Section 4: Software Requirements Analysis describes elicitation
  and documentation activities

#### Capability Level 2 — Managed
##### PA 2.1

- **Criteria ID:** SWE.1-PA2.1-001
- **Rating:** Partially achieved
- **Evidence found:** Section 3 references project planning
- **Gaps:** No explicit performance objectives for requirements analysis;
  missing progress tracking records
- **Recommendations:** Add measurable performance objectives for the
  requirements analysis process; implement progress tracking with
  planned-vs-actual metrics

...

## Traceability Matrix
| Criteria ID | Process Group | SDP Section(s) Assessed | Rating |
|---|---|---|---|
| SWE.1-PA1.1-001 | SWE | Section 4: Software Requirements | Fully achieved |
| SWE.1-PA2.1-001 | SWE | Section 3: Project Planning | Partially achieved |
| MAN.3-PA1.1-001 | MAN | Section 2: Management Approach | Fully achieved |
```

## Configuration

### Knowledge Base Structure

The knowledge base is organized as follows:

```
knowledge_base/
├── schema/
│   └── criteria_schema.json      # JSON Schema for YAML validation
└── aspice/
    ├── _metadata.yaml            # Standard metadata (version, process groups)
    ├── swe.yaml                  # SWE process group criteria
    ├── sys.yaml                  # SYS process group criteria
    ├── man.yaml                  # MAN process group criteria
    └── sup.yaml                  # SUP process group criteria
```

Each criteria YAML file contains entries with:

- `process_id` — Process identifier (e.g., SWE.1)
- `capability_level` — ASPICE level (0–5)
- `process_attribute` — PA identifier (e.g., PA 2.1)
- `description` — What the criterion evaluates
- `expected_evidence` — Information items that demonstrate compliance
- `evaluation_guidance` — How to assess the criterion
- `example_evidence` — Concrete examples of acceptable evidence

### Adding a New Standard

To add a new compliance standard (e.g., CMMI):

1. Create a directory under `knowledge_base/` (e.g., `knowledge_base/cmmi/`)
2. Add a `_metadata.yaml` with standard name, version, and source references
3. Add criteria YAML files following the same schema as ASPICE files
4. Validate with `aspice-eval validate-kb --kb-path knowledge_base`

## Development

### Setup

```bash
# Create venv and install with dev dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Running Tests

```bash
# Activate the virtual environment
source .venv/bin/activate

# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only property-based tests
pytest tests/property/

# Run with dev profile (faster, 50 examples)
pytest --hypothesis-profile=dev
```

### Project Structure

```
aspice-eval/
├── pyproject.toml
├── src/aspice_eval/          # Source package
│   ├── cli.py                # Click-based CLI entry point
│   ├── evaluator.py          # Base evaluator + MockEvaluator
│   ├── exceptions.py         # Custom exception types
│   ├── kb_validator.py       # KB schema and completeness validation
│   ├── knowledge_base.py     # KB loader and query interface
│   ├── level_calculator.py   # Capability level determination
│   ├── models.py             # Core dataclasses
│   ├── report_generator.py   # Markdown report generation
│   ├── sdp_ingester.py       # SDP document ingestion
│   └── providers/            # AI provider implementations
│       ├── __init__.py       # Provider factory (create_evaluator)
│       ├── bedrock.py        # Amazon Bedrock (Converse API)
│       ├── openai_provider.py    # OpenAI (Chat Completions)
│       └── anthropic_provider.py # Anthropic (Messages API)
├── knowledge_base/           # ASPICE criteria YAML files
├── examples/                 # Sample documents
├── scripts/                  # Utility scripts
└── tests/                    # Unit and property-based tests
```

## Contributing

Contributions are welcome. Here's how to get started:

1. Fork the repository and create a feature branch
2. Install dev dependencies: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
3. Make your changes, following existing code conventions:
   - Type hints throughout (`from __future__ import annotations`)
   - Dataclasses for models (no Pydantic)
   - Module docstrings on all files
4. Add or update tests as needed:
   - Unit tests in `tests/unit/`
   - Property-based tests in `tests/property/`
5. Run the full test suite: `pytest`
6. Validate the knowledge base if you modified criteria files: `aspice-eval validate-kb`
7. Submit a pull request with a clear description of your changes

### Knowledge Base Contributions

When adding or modifying ASPICE criteria:

- Follow the JSON Schema defined in `knowledge_base/schema/criteria_schema.json`
- Use ASPICE 4.0 "Information Items" terminology for evidence descriptions
- Include only content derived from publicly available summaries — no proprietary VDA content
- Run `aspice-eval validate-kb` to verify schema compliance and completeness

## License

MIT

## Attribution

Criteria descriptions in the knowledge base are derived from publicly available ASPICE standard summaries. No proprietary VDA content is included. See `knowledge_base/aspice/_metadata.yaml` for source references.
