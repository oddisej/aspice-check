"""Unit tests for :mod:`confluence_ai.publish`.

Covers:
- Credential validation (raises ``AuthenticationError`` with actionable
  messages when ``email`` / ``api_token`` are empty or ``None``).
- Emoji sanitization (known emoji replaced with ASCII tokens; other
  emoji blocks stripped; emoji-free HTML is a no-op).
- Title-based deduplication (existing page → ``update_page``; missing
  page → ``create_page``).
- URL construction (correct spaces/pages path, no double slashes).

All Confluence HTTP I/O is mocked via ``pytest-mock`` — no network
traffic is issued by these tests.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.7
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from confluence_ai.exceptions import AuthenticationError
from confluence_ai.publish import (
    _EMOJI_RE,
    _EMOJI_REPLACEMENTS,
    _sanitize_emoji,
    publish_page,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_confluence(
    mocker,
    *,
    existing_page: dict | None = None,
    get_page_raises: bool = False,
    create_result: dict | None = None,
    converted_storage: str | None = None,
    convert_status: int = 200,
) -> MagicMock:
    """Install a mocked ``atlassian.Confluence`` in the publish module.

    Returns the mock instance so tests can assert on its methods.
    """
    # Mock the conversion-API HTTP response.
    convert_response = MagicMock()
    convert_response.status_code = convert_status
    convert_response.json.return_value = {
        "value": converted_storage if converted_storage is not None else ""
    }

    session = MagicMock()
    session.post.return_value = convert_response

    instance = MagicMock()
    instance._session = session

    # Page lookup behaviour.
    if get_page_raises:
        instance.get_page_by_title.side_effect = Exception(
            "page not found"
        )
    else:
        instance.get_page_by_title.return_value = existing_page

    instance.create_page.return_value = create_result or {"id": "999"}

    cls_mock = mocker.patch("confluence_ai.publish.Confluence")
    cls_mock.return_value = instance
    return instance


# ---------------------------------------------------------------------------
# Credential validation
# ---------------------------------------------------------------------------


class TestCredentialValidation:
    """``publish_page`` raises ``AuthenticationError`` up front."""

    @pytest.mark.parametrize("empty_email", ["", None])
    def test_empty_email_raises(self, empty_email) -> None:
        with pytest.raises(AuthenticationError) as exc_info:
            publish_page(
                "<p>x</p>",
                email=empty_email,
                api_token="token",
                base_url="https://acme.atlassian.net/wiki",
                space_key="ENG",
                title="Test",
            )
        assert "email" in str(exc_info.value).lower()

    @pytest.mark.parametrize("empty_token", ["", None])
    def test_empty_api_token_raises(self, empty_token) -> None:
        with pytest.raises(AuthenticationError) as exc_info:
            publish_page(
                "<p>x</p>",
                email="user@acme.com",
                api_token=empty_token,
                base_url="https://acme.atlassian.net/wiki",
                space_key="ENG",
                title="Test",
            )
        assert "api_token" in str(exc_info.value).lower() or (
            "api token" in str(exc_info.value).lower()
        )

    def test_missing_credentials_do_not_construct_client(
        self, mocker
    ) -> None:
        """Credentials are validated before we try to reach Confluence."""
        cls_mock = mocker.patch("confluence_ai.publish.Confluence")
        with pytest.raises(AuthenticationError):
            publish_page(
                "<p>x</p>",
                email="",
                api_token="token",
                base_url="https://acme.atlassian.net/wiki",
                space_key="ENG",
                title="Test",
            )
        cls_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Emoji sanitization
# ---------------------------------------------------------------------------


class TestSanitizeEmoji:
    """``_sanitize_emoji`` replaces meaningful emoji and strips the rest."""

    @pytest.mark.parametrize(
        "emoji, expected",
        [
            ("\u26a0\ufe0f", "[!]"),   # ⚠️
            ("\u26a0", "[!]"),          # ⚠
            ("\u2705", "[OK]"),         # ✅
            ("\u274c", "[X]"),          # ❌
            ("\U0001f4a1", "[TIP]"),    # 💡
            ("\u2139\ufe0f", "[INFO]"), # ℹ️
            ("\u2139", "[INFO]"),       # ℹ
        ],
    )
    def test_known_emoji_replaced_with_ascii(
        self, emoji: str, expected: str
    ) -> None:
        result = _sanitize_emoji(f"<p>{emoji} hello</p>")
        assert expected in result
        assert emoji not in result

    def test_strips_misc_emoji(self) -> None:
        """Unmapped emoji inside the covered blocks are stripped."""
        # U+1F600 GRINNING FACE — Emoticons block
        result = _sanitize_emoji("<p>hi \U0001f600 there</p>")
        assert "\U0001f600" not in result
        assert "hi" in result and "there" in result

    def test_no_op_for_plain_html(self) -> None:
        html = "<h1>Gap Analysis Report</h1><p>Results...</p>"
        assert _sanitize_emoji(html) == html

    def test_combined_emoji_mix(self) -> None:
        html = (
            "<p>\u26a0\ufe0f warning \u2705 ok \u274c fail "
            "\U0001f600 raw</p>"
        )
        result = _sanitize_emoji(html)
        assert "[!]" in result
        assert "[OK]" in result
        assert "[X]" in result
        # Raw grinning face should be stripped (not replaced).
        assert "\U0001f600" not in result

    def test_replacement_tokens_present_in_map(self) -> None:
        """Sanity-check: the replacement map covers every documented emoji."""
        assert set(_EMOJI_REPLACEMENTS.values()) >= {
            "[!]",
            "[OK]",
            "[X]",
            "[TIP]",
            "[INFO]",
        }

    def test_emoji_regex_matches_known_ranges(self) -> None:
        # A codepoint from each of the four stripped blocks.
        for cp in (0x1F600, 0x1F300, 0x1F680, 0x1F900):
            assert _EMOJI_RE.match(chr(cp)) is not None


# ---------------------------------------------------------------------------
# End-to-end publish flow (mocked)
# ---------------------------------------------------------------------------


class TestPublishPageFlow:
    """End-to-end wiring: conversion, dedup, URL construction."""

    def test_existing_page_triggers_update(self, mocker) -> None:
        instance = _make_mock_confluence(
            mocker,
            existing_page={"id": "12345"},
            converted_storage="<p>storage</p>",
        )

        url = publish_page(
            "<h1>Report</h1>",
            email="user@acme.com",
            api_token="token",
            base_url="https://acme.atlassian.net/wiki",
            space_key="ENG",
            title="Gap Analysis",
        )

        instance.update_page.assert_called_once()
        instance.create_page.assert_not_called()
        kwargs = instance.update_page.call_args.kwargs
        assert kwargs["page_id"] == "12345"
        assert kwargs["title"] == "Gap Analysis"
        assert kwargs["representation"] == "storage"
        assert kwargs["body"] == "<p>storage</p>"
        assert url == (
            "https://acme.atlassian.net/wiki/spaces/ENG/pages/12345"
        )

    def test_missing_page_triggers_create(self, mocker) -> None:
        """When no existing page is found, ``create_page`` is called."""
        instance = _make_mock_confluence(
            mocker,
            existing_page=None,
            converted_storage="<p>storage</p>",
            create_result={"id": "77"},
        )

        url = publish_page(
            "<h1>Report</h1>",
            email="user@acme.com",
            api_token="token",
            base_url="https://acme.atlassian.net/wiki",
            space_key="ENG",
            title="New Report",
            parent_page_id="42",
        )

        instance.create_page.assert_called_once()
        instance.update_page.assert_not_called()
        kwargs = instance.create_page.call_args.kwargs
        assert kwargs["space"] == "ENG"
        assert kwargs["title"] == "New Report"
        assert kwargs["parent_id"] == "42"
        assert kwargs["representation"] == "storage"
        assert url == (
            "https://acme.atlassian.net/wiki/spaces/ENG/pages/77"
        )

    def test_get_page_by_title_error_falls_through_to_create(
        self, mocker
    ) -> None:
        """``get_page_by_title`` exceptions are swallowed → create path."""
        instance = _make_mock_confluence(
            mocker,
            get_page_raises=True,
            converted_storage="<p>storage</p>",
            create_result={"id": "3"},
        )

        url = publish_page(
            "<h1>Report</h1>",
            email="user@acme.com",
            api_token="token",
            base_url="https://acme.atlassian.net/wiki",
            space_key="ENG",
            title="Fresh",
        )

        instance.create_page.assert_called_once()
        instance.update_page.assert_not_called()
        assert url.endswith("/spaces/ENG/pages/3")

    def test_trailing_slash_on_base_url_is_normalized(
        self, mocker
    ) -> None:
        _make_mock_confluence(
            mocker,
            existing_page={"id": "10"},
            converted_storage="<p>s</p>",
        )

        url = publish_page(
            "<p>x</p>",
            email="user@acme.com",
            api_token="token",
            base_url="https://acme.atlassian.net/wiki/",
            space_key="ENG",
            title="T",
        )

        # No double slash, no trailing slash on the host portion.
        assert url == (
            "https://acme.atlassian.net/wiki/spaces/ENG/pages/10"
        )
        assert "//spaces" not in url

    def test_emoji_sanitized_before_conversion_call(self, mocker) -> None:
        """The conversion API receives sanitized (emoji-stripped) HTML."""
        instance = _make_mock_confluence(
            mocker,
            existing_page={"id": "1"},
            converted_storage="<p>s</p>",
        )

        publish_page(
            "<p>\u26a0\ufe0f Danger \U0001f600</p>",
            email="user@acme.com",
            api_token="token",
            base_url="https://acme.atlassian.net/wiki",
            space_key="ENG",
            title="T",
        )

        # First positional/keyword arg to session.post is the URL, the
        # ``json`` kwarg carries the payload. The first post call is the
        # conversion API; later calls are from _set_full_width.
        call = instance._session.post.call_args_list[0]
        payload = call.kwargs["json"]
        assert "[!]" in payload["value"]
        assert "\u26a0\ufe0f" not in payload["value"]
        assert "\U0001f600" not in payload["value"]

    def test_conversion_api_failure_falls_back_to_raw_html(
        self, mocker
    ) -> None:
        instance = _make_mock_confluence(
            mocker,
            existing_page={"id": "1"},
            converted_storage=None,
            convert_status=500,
        )

        publish_page(
            "<p>hello</p>",
            email="user@acme.com",
            api_token="token",
            base_url="https://acme.atlassian.net/wiki",
            space_key="ENG",
            title="T",
        )

        # Fallback: update_page receives the raw (sanitized) HTML, not
        # the converted storage value.
        kwargs = instance.update_page.call_args.kwargs
        assert kwargs["body"] == "<p>hello</p>"
