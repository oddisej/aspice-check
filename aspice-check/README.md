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

An MCP (Model Context Protocol) server exposing evaluation and Confluence tools to AI assistants. It uses **stdio transport** (JSON-RPC 2.0) and works with any MCP-compatible client.

### Configuration

The server is configured in your MCP client's config file. The exact location depends on the client:

| Client | Config file |
|--------|-------------|
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude Desktop (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Kiro | `.kiro/settings/mcp.json` (workspace) or `~/.kiro/settings/mcp.json` (global) |
| VS Code (Copilot) | `.vscode/mcp.json` |

Add the following to your config:

```json
{
  "mcpServers": {
    "aspice": {
      "command": "aspice-mcp",
      "args": [],
      "env": {
        "CONFLUENCE_EMAIL": "user@acme.com",
        "CONFLUENCE_API_TOKEN": "your-token",
        "AWS_DEFAULT_REGION": "us-east-1"
      }
    }
  }
}
```

The `env` block passes credentials to the server process. Tools that need Confluence access (`export_page`) or AI providers (`evaluate_sdp`, `describe_image`) will use these values. You can omit credentials here and pass them per-tool-call instead.

If `aspice-mcp` is not on your `PATH` (e.g. installed in a virtualenv), use the full path:

```json
{
  "mcpServers": {
    "aspice": {
      "command": "/path/to/venv/bin/aspice-mcp",
      "args": []
    }
  }
}
```

### Starting Manually (for testing)

```bash
aspice-mcp
```

The server reads JSON-RPC requests from stdin and writes responses to stdout. Logs go to stderr.

### Tool Inventory

| Tool | Description |
|------|-------------|
| `evaluate_sdp` | Evaluate an SDP document against ASPICE knowledge base criteria |
| `validate_kb` | Validate a knowledge base directory for schema compliance and completeness |
| `list_standards` | List available knowledge base standards and their process groups |
| `export_page` | Export a Confluence Cloud page to Markdown with AI image descriptions |
| `publish_page` | Publish content to Confluence Cloud as a page |
| `describe_image` | Generate an AI description of an image file |
| `list_calendars` | Discover Team Calendars referenced by a Confluence page |
| `export_calendar` | Export events from a Team Calendar to JSON or Markdown (unified subcalendar view) |

### Tool Parameters

**evaluate_sdp** — `provider` (required), `model` (required), `sdp_path`, `sdp_content`, `target_level` (1–5, default 3), `process_groups`, `standard`

**validate_kb** — `kb_path` (required), `standard`

**list_standards** — `kb_path` (optional, uses bundled KB if omitted)

**export_page** — `page_url` (required), `output_dir` (required), `email` (required), `api_token` (required), `ai_provider`, `ai_model`, `output_format`

**describe_image** — `image_path` (required), `provider` (required), `model` (required), `is_gliffy`, `page_title`

**publish_page** — `base_url` (required), `space_key` (required), `title` (required), `file_path`, `html_content`, `parent_page_id`, `email`, `api_token`

**list_calendars** — `base_url` (required), `page_url` (required), `email`, `api_token`

**export_calendar** — `base_url` (required), `calendar_id` (required), `output_dir` (required), `output_format` (`json` or `markdown`, default `json`), `start_date`, `end_date`, `email`, `api_token`

### Example Tool Call (JSON-RPC)

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "validate_kb", "arguments": {"kb_path": "/path/to/knowledge_base", "standard": "aspice"}}}
```

Response:

```json
{"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "{\"is_valid\": true, ...}"}]}}
```

### Error Handling

Invalid parameters return a structured error with code `-32602`:

```json
{"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Invalid params", "data": {"tool": "evaluate_sdp", "parameter": "provider", "actual_value": "gpt", "valid_values": ["bedrock", "openai", "anthropic"], "suggestion": "Use one of: bedrock, openai, anthropic"}}}
```

## Installation

### From the monorepo (development)

Install all three packages in editable mode from the repo root:

```bash
pip install -e ./confluence-ai
pip install -e ./aspice-eval
pip install -e ./aspice-check
```

This registers the `aspice-analyze` and `aspice-mcp` commands in your environment. Verify:

```bash
which aspice-mcp
# → /path/to/venv/bin/aspice-mcp
```

### From PyPI (once published)

```bash
pip install aspice-check
```

This pulls in `confluence-ai` and `aspice-eval` automatically.

### Making `aspice-mcp` available to MCP clients

MCP clients launch the server as a subprocess, so the `aspice-mcp` command must be resolvable from the client's environment. Two options:

1. **Use the absolute path** in your MCP config (works regardless of PATH):
   ```json
   { "command": "/path/to/venv/bin/aspice-mcp" }
   ```

2. **Activate the venv** before launching the client, or install into the system Python so `aspice-mcp` is on the global PATH.

To find the path after installing:
```bash
which aspice-mcp
```

Requires Python 3.10+.

## License

MIT
