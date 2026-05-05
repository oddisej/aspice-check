"""SDP document ingester for the ASPICE evaluation tool.

Reads Markdown SDP documents, validates the file format, extracts
structural metadata (section headers), and returns an SDPDocument
ready for evaluation.
"""

from __future__ import annotations

import pathlib
import re

from aspice_eval.exceptions import UnsupportedFormatError
from aspice_eval.models import SDPDocument

# Markdown header pattern: lines starting with one or more '#' characters
_HEADER_RE = re.compile(r"^(#{1,6})[ \t]+(\S.*)$", re.MULTILINE)


class SDPIngester:
    """Reads and prepares SDP documents for evaluation."""

    def ingest(self, sdp_path: str) -> SDPDocument:
        """Read an SDP document from a Markdown file.

        Args:
            sdp_path: Path to the SDP Markdown file.

        Returns:
            SDPDocument containing the raw content and structural metadata.

        Raises:
            UnsupportedFormatError: If the file is not Markdown.
            FileNotFoundError: If the file does not exist.
        """
        path = pathlib.Path(sdp_path)

        # Check file existence first
        if not path.exists():
            raise FileNotFoundError(
                f"SDP document not found: {sdp_path}"
            )

        # Validate file extension
        ext = path.suffix.lower()
        supported = [".md"]
        if ext not in supported:
            supported_str = ", ".join(supported)
            raise UnsupportedFormatError(
                f"Unsupported file format '{ext}'. "
                f"Supported formats: {supported_str}. "
                f"Convert the document to Markdown (.md) before evaluation.",
                file_path=str(path),
                actual_extension=ext,
                supported_formats=supported,
            )

        # Read file content
        content = path.read_text(encoding="utf-8")

        # Extract section headers from Markdown
        section_headers = [match.group(2).strip() for match in _HEADER_RE.finditer(content)]

        return SDPDocument(
            content=content,
            file_path=str(path),
            section_headers=section_headers,
            metadata={
                "file_name": path.name,
                "file_size": path.stat().st_size,
            },
        )
