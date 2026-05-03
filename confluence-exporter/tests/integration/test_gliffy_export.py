"""Integration test for Gliffy diagram export.

Mocks a page with a Gliffy macro and matching PNG attachment, then verifies
the Gliffy diagram appears as an image reference in the output with the
diagram name as alt-text.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4**
"""

from __future__ import annotations

import os
import re

from click.testing import CliRunner
from unittest.mock import MagicMock, patch

from confluence_exporter.cli import main


_GLIFFY_XHTML = (
    "<h1>Process Flow</h1>"
    "<p>The following diagram shows the development process:</p>"
    '<ac:structured-macro ac:name="gliffy">'
    '<ac:parameter ac:name="name">Development Process Flow</ac:parameter>'
    '<ac:parameter ac:name="diagramId">98765</ac:parameter>'
    "</ac:structured-macro>"
    "<p>See the diagram above for details.</p>"
)


class TestGliffyExport:
    """Integration test for Gliffy diagram export."""

    def test_gliffy_diagram_exported_with_name_as_alt(self, tmp_path):
        """Gliffy diagram appears as image reference with diagram name as alt-text."""
        output_dir = str(tmp_path / "output")

        with patch("confluence_exporter.cli.ConfluenceClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            mock_client.get_page.return_value = MagicMock(
                title="Process Flow",
                storage_format=_GLIFFY_XHTML,
                space_key="ENG",
                labels=["process"],
            )
            mock_client.get_attachments.return_value = [
                MagicMock(
                    filename="Development Process Flow.png",
                    media_type="image/png",
                    download_url="/download/attachments/111/Development Process Flow.png",
                    file_size=16384,
                    comment="",
                ),
            ]

            # Mock download: write a fake PNG file
            def mock_download(url, dest):
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(b"\x89PNG\r\n\x1a\nfake_gliffy_png")

            mock_client.download_attachment.side_effect = mock_download

            runner = CliRunner()
            result = runner.invoke(main, [
                "https://acme.atlassian.net/wiki/spaces/ENG/pages/111/Process-Flow",
                output_dir,
                "--email", "user@example.com",
                "--api-token", "test-token",
                "--no-ai",
            ])

            assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"

            # Read output
            md_path = os.path.join(output_dir, "Process_Flow.md")
            assert os.path.exists(md_path), f"Markdown file not found at {md_path}"

            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Verify Gliffy diagram appears as image reference
            # The alt-text should be the diagram name
            img_match = re.search(r"!\[([^\]]*)\]\(([^)]+)\)", content)
            assert img_match is not None, (
                f"No image reference found in output. Content:\n{content}"
            )

            alt_text = img_match.group(1)
            img_path = img_match.group(2)

            assert alt_text == "Development Process Flow", (
                f"Expected alt-text 'Development Process Flow', got {alt_text!r}"
            )
            assert img_path.startswith("images/"), (
                f"Image path should start with 'images/', got {img_path!r}"
            )

            # Verify the PNG was downloaded
            images_dir = os.path.join(output_dir, "images")
            assert os.path.isdir(images_dir)
            png_files = [f for f in os.listdir(images_dir) if f.endswith(".png")]
            assert len(png_files) >= 1, "No PNG files found in images/"
