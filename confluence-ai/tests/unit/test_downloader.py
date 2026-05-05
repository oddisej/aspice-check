"""Unit tests for the AssetDownloader class.

Tests cover image downloading (attachment and external), Gliffy PNG
resolution and download, filename sanitization, and graceful failure
handling.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from confluence_ai.downloader import AssetDownloader
from confluence_ai.exceptions import DownloadError
from confluence_ai.models import (
    AttachmentData,
    ContentNode,
    GliffyNode,
    HeadingNode,
    ImageNode,
    ParagraphNode,
)


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock ConfluenceClient."""
    return MagicMock()


@pytest.fixture
def downloader(mock_client: MagicMock, tmp_path: str) -> AssetDownloader:
    """Return an AssetDownloader with a mock client and temp output dir."""
    return AssetDownloader(mock_client, str(tmp_path))


@pytest.fixture
def sample_attachments() -> list[AttachmentData]:
    """Return a sample list of attachments."""
    return [
        AttachmentData(
            filename="screenshot.png",
            media_type="image/png",
            download_url="/download/attachments/123/screenshot.png",
            file_size=1024,
        ),
        AttachmentData(
            filename="diagram.png",
            media_type="image/png",
            download_url="/download/attachments/123/diagram.png",
            file_size=2048,
        ),
        AttachmentData(
            filename="My Gliffy Diagram.png",
            media_type="image/png",
            download_url="/download/attachments/123/My Gliffy Diagram.png",
            file_size=4096,
        ),
        AttachmentData(
            filename="gliffy-42-process-flow.png",
            media_type="image/png",
            download_url="/download/attachments/123/gliffy-42-process-flow.png",
            file_size=3072,
        ),
    ]


class TestAssetDownloaderInit:
    """Tests for AssetDownloader initialization."""

    def test_creates_images_directory(self, mock_client: MagicMock, tmp_path: str) -> None:
        """The images/ subdirectory is created on init."""
        downloader = AssetDownloader(mock_client, str(tmp_path))
        assert os.path.isdir(os.path.join(str(tmp_path), "images"))

    def test_images_dir_already_exists(self, mock_client: MagicMock, tmp_path: str) -> None:
        """No error if images/ already exists."""
        os.makedirs(os.path.join(str(tmp_path), "images"))
        downloader = AssetDownloader(mock_client, str(tmp_path))
        assert os.path.isdir(os.path.join(str(tmp_path), "images"))


class TestDownloadAssets:
    """Tests for the download_assets method."""

    def test_returns_new_list(
        self,
        downloader: AssetDownloader,
        sample_attachments: list[AttachmentData],
    ) -> None:
        """download_assets returns a new list, not the original."""
        nodes: list[ContentNode] = [HeadingNode(level=1, text="Title")]
        result = downloader.download_assets(nodes, sample_attachments)
        assert result is not nodes

    def test_non_image_nodes_passed_through(
        self,
        downloader: AssetDownloader,
        sample_attachments: list[AttachmentData],
    ) -> None:
        """Non-image/gliffy nodes are passed through unchanged."""
        heading = HeadingNode(level=1, text="Title")
        paragraph = ParagraphNode(children=[])
        nodes: list[ContentNode] = [heading, paragraph]
        result = downloader.download_assets(nodes, sample_attachments)
        assert result[0] is heading
        assert result[1] is paragraph

    def test_original_image_node_not_modified(
        self,
        downloader: AssetDownloader,
        mock_client: MagicMock,
        sample_attachments: list[AttachmentData],
    ) -> None:
        """The original ImageNode is not modified."""
        original = ImageNode(
            source_type="attachment",
            filename="screenshot.png",
        )
        result = downloader.download_assets([original], sample_attachments)
        assert original.local_path is None
        assert result[0] is not original

    def test_download_attachment_image(
        self,
        downloader: AssetDownloader,
        mock_client: MagicMock,
        sample_attachments: list[AttachmentData],
    ) -> None:
        """Attachment images are downloaded and local_path is set."""
        node = ImageNode(source_type="attachment", filename="screenshot.png")
        result = downloader.download_assets([node], sample_attachments)
        downloaded = result[0]
        assert isinstance(downloaded, ImageNode)
        assert downloaded.local_path == "images/screenshot.png"
        mock_client.download_attachment.assert_called_once()

    @patch("confluence_ai.downloader.requests.get")
    def test_download_external_image(
        self,
        mock_get: MagicMock,
        downloader: AssetDownloader,
        sample_attachments: list[AttachmentData],
    ) -> None:
        """External images are downloaded via requests.get."""
        mock_response = MagicMock()
        mock_response.content = b"fake image data"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        node = ImageNode(
            source_type="external",
            url="https://example.com/photo.jpg",
        )
        result = downloader.download_assets([node], sample_attachments)
        downloaded = result[0]
        assert isinstance(downloaded, ImageNode)
        assert downloaded.local_path == "images/photo.jpg"
        mock_get.assert_called_once_with("https://example.com/photo.jpg", timeout=30)

    def test_download_gliffy_exact_match(
        self,
        downloader: AssetDownloader,
        mock_client: MagicMock,
        sample_attachments: list[AttachmentData],
    ) -> None:
        """Gliffy diagram with exact name match downloads correctly."""
        node = GliffyNode(name="diagram", diagram_id="1")
        result = downloader.download_assets([node], sample_attachments)
        downloaded = result[0]
        assert isinstance(downloaded, GliffyNode)
        assert downloaded.local_path == "images/diagram.png"
        mock_client.download_attachment.assert_called_once()

    def test_download_failure_logs_warning_and_continues(
        self,
        downloader: AssetDownloader,
        mock_client: MagicMock,
        sample_attachments: list[AttachmentData],
    ) -> None:
        """On download failure, local_path is None and processing continues."""
        mock_client.download_attachment.side_effect = DownloadError(
            filename="screenshot.png",
            url="/download/attachments/123/screenshot.png",
        )
        nodes: list[ContentNode] = [
            ImageNode(source_type="attachment", filename="screenshot.png"),
            HeadingNode(level=1, text="After image"),
        ]
        result = downloader.download_assets(nodes, sample_attachments)
        assert isinstance(result[0], ImageNode)
        assert result[0].local_path is None
        assert isinstance(result[1], HeadingNode)

    def test_missing_attachment_sets_none(
        self,
        downloader: AssetDownloader,
        mock_client: MagicMock,
    ) -> None:
        """If no matching attachment is found, local_path stays None."""
        node = ImageNode(source_type="attachment", filename="nonexistent.png")
        result = downloader.download_assets([node], [])
        assert isinstance(result[0], ImageNode)
        assert result[0].local_path is None

    @patch("confluence_ai.downloader.requests.get")
    def test_external_download_failure(
        self,
        mock_get: MagicMock,
        downloader: AssetDownloader,
    ) -> None:
        """External image download failure sets local_path to None."""
        import requests as req

        mock_get.side_effect = req.RequestException("Connection refused")
        node = ImageNode(
            source_type="external",
            url="https://example.com/broken.png",
        )
        result = downloader.download_assets([node], [])
        assert isinstance(result[0], ImageNode)
        assert result[0].local_path is None


