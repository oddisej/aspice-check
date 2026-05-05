"""Unit tests for ConfluenceClient.

Tests cover:
- Successful page retrieval and mapping to PageData
- Successful attachment retrieval and mapping to AttachmentData
- HTTP error mapping: 401 → AuthenticationError, 404 → PageNotFoundError,
  403 → PageNotFoundError
- Connection errors → ConfluenceConnectionError
- Attachment download success and failure
"""

from __future__ import annotations

import pathlib
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError

from confluence_ai.client import ConfluenceClient
from confluence_ai.exceptions import (
    AuthenticationError,
    ConfluenceConnectionError,
    DownloadError,
    PageNotFoundError,
)
from confluence_ai.models import AttachmentData, PageData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_confluence():
    """Patch the Confluence constructor so no real HTTP calls are made."""
    with patch("confluence_ai.client.Confluence") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield instance


@pytest.fixture()
def client(mock_confluence):
    """Return a ConfluenceClient backed by the mocked Confluence instance."""
    return ConfluenceClient(
        base_url="https://acme.atlassian.net/wiki",
        email="user@example.com",
        api_token="test-token",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_http_error(status_code: int) -> HTTPError:
    """Create an HTTPError with a mock response carrying *status_code*."""
    response = MagicMock()
    response.status_code = status_code
    return HTTPError(response=response)


def _make_page_response(
    *,
    title: str = "My Page",
    body: str = "<p>Hello</p>",
    version: int = 3,
    labels: list[dict] | None = None,
    space_key: str = "DEV",
) -> dict:
    """Build a realistic Confluence API page response dict."""
    if labels is None:
        labels = [{"name": "sdp"}, {"name": "process"}]
    return {
        "title": title,
        "body": {"storage": {"value": body}},
        "version": {"number": version},
        "metadata": {"labels": {"results": labels}},
        "space": {"key": space_key},
    }


def _make_attachment_response(
    *,
    title: str = "diagram.png",
    media_type: str = "image/png",
    download_url: str = "/download/attachments/123/diagram.png",
    file_size: int = 4096,
    comment: str = "",
) -> dict:
    """Build a realistic Confluence API attachment response dict."""
    return {
        "title": title,
        "metadata": {"mediaType": media_type, "comment": comment},
        "_links": {"download": download_url},
        "extensions": {"fileSize": file_size},
    }


# ---------------------------------------------------------------------------
# get_page tests
# ---------------------------------------------------------------------------


class TestGetPage:
    """Tests for ConfluenceClient.get_page."""

    def test_returns_page_data(self, client, mock_confluence):
        mock_confluence.get_page_by_id.return_value = _make_page_response(
            title="SDP Overview",
            body="<h1>Overview</h1>",
            version=5,
            labels=[{"name": "sdp"}],
            space_key="ENG",
        )

        result = client.get_page("12345")

        assert isinstance(result, PageData)
        assert result.page_id == "12345"
        assert result.title == "SDP Overview"
        assert result.storage_format == "<h1>Overview</h1>"
        assert result.version == 5
        assert result.labels == ["sdp"]
        assert result.space_key == "ENG"

    def test_expands_correct_fields(self, client, mock_confluence):
        mock_confluence.get_page_by_id.return_value = _make_page_response()

        client.get_page("99")

        mock_confluence.get_page_by_id.assert_called_once_with(
            "99",
            expand="body.storage,metadata.labels,version,space",
        )

    def test_401_raises_authentication_error(self, client, mock_confluence):
        mock_confluence.get_page_by_id.side_effect = _make_http_error(401)

        with pytest.raises(AuthenticationError):
            client.get_page("12345")

    def test_404_raises_page_not_found(self, client, mock_confluence):
        mock_confluence.get_page_by_id.side_effect = _make_http_error(404)

        with pytest.raises(PageNotFoundError) as exc_info:
            client.get_page("12345")

        assert exc_info.value.page_id == "12345"
        assert exc_info.value.status_code == 404

    def test_403_raises_page_not_found(self, client, mock_confluence):
        mock_confluence.get_page_by_id.side_effect = _make_http_error(403)

        with pytest.raises(PageNotFoundError) as exc_info:
            client.get_page("12345")

        assert exc_info.value.status_code == 403

    def test_connection_error_raises_confluence_connection_error(
        self, client, mock_confluence
    ):
        mock_confluence.get_page_by_id.side_effect = RequestsConnectionError()

        with pytest.raises(ConfluenceConnectionError):
            client.get_page("12345")

    def test_unhandled_http_error_propagates(self, client, mock_confluence):
        mock_confluence.get_page_by_id.side_effect = _make_http_error(500)

        with pytest.raises(HTTPError):
            client.get_page("12345")

    def test_empty_labels(self, client, mock_confluence):
        resp = _make_page_response()
        resp["metadata"]["labels"]["results"] = []
        mock_confluence.get_page_by_id.return_value = resp

        result = client.get_page("1")
        assert result.labels == []


# ---------------------------------------------------------------------------
# get_attachments tests
# ---------------------------------------------------------------------------


class TestGetAttachments:
    """Tests for ConfluenceClient.get_attachments."""

    def test_returns_attachment_list(self, client, mock_confluence):
        mock_confluence.get_attachments_from_content.return_value = {
            "results": [
                _make_attachment_response(
                    title="arch.png",
                    media_type="image/png",
                    download_url="/download/attachments/1/arch.png",
                    file_size=8192,
                ),
                _make_attachment_response(
                    title="notes.pdf",
                    media_type="application/pdf",
                    download_url="/download/attachments/1/notes.pdf",
                    file_size=102400,
                ),
            ],
        }

        result = client.get_attachments("1")

        assert len(result) == 2
        assert all(isinstance(a, AttachmentData) for a in result)
        assert result[0].filename == "arch.png"
        assert result[0].media_type == "image/png"
        assert result[0].file_size == 8192
        assert result[1].filename == "notes.pdf"

    def test_empty_results(self, client, mock_confluence):
        mock_confluence.get_attachments_from_content.return_value = {"results": []}

        result = client.get_attachments("1")
        assert result == []

    def test_401_raises_authentication_error(self, client, mock_confluence):
        mock_confluence.get_attachments_from_content.side_effect = _make_http_error(401)

        with pytest.raises(AuthenticationError):
            client.get_attachments("1")

    def test_404_raises_page_not_found(self, client, mock_confluence):
        mock_confluence.get_attachments_from_content.side_effect = _make_http_error(404)

        with pytest.raises(PageNotFoundError):
            client.get_attachments("1")

    def test_connection_error(self, client, mock_confluence):
        mock_confluence.get_attachments_from_content.side_effect = (
            RequestsConnectionError()
        )

        with pytest.raises(ConfluenceConnectionError):
            client.get_attachments("1")


# ---------------------------------------------------------------------------
# download_attachment tests
# ---------------------------------------------------------------------------


class TestDownloadAttachment:
    """Tests for ConfluenceClient.download_attachment."""

    def test_downloads_to_dest_path(self, client, mock_confluence, tmp_path):
        response = MagicMock()
        response.content = b"\x89PNG\r\n\x1a\n"
        mock_confluence.request.return_value = response

        dest = tmp_path / "images" / "diagram.png"
        client.download_attachment("/download/attachments/1/diagram.png", str(dest))

        assert dest.exists()
        assert dest.read_bytes() == b"\x89PNG\r\n\x1a\n"

    def test_creates_parent_directories(self, client, mock_confluence, tmp_path):
        response = MagicMock()
        response.content = b"data"
        mock_confluence.request.return_value = response

        dest = tmp_path / "deep" / "nested" / "file.jpg"
        client.download_attachment("/download/file.jpg", str(dest))

        assert dest.exists()

    def test_http_error_raises_download_error(self, client, mock_confluence, tmp_path):
        mock_confluence.request.side_effect = _make_http_error(404)

        with pytest.raises(DownloadError):
            client.download_attachment(
                "/download/missing.png",
                str(tmp_path / "missing.png"),
            )

    def test_connection_error_raises_download_error(
        self, client, mock_confluence, tmp_path
    ):
        mock_confluence.request.side_effect = RequestsConnectionError()

        with pytest.raises(DownloadError):
            client.download_attachment(
                "/download/file.png",
                str(tmp_path / "file.png"),
            )
