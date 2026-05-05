"""URL parser for Confluence Cloud page URLs.

Extracts the base URL and numeric page ID from Confluence Cloud URL patterns.
Raises InvalidURLError for URLs that do not match the expected format.
"""

from __future__ import annotations

import re

from confluence_ai.exceptions import InvalidURLError
from confluence_ai.models import ParsedURL


class URLParser:
    """Extracts base URL and page ID from Confluence Cloud page URLs."""

    # Matches Confluence Cloud URL patterns:
    #   https://{domain}.atlassian.net/wiki/spaces/{space}/pages/{page_id}
    #   https://{domain}.atlassian.net/wiki/spaces/{space}/pages/{page_id}/{title}
    _CLOUD_URL_RE = re.compile(
        r"^(https://[^/]+\.atlassian\.net/wiki)/spaces/[^/]+/pages/(\d+)"
    )

    def parse(self, url: str) -> ParsedURL:
        """Parse a Confluence Cloud page URL.

        Args:
            url: Full Confluence Cloud page URL.

        Returns:
            ParsedURL with base_url and page_id.

        Raises:
            InvalidURLError: If the URL doesn't match expected Confluence
                Cloud patterns.
        """
        match = self._CLOUD_URL_RE.match(url)
        if not match:
            raise InvalidURLError(url)
        return ParsedURL(base_url=match.group(1), page_id=match.group(2))
