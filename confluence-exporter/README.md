# Confluence Page Exporter

A Python CLI tool that exports Confluence Cloud pages to self-contained Markdown files with locally downloaded images and AI-generated image descriptions.

Designed to bridge the gap between Confluence-hosted documentation and the `aspice-eval` tool's Markdown-based ingestion pipeline. The exporter handles inline images, Gliffy diagrams, and uses multimodal AI models to generate textual descriptions of visual content — so downstream AI agents can understand process flows, swimlanes, and decision points.

## Features

- Export Confluence Cloud pages to clean Markdown
- Download all inline images and Gliffy diagram PNGs locally
- Generate AI-powered image descriptions using Anthropic Claude or OpenAI GPT-4o
- Preserve heading hierarchy for `aspice-eval` SDP ingestion
- YAML front-matter with page metadata
- Graceful handling of partial failures (missing images, AI errors)

## Installation

```bash
# Clone the repository and install in editable mode
cd confluence-exporter
pip install -e ".[dev]"

# With AI provider support
pip install -e ".[anthropic]"   # For Anthropic Claude
pip install -e ".[openai]"      # For OpenAI GPT-4o
pip install -e ".[all]"         # Both providers
```

### Requirements

- Python 3.10 or later
- A Confluence Cloud instance with API access
- An API token for your Confluence account

## Usage

### Basic export (no AI descriptions)

```bash
confluence-export \
  "https://acme.atlassian.net/wiki/spaces/ENG/pages/12345/My-Page" \
  ./output \
  --email user@example.com \
  --api-token YOUR_API_TOKEN \
  --no-ai
```

### Export with AI image descriptions

```bash
confluence-export \
  "https://acme.atlassian.net/wiki/spaces/ENG/pages/12345/My-Page" \
  ./output \
  --email user@example.com \
  --api-token YOUR_API_TOKEN \
  --ai-provider anthropic \
  --ai-api-key YOUR_ANTHROPIC_KEY
```

### Using environment variables

```bash
export CONFLUENCE_EMAIL="user@example.com"
export CONFLUENCE_API_TOKEN="your-token"
export CONFLUENCE_EXPORT_AI_PROVIDER="anthropic"
export ANTHROPIC_API_KEY="your-anthropic-key"

confluence-export \
  "https://acme.atlassian.net/wiki/spaces/ENG/pages/12345/My-Page" \
  ./output
```

### Verbose logging

```bash
confluence-export \
  "https://acme.atlassian.net/wiki/spaces/ENG/pages/12345/My-Page" \
  ./output \
  --email user@example.com \
  --api-token YOUR_API_TOKEN \
  --no-ai \
  --verbose
```

## CLI Reference

```
confluence-export <PAGE_URL> <OUTPUT_DIR> [OPTIONS]
```

### Arguments

| Argument | Description |
|---|---|
| `PAGE_URL` | Full Confluence Cloud page URL |
| `OUTPUT_DIR` | Directory for the Markdown file and images |

### Options

| Option | Env Variable | Description |
|---|---|---|
| `--email` | `CONFLUENCE_EMAIL` | Confluence account email |
| `--api-token` | `CONFLUENCE_API_TOKEN` | Confluence Cloud API token |
| `--confluence-url` | — | Override base URL extracted from page URL |
| `--ai-provider` | `CONFLUENCE_EXPORT_AI_PROVIDER` | AI provider: `anthropic` or `openai` |
| `--ai-model` | `CONFLUENCE_EXPORT_AI_MODEL` | AI model name (defaults per provider) |
| `--ai-api-key` | `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | AI provider API key |
| `--no-ai` | — | Skip AI image description generation |
| `--verbose` | — | Enable DEBUG-level logging |

## Environment Variables

| Variable | Description |
|---|---|
| `CONFLUENCE_EMAIL` | Confluence account email address |
| `CONFLUENCE_API_TOKEN` | Confluence Cloud API token |
| `CONFLUENCE_EXPORT_AI_PROVIDER` | AI provider name (`anthropic` or `openai`) |
| `CONFLUENCE_EXPORT_AI_MODEL` | AI model name |
| `ANTHROPIC_API_KEY` | Anthropic API key (used when provider is `anthropic`) |
| `OPENAI_API_KEY` | OpenAI API key (used when provider is `openai`) |

## AI Provider Configuration

### Anthropic Claude (default)

```bash
export CONFLUENCE_EXPORT_AI_PROVIDER="anthropic"
export ANTHROPIC_API_KEY="sk-ant-..."
# Default model: claude-sonnet-4-20250514
```

### OpenAI GPT-4o

```bash
export CONFLUENCE_EXPORT_AI_PROVIDER="openai"
export OPENAI_API_KEY="sk-..."
# Default model: gpt-4o
```

For Gliffy diagrams, the AI prompt focuses on process flow elements: activities, decision points, swimlanes, transitions, and text labels.

## Output Structure

```
output/
├── My_Page.md              # Converted Markdown with front-matter
└── images/
    ├── architecture.png     # Downloaded inline images
    ├── process_flow.png     # Gliffy diagram PNG previews
    └── ...
```

### Example Output

```markdown
---
source_url: https://acme.atlassian.net/wiki/spaces/ENG/pages/12345/My-Page
page_id: '12345'
page_title: My Page
export_timestamp: '2024-01-15T10:30:00+00:00'
exporter_version: 0.1.0
space_key: ENG
labels:
- sdp
- process
---

# My Page

This document describes the software development process.

![Architecture Diagram](images/architecture.png)

> **Image Description:** A high-level architecture diagram showing the system's
> main components: the API gateway, microservices layer, and database cluster.
> Arrows indicate data flow between components.

## Process Overview

The development process follows ASPICE guidelines.

- Step 1: Requirements analysis
- Step 2: Design and implementation
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only property-based tests
pytest tests/property/

# Run only integration tests
pytest tests/integration/

# Run with dev profile (faster, 50 examples)
pytest --hypothesis-profile=dev
```

## License

MIT
