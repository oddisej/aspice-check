"""High-level convenience function for publishing pages to Confluence.

Handles HTML-to-storage-format conversion (via the Confluence
conversion API), emoji sanitization (stripping Unicode characters
rejected by the Fabric editor), and title-based page deduplication
(update vs create) so callers do not need to manage these
Confluence-specific details.

Requirements: 3.6, 7.1, 7.2, 7.3, 7.4, 7.5, 7.7, 22.6
"""

from __future__ import annotations

import logging
import re
from typing import Any

from atlassian import Confluence

from confluence_ai.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


# Emoji replacements that preserve semantic meaning as ASCII tokens.
# The Confluence Fabric editor silently rejects several Unicode
# codepoints; these substitutions keep reports readable after publish.
_EMOJI_REPLACEMENTS: dict[str, str] = {
    "\u26a0\ufe0f": "[!]",  # ⚠️  warning sign + variation selector
    "\u26a0": "[!]",         # ⚠   warning sign (no VS)
    "\u2705": "[OK]",       # ✅
    "\u274c": "[X]",        # ❌
    "\U0001f4a1": "[TIP]",  # 💡
    "\u2139\ufe0f": "[INFO]",  # ℹ️
    "\u2139": "[INFO]",       # ℹ
}

# Strip remaining emoji blocks:
#   Emoticons                        U+1F600..U+1F64F
#   Miscellaneous symbols & pictographs U+1F300..U+1F5FF
#   Transport and map symbols        U+1F680..U+1F6FF
#   Supplemental symbols & pictographs  U+1F900..U+1F9FF
_EMOJI_RE = re.compile(
    r"[\U0001F600-\U0001F64F"
    r"\U0001F300-\U0001F5FF"
    r"\U0001F680-\U0001F6FF"
    r"\U0001F900-\U0001F9FF]"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sanitize_emoji(html_content: str) -> str:
    """Replace or strip emoji from HTML content.

    Known-meaningful emoji are substituted with ASCII equivalents
    (e.g. ``⚠️`` → ``[!]``). Everything else in the standard emoji
    blocks is stripped. The substitution order matters: variation-
    selector variants are replaced before their plain counterparts.
    """
    for emoji, replacement in _EMOJI_REPLACEMENTS.items():
        html_content = html_content.replace(emoji, replacement)
    return _EMOJI_RE.sub("", html_content)


def _set_full_width(confluence: Any, base_url: str, page_id: str) -> None:
    """Set a Confluence page to full-width layout.

    Updates the ``content-appearance-published`` and
    ``content-appearance-draft`` properties so the page renders
    edge-to-edge rather than in the narrow centered column.
    """
    session = confluence._session
    base = base_url.rstrip("/")

    for key in ("content-appearance-published", "content-appearance-draft"):
        prop_url = f"{base}/rest/api/content/{page_id}/property/{key}"
        resp = session.get(prop_url)
        if resp.status_code == 200:
            version = resp.json().get("version", {}).get("number", 0) + 1
            payload = {
                "key": key,
                "value": "full-width",
                "version": {"number": version},
            }
            session.put(prop_url, json=payload)
        else:
            # Property doesn't exist yet — create it
            props_url = (
                f"{base}/rest/api/content/{page_id}/property"
            )
            payload = {
                "key": key,
                "value": "full-width",
                "version": {"number": 1},
            }
            session.post(props_url, json=payload)

    logger.info("Set page %s to full-width layout", page_id)


def _convert_to_storage(
    confluence: Any, base_url: str, html_content: str
) -> str:
    """Convert HTML to Confluence storage format via the conversion API.

    Falls back to the raw HTML if the conversion endpoint is unavailable
    or returns a non-200 response.
    """
    session = confluence._session
    base = base_url.rstrip("/")
    url = f"{base}/rest/api/contentbody/convert/storage"

    response = session.post(
        url,
        json={"value": html_content, "representation": "editor"},
        headers={"Content-Type": "application/json"},
    )

    if response.status_code == 200:
        data = response.json()
        converted = data.get("value", html_content)
        logger.info(
            "Converted HTML to storage format (%d chars)", len(converted)
        )
        return converted

    logger.warning(
        "Content conversion failed (HTTP %d), using raw HTML",
        response.status_code,
    )
    return html_content


# ---------------------------------------------------------------------------
# Public convenience function
# ---------------------------------------------------------------------------


def publish_page(
    html_content: str,
    *,
    email: str,
    api_token: str,
    base_url: str,
    space_key: str,
    title: str,
    parent_page_id: str | None = None,
    full_width: bool = True,
) -> str:
    """Publish HTML content to Confluence Cloud as a page.

    Handles HTML-to-storage-format conversion via the Confluence
    conversion API, emoji sanitization (stripping Unicode characters
    rejected by the Fabric editor), and page deduplication — if a
    page with this ``title`` already exists in ``space_key``, it is
    updated rather than creating a duplicate.

    Parameters
    ----------
    html_content:
        HTML string to publish as the page body.
    email:
        Confluence account email for authentication. Must be non-empty.
    api_token:
        Confluence Cloud API token. Must be non-empty.
    base_url:
        Confluence Cloud base URL (e.g.,
        ``"https://acme.atlassian.net/wiki"``).
    space_key:
        Confluence space key where the page will be created or updated.
    title:
        Page title. Used for deduplication.
    parent_page_id:
        Optional parent page ID. Only used when creating a new page.
    full_width:
        If ``True`` (default), set the page layout to full-width after
        publishing so content stretches across the entire page.

    Returns
    -------
    str
        URL of the created or updated Confluence page.

    Raises
    ------
    AuthenticationError
        If ``email`` or ``api_token`` is empty or ``None``. The message
        names the missing field.

    Examples
    --------
    Publish a gap analysis report as a child of an existing SDP page::

        from confluence_ai import publish_page

        url = publish_page(
            "<h1>Gap Analysis Report</h1><p>Results...</p>",
            email="user@acme.com",
            api_token="secret-token",
            base_url="https://acme.atlassian.net/wiki",
            space_key="ENG",
            title="SDP Gap Analysis - 2024-01-15",
            parent_page_id="123456",
        )
        print(url)

    Publish a standalone page (no parent)::

        url = publish_page(
            "<h1>Architecture Overview</h1><p>...</p>",
            email="user@acme.com",
            api_token="secret-token",
            base_url="https://acme.atlassian.net/wiki",
            space_key="ENG",
            title="Architecture Overview",
        )
    """
    # --- 1. Validate credentials up front ------------------------------
    if not email:
        raise AuthenticationError(
            base_url=base_url,
            message=(
                "Confluence email is required but was empty or None. "
                "Pass a non-empty value via the 'email' parameter."
            ),
        )
    if not api_token:
        raise AuthenticationError(
            base_url=base_url,
            message=(
                "Confluence API token is required but was empty or "
                "None. Pass a non-empty value via the 'api_token' "
                "parameter."
            ),
        )

    # --- 2. Sanitize emoji (Fabric editor rejects several codepoints) --
    sanitized_html = _sanitize_emoji(html_content)

    # --- 3. Construct client -------------------------------------------
    confluence = Confluence(
        url=base_url,
        username=email,
        password=api_token,
        cloud=True,
    )

    # --- 4. Convert HTML to Confluence storage format ------------------
    storage_content = _convert_to_storage(
        confluence, base_url, sanitized_html
    )

    # --- 5. Deduplicate by title: update if it exists, else create ----
    try:
        existing = confluence.get_page_by_title(space_key, title)
    except Exception:
        existing = None

    base = base_url.rstrip("/")

    if existing:
        existing_id = existing["id"]
        confluence.update_page(
            page_id=existing_id,
            title=title,
            body=storage_content,
            type="page",
            representation="storage",
        )
        page_url = f"{base}/spaces/{space_key}/pages/{existing_id}"
        logger.info("Updated existing page: %s", page_url)
        if full_width:
            _set_full_width(confluence, base_url, existing_id)
        return page_url

    result = confluence.create_page(
        space=space_key,
        title=title,
        body=storage_content,
        parent_id=parent_page_id,
        type="page",
        representation="storage",
    )
    new_id = (
        result.get("id", "unknown") if isinstance(result, dict) else "unknown"
    )
    page_url = f"{base}/spaces/{space_key}/pages/{new_id}"
    logger.info("Created new page: %s", page_url)
    if full_width and new_id != "unknown":
        _set_full_width(confluence, base_url, new_id)
    return page_url
