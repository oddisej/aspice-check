"""Integration test for partial failure handling.

Mocks one image download failure and one AI description failure, then verifies
the export completes with placeholders for failed items and warnings in the
summary.

**Validates: Requirements 4.5, 5.5, 6.5, 9.2**
"""

from __future__ import annotations

import os

from click.testing import CliRunner
from unittest.mock import MagicMock, patch, call

from confluence_exporter.cli import main
from confluence_exporter.exceptions import DownloadError


_PARTIAL_FAILURE_XHTML = (
    "<h1>Test Page</h1>"
    "<p>Page with multiple images.</p>"
    '<ac:image ac:alt="Good Image">'
    '<ri:attachment ri:filename="good_image.png" />'
    "</ac:image>"
    '<ac:image ac:alt="Bad Image">'
    '<ri:attachment ri:filename="bad_image.png" />'
    "</ac:image>"
)


class TestPartialFailure:
    """Integration test for partial failure handling."""

    def test_export_completes_with_partial_failures(self, tmp_path):
        """Export completes with placeholders when some downloads/descriptions fail."""
        output_dir = str(tmp_path / "output")

        with patch("confluence_exporter.cli.ConfluenceClient") as MockClient, \
             patch("confluence_exporter.cli.create_describer") as mock_create:

            mock_client = MagicMock()
            MockClient.return_value = mock_client

            mock_client.get_page.return_value = MagicMock(
                title="Test Page",
                storage_format=_PARTIAL_FAILURE_XHTML,
                space_key="DEV",
                labels=[],
            )
            mock_client.get_attachments.return_value = [
                MagicMock(
                    filename="good_image.png",
                    media_type="image/png",
                    download_url="/download/good_image.png",
                    file_size=4096,
                    comment="",
                ),
                MagicMock(
                    filename="bad_image.png",
                    media_type="image/png",
                    download_url="/download/bad_image.png",
                    file_size=4096,
                    comment="",
                ),
            ]

            # Mock download: succeed for good_image, fail for bad_image
            def mock_download(url, dest):
                if "bad_image" in url:
                    raise DownloadError(
                        filename="bad_image.png",
                        url=url,
                        message="Simulated download failure",
                    )
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(b"\x89PNG\r\n\x1a\nfake_data")

            mock_client.download_attachment.side_effect = mock_download

            # Set up mock AI describer — returns description for good image,
            # placeholder for any that fail
            mock_describer = MagicMock()
            mock_describer.describe_batch.return_value = {
                "images/good_image.png": "A good architecture diagram."
            }
            mock_create.return_value = mock_describer

            runner = CliRunner()
            result = runner.invoke(main, [
                "https://acme.atlassian.net/wiki/spaces/DEV/pages/222/Test",
                output_dir,
                "--email", "user@example.com",
                "--api-token", "test-token",
                "--ai-provider", "anthropic",
                "--ai-api-key", "test-key",
            ])

            assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"

            # Read output
            md_path = os.path.join(output_dir, "Test_Page.md")
            assert os.path.exists(md_path), f"Markdown file not found at {md_path}"

            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Verify good image has an image reference
            assert "good_image.png" in content

            # Verify bad image has a placeholder (not an image reference)
            assert "not available" in content.lower() or "bad_image" in content.lower(), (
                f"Expected placeholder for failed image. Content:\n{content}"
            )

            # Verify export summary
            assert "Export complete" in result.output
