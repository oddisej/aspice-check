"""Property 6: Invalid URL Rejection.

**Validates: Requirements 6.7**

For any string that does NOT match the Confluence Cloud page URL pattern

    ``^https://[^/]+\\.atlassian\\.net/wiki/spaces/[^/]+/pages/\\d+``

calling :func:`confluence_ai.export.export_page` with non-empty credentials
SHALL raise :class:`~confluence_ai.exceptions.InvalidURLError`. We supply
non-empty credentials so the credential validation short-circuit does not
fire before the URL check.
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.exceptions import InvalidURLError
from confluence_ai.export import export_page


# The exact pattern ``URLParser`` uses to recognise a valid Confluence
# Cloud page URL. Any generated string NOT matching this is invalid.
_CONFLUENCE_CLOUD_RE = re.compile(
    r"^https://[^/]+\.atlassian\.net/wiki/spaces/[^/]+/pages/\d+"
)


# Strategy producing strings that are definitely *not* valid Confluence
# Cloud page URLs. We combine hand-picked edge cases with free-form text
# filtered to exclude any accidental matches.
_invalid_url_st = st.one_of(
    st.just(""),
    st.just("not-a-url"),
    st.just("https://example.com/page/123"),
    st.just("http://acme.atlassian.net/wiki/spaces/DEV/pages/123"),  # http
    st.just("https://acme.atlassian.net/spaces/DEV/pages/123"),  # missing /wiki
    st.just("https://acme.atlassian.net/wiki/spaces/DEV/pages/"),  # no page id
    st.just("ftp://acme.atlassian.net/wiki/spaces/DEV/pages/1"),  # wrong scheme
    st.text(min_size=0, max_size=120).filter(
        lambda s: not _CONFLUENCE_CLOUD_RE.match(s)
    ),
)


class TestProperty06InvalidURL:
    """Property 6: Non-Confluence URLs are rejected with InvalidURLError."""

    @given(bad_url=_invalid_url_st)
    @settings(max_examples=100, deadline=None)
    def test_invalid_urls_raise_invalid_url_error(
        self,
        bad_url: str,
    ) -> None:
        """``export_page`` raises ``InvalidURLError`` for non-Confluence URLs.

        The error must fire before any filesystem or network I/O, so the
        output directory is never touched and we pass a dummy path.

        **Validates: Requirements 6.7**
        """
        # Use non-empty credentials so the credential check passes and
        # the URL check is what triggers the error.
        with pytest.raises(InvalidURLError):
            export_page(
                bad_url,
                "/tmp/never-written",
                email="user@example.com",
                api_token="placeholder-token",
            )
