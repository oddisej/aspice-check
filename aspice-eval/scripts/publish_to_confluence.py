"""Publish a Markdown report to Confluence Cloud as a new or updated page.

Converts the Markdown to Confluence storage format (XHTML) and creates
or updates a Confluence page via the REST API.

Usage:
    python publish_to_confluence.py <input.md> \
        --space SPACEKEY \
        --title "Page Title" \
        --email user@example.com \
        --token YOUR_API_TOKEN \
        [--url https://your-instance.atlassian.net/wiki] \
        [--parent-id 12345]

Environment variables (fallback for CLI args):
    CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN, CONFLUENCE_URL
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

# Add src to path so we can import aspice_eval
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from aspice_eval.report_generator import ReportGenerator


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish a Markdown report to Confluence Cloud."
    )
    parser.add_argument("input", help="Path to the Markdown report file.")
    parser.add_argument(
        "--space", required=True, help="Confluence space key (e.g. ENG)."
    )
    parser.add_argument(
        "--title", required=True, help="Page title in Confluence."
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("CONFLUENCE_EMAIL"),
        help="Confluence email (env: CONFLUENCE_EMAIL).",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("CONFLUENCE_API_TOKEN"),
        help="Confluence API token (env: CONFLUENCE_API_TOKEN).",
    )
    parser.add_argument(
        "--url",
        default=os.environ.get(
            "CONFLUENCE_URL", "https://your-instance.atlassian.net/wiki"
        ),
        help="Confluence base URL (env: CONFLUENCE_URL).",
    )
    parser.add_argument(
        "--parent-id",
        default=None,
        help="Parent page ID (optional — creates under space root if omitted).",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update existing page instead of creating a new one.",
    )

    args = parser.parse_args()

    if not args.email or not args.token:
        print(
            "Error: --email and --token are required "
            "(or set CONFLUENCE_EMAIL / CONFLUENCE_API_TOKEN).",
            file=sys.stderr,
        )
        sys.exit(1)

    # Read and convert Markdown to HTML (Confluence storage format)
    md_content = pathlib.Path(args.input).read_text(encoding="utf-8")

    # Strip emoji that the Fabric editor may reject — do this BEFORE HTML conversion
    import re as _re
    # Remove common emoji and emoji variation selectors
    md_content = md_content.replace("⚠️", "[!]")
    md_content = md_content.replace("⚠", "[!]")
    md_content = md_content.replace("✅", "[OK]")
    md_content = md_content.replace("❌", "[X]")
    md_content = md_content.replace("💡", "[TIP]")
    md_content = md_content.replace("ℹ️", "[INFO]")
    md_content = md_content.replace("ℹ", "[INFO]")
    # Strip any remaining emoji (Unicode emoji block)
    md_content = _re.sub(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF]", "", md_content)

    html_content = ReportGenerator._markdown_to_html(md_content)

    try:
        from atlassian import Confluence
    except ImportError:
        print(
            "Error: atlassian-python-api is required. "
            "Install with: pip install atlassian-python-api",
            file=sys.stderr,
        )
        sys.exit(1)

    confluence = Confluence(
        url=args.url,
        username=args.email,
        password=args.token,
        cloud=True,
    )

    # Convert HTML to Confluence storage format using the conversion API
    # This ensures the content is compatible with the Fabric editor
    storage_content = _convert_to_storage(confluence, html_content)

    if args.update:
        # Find existing page by title
        page = confluence.get_page_by_title(args.space, args.title)
        if not page:
            print(
                f"Error: Page '{args.title}' not found in space '{args.space}'.",
                file=sys.stderr,
            )
            sys.exit(1)

        page_id = page["id"]

        confluence.update_page(
            page_id=page_id,
            title=args.title,
            body=storage_content,
            type="page",
            representation="storage",
        )
        page_url = f"{args.url}/spaces/{args.space}/pages/{page_id}"
        print(f"Updated page: {page_url}")
    else:
        # Create new page
        result = confluence.create_page(
            space=args.space,
            title=args.title,
            body=storage_content,
            parent_id=args.parent_id,
            type="page",
            representation="storage",
        )
        page_id = result.get("id", result) if isinstance(result, dict) else "unknown"
        page_url = f"{args.url}/spaces/{args.space}/pages/{page_id}"
        print(f"Created page: {page_url}")


def _convert_to_storage(confluence, html_content: str) -> str:
    """Convert HTML to Confluence storage format using the conversion API.

    Confluence provides a ``/rest/api/contentbody/convert/storage``
    endpoint that converts various representations (wiki, editor, view)
    to the storage format that the Fabric editor accepts.
    """
    session = confluence._session
    base = confluence.url.rstrip("/")
    url = f"{base}/rest/api/contentbody/convert/storage"

    response = session.post(
        url,
        json={
            "value": html_content,
            "representation": "editor",
        },
        headers={"Content-Type": "application/json"},
    )

    if response.status_code == 200:
        data = response.json()
        converted = data.get("value", html_content)
        print(f"Converted HTML to storage format ({len(converted)} chars)")
        return converted

    # If conversion fails, fall back to raw HTML
    print(
        f"Warning: Content conversion failed ({response.status_code}), "
        "using raw HTML. Page may not render correctly.",
        file=sys.stderr,
    )
    return html_content


def _get_space_id(confluence, space_key: str) -> str:
    """Get the numeric space ID from a space key."""
    space = confluence.get_space(space_key)
    return str(space.get("id", ""))


if __name__ == "__main__":
    main()
