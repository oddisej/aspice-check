"""Unit tests for the URL parser module.

Tests that URLParser correctly extracts base URL and page ID from valid
Confluence Cloud URLs and raises InvalidURLError for invalid inputs.
"""

from __future__ import annotations

import pytest

from confluence_exporter.exceptions import InvalidURLError
from confluence_exporter.url_parser import URLParser


@pytest.fixture
def parser() -> URLParser:
    return URLParser()


class TestURLParserValidURLs:
    """Tests for valid Confluence Cloud URL patterns."""

    def test_standard_url_with_title(self, parser: URLParser) -> None:
        result = parser.parse(
            "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456789/My+Page+Title"
        )
        assert result.base_url == "https://acme.atlassian.net/wiki"
        assert result.page_id == "123456789"

    def test_url_without_title(self, parser: URLParser) -> None:
        result = parser.parse(
            "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456789"
        )
        assert result.base_url == "https://acme.atlassian.net/wiki"
        assert result.page_id == "123456789"

    def test_different_domain(self, parser: URLParser) -> None:
        result = parser.parse(
            "https://my-company.atlassian.net/wiki/spaces/DEV/pages/42/Some+Title"
        )
        assert result.base_url == "https://my-company.atlassian.net/wiki"
        assert result.page_id == "42"

    def test_large_page_id(self, parser: URLParser) -> None:
        result = parser.parse(
            "https://test.atlassian.net/wiki/spaces/SPACE/pages/99999999999/Title"
        )
        assert result.page_id == "99999999999"

    def test_single_digit_page_id(self, parser: URLParser) -> None:
        result = parser.parse(
            "https://x.atlassian.net/wiki/spaces/S/pages/1"
        )
        assert result.page_id == "1"

    def test_url_with_trailing_slash(self, parser: URLParser) -> None:
        result = parser.parse(
            "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456789/"
        )
        assert result.page_id == "123456789"

    def test_url_with_query_params(self, parser: URLParser) -> None:
        result = parser.parse(
            "https://acme.atlassian.net/wiki/spaces/ENG/pages/123/Title?version=2"
        )
        assert result.page_id == "123"

    def test_url_with_fragment(self, parser: URLParser) -> None:
        result = parser.parse(
            "https://acme.atlassian.net/wiki/spaces/ENG/pages/456/Title#section"
        )
        assert result.page_id == "456"


class TestURLParserInvalidURLs:
    """Tests for URLs that should raise InvalidURLError."""

    def test_empty_string(self, parser: URLParser) -> None:
        with pytest.raises(InvalidURLError):
            parser.parse("")

    def test_plain_text(self, parser: URLParser) -> None:
        with pytest.raises(InvalidURLError):
            parser.parse("not a url at all")

    def test_http_not_https(self, parser: URLParser) -> None:
        with pytest.raises(InvalidURLError):
            parser.parse(
                "http://acme.atlassian.net/wiki/spaces/ENG/pages/123/Title"
            )

    def test_non_atlassian_domain(self, parser: URLParser) -> None:
        with pytest.raises(InvalidURLError):
            parser.parse(
                "https://acme.example.com/wiki/spaces/ENG/pages/123/Title"
            )

    def test_missing_wiki_path(self, parser: URLParser) -> None:
        with pytest.raises(InvalidURLError):
            parser.parse(
                "https://acme.atlassian.net/spaces/ENG/pages/123/Title"
            )

    def test_missing_spaces_segment(self, parser: URLParser) -> None:
        with pytest.raises(InvalidURLError):
            parser.parse(
                "https://acme.atlassian.net/wiki/pages/123/Title"
            )

    def test_non_numeric_page_id(self, parser: URLParser) -> None:
        with pytest.raises(InvalidURLError):
            parser.parse(
                "https://acme.atlassian.net/wiki/spaces/ENG/pages/abc/Title"
            )

    def test_missing_page_id(self, parser: URLParser) -> None:
        with pytest.raises(InvalidURLError):
            parser.parse(
                "https://acme.atlassian.net/wiki/spaces/ENG/pages/"
            )

    def test_confluence_server_url(self, parser: URLParser) -> None:
        """Confluence Server/DC URLs don't match the Cloud pattern."""
        with pytest.raises(InvalidURLError):
            parser.parse(
                "https://confluence.mycompany.com/display/ENG/My+Page"
            )

    def test_error_contains_url(self, parser: URLParser) -> None:
        bad_url = "https://not-valid.example.com/page"
        with pytest.raises(InvalidURLError) as exc_info:
            parser.parse(bad_url)
        assert bad_url in str(exc_info.value)
