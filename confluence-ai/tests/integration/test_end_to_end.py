"""End-to-end integration test for the Confluence Page Exporter.

Mocks Confluence API responses (page content with XHTML, attachment list)
and AI provider responses, then runs the full pipeline via CLI and verifies
the output Markdown file exists with correct front-matter, headings, image
references, and descriptions. Also verifies the ``images/`` directory
contains downloaded files.

**Validates: Requirements 3.1, 4.3, 5.3, 6.3, 8.1, 8.2, 8.5**
"""

from __future__ import annotations

import os
import re

import yaml
from click.testing import CliRunner
from unittest.mock import MagicMock, patch

from confluence_ai.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_XHTML = (
    "<h1>Software Development Process</h1>"
    "<p>This document describes the SDP.</p>"
    '<ac:image ac:alt="Architecture Diagram">'
    '<ri:attachment ri:filename="architecture.png" />'
    "</ac:image>"
    "<h2>Process Overview</h2>"
    "<p>The process follows <strong>ASPICE</strong> guidelines.</p>"
    "<ul><li>Step 1</li><li>Step 2</li></ul>"
    "<hr />"
    "<table>"
    "<tr><th>Phase</th><th>Output</th></tr>"
    "<tr><td>Design</td><td>SDD</td></tr>"
    "</table>"
)


def _make_page_response() -> dict:
    return {
        "title": "Software Development Process",
        "body": {"storage": {"value": _SAMPLE_XHTML}},
        "version": {"number": 3},
        "metadata": {"labels": {"results": [{"name": "sdp"}, {"name": "process"}]}},
        "space": {"key": "ENG"},
    }


def _make_attachment_response() -> dict:
    return {
        "results": [
            {
                "title": "architecture.png",
                "metadata": {"mediaType": "image/png", "comment": ""},
                "_links": {"download": "/download/attachments/12345/architecture.png"},
                "extensions": {"fileSize": 8192},
            },
        ],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """End-to-end integration test with mocked Confluence and AI."""

    def test_full_export_pipeline(self, tmp_path):
        """Run full pipeline and verify output structure and content."""
        output_dir = str(tmp_path / "output")

        with patch("confluence_ai.cli.ConfluenceClient") as MockClient, \
             patch("confluence_ai.cli.create_describer") as mock_create:

            # Set up mock client
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            mock_client.get_page.return_value = MagicMock(
                title="Software Development Process",
                storage_format=_SAMPLE_XHTML,
                space_key="ENG",
                labels=["sdp", "process"],
            )
            mock_client.get_attachments.return_value = [
                MagicMock(
                    filename="architecture.png",
                    media_type="image/png",
                    download_url="/download/attachments/12345/architecture.png",
                    file_size=8192,
                    comment="",
                ),
            ]

            # Mock download: write a fake PNG file
            def mock_download(url, dest):
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(b"\x89PNG\r\n\x1a\nfake_image_data")

            mock_client.download_attachment.side_effect = mock_download

            # Set up mock AI describer
            mock_describer = MagicMock()
            mock_describer.describe_batch.return_value = {
                "images/architecture.png": "A high-level architecture diagram showing system components."
            }
            mock_create.return_value = mock_describer

            # Run CLI
            runner = CliRunner()
            result = runner.invoke(main, [
                "https://acme.atlassian.net/wiki/spaces/ENG/pages/12345/SDP",
                output_dir,
                "--email", "user@example.com",
                "--api-token", "test-token",
                "--ai-provider", "anthropic",
                "--ai-api-key", "test-key",
            ])

            assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"

            # Verify output file exists
            md_path = os.path.join(output_dir, "Software_Development_Process.md")
            assert os.path.exists(md_path), f"Markdown file not found at {md_path}"

            # Read and verify content
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Verify YAML front-matter
            assert content.startswith("---\n"), "Missing YAML front-matter"
            fm_end = content.index("---", 4)
            fm_yaml = yaml.safe_load(content[4:fm_end])
            assert fm_yaml["page_title"] == "Software Development Process"
            assert fm_yaml["page_id"] == "12345"
            assert "source_url" in fm_yaml
            assert "export_timestamp" in fm_yaml
            assert "exporter_version" in fm_yaml

            # Verify headings
            assert "# Software Development Process" in content
            assert "## Process Overview" in content

            # Verify image reference
            assert re.search(r"!\[.*\]\(images/architecture\.png\)", content), (
                "Image reference not found in output"
            )

            # Verify images directory
            images_dir = os.path.join(output_dir, "images")
            assert os.path.isdir(images_dir), "images/ directory not created"
            assert os.path.exists(os.path.join(images_dir, "architecture.png")), (
                "architecture.png not found in images/"
            )

            # Verify summary output
            assert "Export complete" in result.output
            assert "Images downloaded: 1" in result.output

    def test_export_with_no_ai(self, tmp_path):
        """Run pipeline with --no-ai and verify no AI calls are made."""
        output_dir = str(tmp_path / "output")

        with patch("confluence_ai.cli.ConfluenceClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            mock_client.get_page.return_value = MagicMock(
                title="Test Page",
                storage_format="<h1>Test</h1><p>Content</p>",
                space_key="DEV",
                labels=[],
            )
            mock_client.get_attachments.return_value = []

            runner = CliRunner()
            result = runner.invoke(main, [
                "https://acme.atlassian.net/wiki/spaces/DEV/pages/99/Test",
                output_dir,
                "--email", "user@example.com",
                "--api-token", "test-token",
                "--no-ai",
            ])

            assert result.exit_code == 0, f"CLI failed: {result.output}"

            md_path = os.path.join(output_dir, "Test_Page.md")
            assert os.path.exists(md_path)
