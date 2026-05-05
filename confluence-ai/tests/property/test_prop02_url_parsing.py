"""Property 2: URL parser extracts correct page ID from valid URLs and rejects invalid URLs.

*For any* string matching the Confluence Cloud URL pattern
``https://{domain}.atlassian.net/wiki/spaces/{space}/pages/{page_id}/{optional_title}``,
the URL parser SHALL extract the numeric page ID correctly. *For any* string that
does not match this pattern, the URL parser SHALL raise an ``InvalidURLError``
with a message describing the expected format.

**Validates: Requirements 2.1, 2.3**

Feature: confluence-ai, Property 2: URL parser extracts correct page ID from valid URLs and rejects invalid URLs
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.exceptions import InvalidURLError
from confluence_ai.url_parser import URLParser

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for valid Confluence Cloud URL components
_domain_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=30,
).filter(lambda s: s.isalnum())

_space_key_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
).filter(lambda s: s.isalnum())

_page_id_strategy = st.integers(min_value=1, max_value=10**15).map(str)

_optional_title_strategy = st.one_of(
    st.just(""),
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
        min_size=1,
        max_size=50,
    ).filter(lambda s: s.strip()),
)

# Strategy for invalid URLs — strings that don't match the Confluence pattern
_invalid_url_strategy = st.one_of(
    st.just(""),
    st.just("not-a-url"),
    st.just("https://example.com/page/123"),
    st.just("https://acme.atlassian.net/spaces/DEV/pages/123"),  # missing /wiki
    st.just("http://acme.atlassian.net/wiki/spaces/DEV/pages/123"),  # http not https
    st.text(min_size=0, max_size=100).filter(
        lambda s: not re.match(
            r"^https://[^/]+\.atlassian\.net/wiki/spaces/[^/]+/pages/\d+", s
        )
    ),
)


class TestProperty02URLParsing:
    """Property 2: URL parser extracts correct page ID and rejects invalid URLs."""

    @given(
        domain=_domain_strategy,
        space=_space_key_strategy,
        page_id=_page_id_strategy,
        title=_optional_title_strategy,
    )
    @settings(max_examples=100)
    def test_valid_urls_extract_correct_page_id(
        self,
        domain: str,
        space: str,
        page_id: str,
        title: str,
    ) -> None:
        """Valid Confluence Cloud URLs yield the correct page ID and base URL.

        **Validates: Requirements 2.1**
        """
        base_url = f"https://{domain}.atlassian.net/wiki"
        url = f"{base_url}/spaces/{space}/pages/{page_id}"
        if title:
            url += f"/{title}"

        parser = URLParser()
        result = parser.parse(url)

        assert result.page_id == page_id, (
            f"Expected page_id={page_id!r}, got {result.page_id!r} for URL {url!r}"
        )
        assert result.base_url == base_url, (
            f"Expected base_url={base_url!r}, got {result.base_url!r} for URL {url!r}"
        )

    @given(url=_invalid_url_strategy)
    @settings(max_examples=100)
    def test_invalid_urls_raise_error(self, url: str) -> None:
        """Invalid strings raise InvalidURLError.

        **Validates: Requirements 2.3**
        """
        parser = URLParser()
        with pytest.raises(InvalidURLError):
            parser.parse(url)
