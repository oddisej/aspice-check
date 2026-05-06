# confluence-ai

General-purpose AI-powered Confluence toolkit — export, publish, and describe pages.

## Library Usage

### Export a Page

```python
from confluence_ai import export_page, ImageDescriberConfig

# Export with AI-powered image descriptions
result = export_page(
    "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456/My-Page",
    "./output",
    email="user@acme.com",
    api_token="your-api-token",
    ai_config=ImageDescriberConfig(
        provider="bedrock",
        model="us.anthropic.claude-sonnet-4-20250514-v1:0",
    ),
)
print(f"Exported to: {result.markdown_path}")
print(f"Images: {result.images_downloaded}, Descriptions: {result.descriptions_generated}")

# Export without AI descriptions
result = export_page(
    "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456/My-Page",
    "./output",
    email="user@acme.com",
    api_token="your-api-token",
)
```

### Publish a Page

```python
from confluence_ai import publish_page

url = publish_page(
    "<h1>Report</h1><p>Analysis results...</p>",
    email="user@acme.com",
    api_token="your-api-token",
    base_url="https://acme.atlassian.net/wiki",
    space_key="ENG",
    title="Gap Analysis Report - 2024-01-15",
    parent_page_id="123456",
)
print(f"Published: {url}")
```

### Export as JSON

```python
from confluence_ai import export_page

result = export_page(
    "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456/My-Page",
    "./output",
    email="user@acme.com",
    api_token="your-api-token",
    output_format="json",
)
```

### List Calendars from a Page

```python
from confluence_ai.calendar_client import CalendarClient

client = CalendarClient(
    base_url="https://acme.atlassian.net/wiki",
    email="user@acme.com",
    api_token="your-api-token",
)
calendars = client.list_calendars_from_page(
    "https://acme.atlassian.net/wiki/spaces/ENG/pages/123/Team-Calendar"
)
for cal in calendars:
    print(f"{cal.name} ({len(cal.sub_calendars)} subcalendars)")
```

### Export Calendar Events

```python
from confluence_ai import export_calendar_grouped

# Export all events from a parent calendar as a unified view
result = export_calendar_grouped(
    base_url="https://acme.atlassian.net/wiki",
    calendar_id="31fc5bcc-b80d-4a27-bed1-5a33eb83001d",
    output_dir="./calendar-output",
    email="user@acme.com",
    api_token="your-api-token",
    output_format="json",  # or "markdown"
)
print(f"Exported {result.event_count} events to {result.output_path}")
```

`export_calendar_grouped` resolves the parent calendar's descriptive name, fetches events from all child subcalendars, and produces a single unified output file. In Markdown format, events from multiple subcalendars include a `Calendar:` provenance sub-bullet.

The lower-level `export_calendar` function is also available if you don't need parent name resolution.

## Extension Points

### Custom Image Describer

Subclass `ImageDescriber` and register it to use your own vision model:

```python
from confluence_ai import ImageDescriber, ImageDescriberConfig, ImageContext, register_describer

class LocalLlavaDescriber(ImageDescriber):
    """Image describer using a local LLaVA model."""

    def describe(self, image_path: str, context: ImageContext) -> str:
        # Call your local model here
        return f"Description of {context.filename}"

# Register the custom provider
register_describer("local-llava", LocalLlavaDescriber)

# Use it via the standard factory
from confluence_ai import create_describer

describer = create_describer(ImageDescriberConfig(provider="local-llava", model="llava-1.5"))
description = describer.describe("diagram.png", ImageContext(is_gliffy=True))
```

### Custom Output Renderer

Subclass `OutputRenderer` to export pages in formats beyond Markdown and JSON:

```python
from confluence_ai import OutputRenderer, register_renderer
from confluence_ai.models import ContentNode, PageMetadata

class ReStructuredTextRenderer(OutputRenderer):
    """Render Confluence pages as reStructuredText."""

    def render(
        self,
        nodes: list[ContentNode],
        metadata: PageMetadata,
        descriptions: dict[str, str] | None = None,
    ) -> str:
        # Convert nodes to RST format
        lines = [metadata.page_title, "=" * len(metadata.page_title), ""]
        # ... render nodes ...
        return "\n".join(lines)

# Register and use
register_renderer("rst", ReStructuredTextRenderer)

from confluence_ai import export_page

result = export_page(
    "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456/My-Page",
    "./output",
    email="user@acme.com",
    api_token="your-api-token",
    output_format="rst",
)
```

## CLI Usage

### confluence-export

```bash
# Basic export (no AI descriptions)
confluence-export \
  "https://acme.atlassian.net/wiki/spaces/ENG/pages/12345/My-Page" \
  ./output \
  --email user@example.com \
  --api-token YOUR_API_TOKEN \
  --no-ai

# Export with AI image descriptions
confluence-export \
  "https://acme.atlassian.net/wiki/spaces/ENG/pages/12345/My-Page" \
  ./output \
  --email user@example.com \
  --api-token YOUR_API_TOKEN \
  --ai-provider anthropic \
  --ai-api-key YOUR_ANTHROPIC_KEY
```

| Option | Env Variable | Description |
|---|---|---|
| `--email` | `CONFLUENCE_EMAIL` | Confluence account email |
| `--api-token` | `CONFLUENCE_API_TOKEN` | Confluence Cloud API token |
| `--ai-provider` | `CONFLUENCE_EXPORT_AI_PROVIDER` | AI provider: `anthropic`, `openai`, or `bedrock` |
| `--ai-model` | `CONFLUENCE_EXPORT_AI_MODEL` | AI model name |
| `--ai-api-key` | `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | AI provider API key |
| `--no-ai` | — | Skip AI image description generation |
| `--verbose` | — | Enable DEBUG-level logging |

## Installation

```bash
pip install confluence-ai

# With AI provider support
pip install "confluence-ai[bedrock]"    # Amazon Bedrock (Claude)
pip install "confluence-ai[openai]"     # OpenAI GPT-4o
pip install "confluence-ai[anthropic]"  # Anthropic Claude (direct API)
pip install "confluence-ai[all]"        # All providers
```

Requires Python 3.10+.

## License

MIT