class TestResolveGliffyAttachment:
    """Tests for _resolve_gliffy_attachment."""

    def test_exact_match(
        self,
        downloader: AssetDownloader,
        sample_attachments: list[AttachmentData],
    ) -> None:
        """Exact match on '{name}.png'."""
        node = GliffyNode(name="screenshot")
        result = downloader._resolve_gliffy_attachment(node, sample_attachments)
        assert result is not None
        assert result.filename == "screenshot.png"

    def test_partial_match(
        self,
        downloader: AssetDownloader,
        sample_attachments: list[AttachmentData],
    ) -> None:
        """Partial match — filename contains name and ends with .png."""
        node = GliffyNode(name="My Gliffy Diagram")
        result = downloader._resolve_gliffy_attachment(node, sample_attachments)
        assert result is not None
        assert result.filename == "My Gliffy Diagram.png"

    def test_gliffy_keyword_match(
        self,
        downloader: AssetDownloader,
        sample_attachments: list[AttachmentData],
    ) -> None:
        """Fallback: media type image/png with 'gliffy' in filename."""
        node = GliffyNode(name="unknown-diagram")
        # Remove exact and partial matches, keep only the gliffy-named one
        attachments = [
            AttachmentData(
                filename="gliffy-99-something.png",
                media_type="image/png",
                download_url="/download/gliffy-99-something.png",
            ),
        ]
        result = downloader._resolve_gliffy_attachment(node, attachments)
        assert result is not None
        assert result.filename == "gliffy-99-something.png"

    def test_no_match_returns_none(
        self,
        downloader: AssetDownloader,
    ) -> None:
        """Returns None when no matching attachment exists."""
        node = GliffyNode(name="nonexistent")
        attachments = [
            AttachmentData(
                filename="unrelated.pdf",
                media_type="application/pdf",
                download_url="/download/unrelated.pdf",
            ),
        ]
        result = downloader._resolve_gliffy_attachment(node, attachments)
        assert result is None


class TestSanitizeFilename:
    """Tests for _sanitize_filename."""

    def test_spaces_to_underscores(self, downloader: AssetDownloader) -> None:
        """Spaces are replaced with underscores."""
        assert downloader._sanitize_filename("my file.png") == "my_file.png"

    def test_special_chars_removed(self, downloader: AssetDownloader) -> None:
        """Special characters are removed."""
        result = downloader._sanitize_filename("file@#$%.png")
        assert result == "file.png"

    def test_extension_preserved(self, downloader: AssetDownloader) -> None:
        """File extension is preserved."""
        result = downloader._sanitize_filename("image.jpeg")
        assert result.endswith(".jpeg")

    def test_collision_resolution(self, downloader: AssetDownloader) -> None:
        """Duplicate filenames get numeric suffixes."""
        name1 = downloader._sanitize_filename("test.png")
        name2 = downloader._sanitize_filename("test.png")
        assert name1 == "test.png"
        assert name2 == "test_1.png"

    def test_empty_stem_fallback(self, downloader: AssetDownloader) -> None:
        """Empty stem after sanitization falls back to 'file'."""
        result = downloader._sanitize_filename("@#$.png")
        assert result == "file.png"

    def test_no_extension(self, downloader: AssetDownloader) -> None:
        """Filenames without extensions are handled."""
        result = downloader._sanitize_filename("readme")
        assert result == "readme"

    def test_multiple_collisions(self, downloader: AssetDownloader) -> None:
        """Multiple collisions produce incrementing suffixes."""
        r1 = downloader._sanitize_filename("img.png")
        r2 = downloader._sanitize_filename("img.png")
        r3 = downloader._sanitize_filename("img.png")
        assert r1 == "img.png"
        assert r2 == "img_1.png"
        assert r3 == "img_2.png"

    def test_preserves_hyphens_and_underscores(self, downloader: AssetDownloader) -> None:
        """Hyphens and underscores in the stem are preserved."""
        result = downloader._sanitize_filename("my-file_name.png")
        assert result == "my-file_name.png"
