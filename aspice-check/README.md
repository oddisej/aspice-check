# aspice-check

Orchestrator composing `confluence-ai` and `aspice-eval` into a pipeline CLI and MCP server.

## Pipeline CLI — aspice-analyze

Run a full ASPICE gap analysis pipeline on a Confluence SDP page: export → evaluate → publish.

### Usage

```bash
aspice-analyze <PAGE_URL> --target-level <1-5> --groups <GROUPS> [OPTIONS]
```

### Examples

```bash
# Full pipeline: export, evaluate at level 2, publish report back to Confluence
aspice-analyze \
  "https://acme.atlassian.net/wiki/spaces/ENG/pages/12345/My-SDP" \
  --target-level 2 \
  --groups SWE,MAN \
  --email user@acme.com \
  --api-token YOUR_TOKEN \
  --region us-east-1

# Evaluate without publishing
aspice-analyze \
  "https://acme.atlassian.net/wiki/spaces/ENG/pages/12345/My-SDP" \
  --target-level 1 \
  --groups SWE \
  --no-publish

# Use OpenAI instead of Bedrock
aspice-analyze \
  "https://acme.atlassian.net/wiki/spaces/ENG/pages/12345/My-SDP" \
  --target-level 3 \
  --groups SWE,SYS,MAN,SUP \
  --provider openai \
  --model gpt-4o
```

### Options

| Option | Env Variable | Description |
|---|---|---|
| `PAGE_URL` | — | Confluence Cloud page URL (required) |
| `--target-level` | — | ASPICE capability level 1–5 (required) |
| `--groups` | — | Comma-separated process groups, e.g. `SWE,MAN` (required) |
| `--email` | `CONFLUENCE_EMAIL` | Confluence account email |
| `--api-token` | `CONFLUENCE_API_TOKEN` | Confluence API token |
| `--provider` | `ASPICE_EVAL_PROVIDER` | AI provider: `bedrock`, `openai`, `anthropic` (default: `bedrock`) |
| `--model` | — | AI model name (default depends on provider) |
| `--region` | `AWS_DEFAULT_REGION` | AWS region (required for Bedrock) |
| `--report-title` | — | Custom title for the published report page |
| `--output-dir` | — | Local directory for intermediate artifacts |
| `--no-publish` | — | Skip publishing report to Confluence |
| `--verbose` | — | Enable DEBUG-level logging |
| `--quiet` | — | Suppress progress messages |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Parameter validation error |
| 2 | Export stage failure |
| 3 | Evaluation stage failure |
| 4 | Publish stage failure |

## MCP Server — aspice-mcp

An MCP (Model Context Protocol) server exposing evaluation and Confluence tools to AI assistants.

### Starting the Server

```bash
aspice-mcp
```

The server communicates via **stdio transport** (JSON-RPC 2.0). Connect it to any MCP-compatible client (Claude Desktop, Copilot, custom agents).

### Configuration (Claude Desktop)

Add to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "aspice": {
      "command": "aspice-mcp",
      "args": []
    }
  }
}
```

### Tool Inventory

| Tool | Description |
|------|-------------|
| `evaluate_sdp` | Evaluate an SDP document against ASPICE knowledge base criteria |
| `validate_kb` | Validate a knowledge base directory for schema compliance and completeness |
| `list_standards` | List available knowledge base standards and their process groups |
| `export_page` | Export a Confluence Cloud page to Markdown with AI image descriptions |
| `describe_image` | Generate an AI description of an image file |

### Tool Parameters

**evaluate_sdp** — `provider` (required), `model` (required), `sdp_path`, `sdp_content`, `target_level` (1–5, default 3), `process_groups`, `standard`

**validate_kb** — `kb_path` (required), `standard`

**list_standards** — `kb_path` (optional, uses bundled KB if omitted)

**export_page** — `page_url` (required), `output_dir` (required), `email` (required), `api_token` (required), `ai_provider`, `ai_model`, `output_format`

**describe_image** — `image_path` (required), `provider` (required), `model` (required), `is_gliffy`, `page_title`

## Installation

```bash
pip install aspice-check
```

This installs both `confluence-ai` and `aspice-eval` as dependencies, plus the `aspice-analyze` and `aspice-mcp` CLI commands.

Requires Python 3.10+.

## License

MIT
