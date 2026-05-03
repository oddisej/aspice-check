"""Asset downloader for images and Gliffy diagram PNG previews.

Downloads inline images (attachments and external URLs) and Gliffy diagram
PNG previews to a local ``images/`` directory, updating content nodes with
the resulting local paths.
"""

from __future__ import annotations

import logging
import os
import pathlib
import re

import requests

from confluence_exporter.client import ConfluenceClient
from confluence_exporter.exceptions import DownloadError
from confluence_exporter.models import (
    AttachmentData,
    ContentNode,
    GliffyNode,
    ImageNode,
)

logger = logging.getLogger(__name__)


class AssetDownloader:
    """Downloads images and Gliffy diagram PNGs to a local directory."""

    def __init__(self, client: ConfluenceClient, output_dir: str) -> None:
        """Initialize with a Confluence client and output directory.

        Args:
            client: Authenticated ConfluenceClient for downloading attachments.
            output_dir: Root output directory (images go to ``output_dir/images/``).
        """
        self._client = client
        self._output_dir = output_dir
        self._images_dir = os.path.join(output_dir, "images")
        os.makedirs(self._images_dir, exist_ok=True)
        # Track used filenames within this downloader instance to resolve collisions
        self._used_filenames: set[str] = set()

    def download_assets(
        self,
        nodes: list[ContentNode],
        attachments: list[AttachmentData],
    ) -> list[ContentNode]:
        """Download all referenced images and return nodes with local paths.

        Creates a shallow copy of the node list. For each ``ImageNode`` and
        ``GliffyNode``, downloads the asset and sets ``local_path`` on the
        **copy**.  The original nodes are not modified.

        On download failure the node's ``local_path`` remains ``None`` and a
        warning is logged.

        Args:
            nodes: Content nodes from the parser.
            attachments: Attachment list from the Confluence client.

        Returns:
            New list of content nodes with ``local_path`` populated for
            successfully downloaded assets.
        """
        result: list[ContentNode] = []
        for node in nodes:
            if isinstance(node, ImageNode):
                result.append(self._download_image(node, attachments))
            elif isinstance(node, GliffyNode):
                result.append(self._download_gliffy(node, attachments))
            else:
                result.append(node)
        return result

    # ------------------------------------------------------------------
    # Image download
    # ------------------------------------------------------------------

    def _download_image(
        self,
        node: ImageNode,
        attachments: list[AttachmentData],
    ) -> ImageNode:
        """Download an image and return a new node with ``local_path`` set."""
        # Create a copy so we don't mutate the original
        new_node = ImageNode(
            source_type=node.source_type,
            filename=node.filename,
            url=node.url,
            alt_text=node.alt_text,
            local_path=None,
        )

        try:
            if node.source_type == "attachment":
                self._download_attachment_image(new_node, attachments)
            elif node.source_type == "external":
                self._download_external_image(new_node)
            else:
                logger.warning(
                    "Unknown image source type %r for %s",
                    node.source_type,
                    node.filename or node.url,
                )
        except Exception:
            logger.warning(
                "Failed to download image %s",
                node.filename or node.url,
                exc_info=True,
            )
            new_node.local_path = None

        return new_node

    def _download_attachment_image(
        self,
        node: ImageNode,
        attachments: list[AttachmentData],
    ) -> None:
        """Download an attachment-based image."""
        if not node.filename:
            logger.warning("ImageNode has source_type='attachment' but no filename")
            return

        attachment = self._find_attachment_by_filename(node.filename, attachments)
        if attachment is None:
            logger.warning(
                "No attachment found for image filename %r", node.filename
            )
            return

        safe_name = self._sanitize_filename(node.filename)
        dest_path = os.path.join(self._images_dir, safe_name)

        self._client.download_attachment(attachment.download_url, dest_path)
        node.local_path = os.path.join("images", safe_name)
        logger.info("Downloaded attachment image to %s", dest_path)

    def _download_external_image(self, node: ImageNode) -> None:
        """Download an external-URL image."""
        if not node.url:
            logger.warning("ImageNode has source_type='external' but no URL")
            return

        # Derive filename from URL or use a fallback
        url_path = node.url.rsplit("/", 1)[-1].rsplit("?", 1)[0]
        filename = url_path if url_path else "external_image.png"
        safe_name = self._sanitize_filename(filename)
        dest_path = os.path.join(self._images_dir, safe_name)

        try:
            response = requests.get(node.url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DownloadError(
                filename=filename,
                url=node.url,
                message=f"Failed to download external image from {node.url}: {exc}",
            ) from exc

        pathlib.Path(dest_path).write_bytes(response.content)
        node.local_path = os.path.join("images", safe_name)
        logger.info("Downloaded external image to %s", dest_path)

    # ------------------------------------------------------------------
    # Gliffy download
    # ------------------------------------------------------------------

    def _download_gliffy(
        self,
        node: GliffyNode,
        attachments: list[AttachmentData],
    ) -> GliffyNode:
        """Download a Gliffy PNG preview and return a new node with ``local_path``."""
        new_node = GliffyNode(
            name=node.name,
            diagram_id=node.diagram_id,
            local_path=None,
            alt_text=node.alt_text,
        )

        try:
            attachment = self._resolve_gliffy_attachment(node, attachments)
            if attachment is None:
                logger.warning(
                    "No PNG preview attachment found for Gliffy diagram %r",
                    node.name,
                )
                return new_node

            safe_name = self._sanitize_filename(
                f"{node.name}.png" if not node.name.lower().endswith(".png") else node.name
            )
            dest_path = os.path.join(self._images_dir, safe_name)

            self._client.download_attachment(attachment.download_url, dest_path)
            new_node.local_path = os.path.join("images", safe_name)
            logger.info("Downloaded Gliffy PNG to %s", dest_path)
        except Exception:
            logger.warning(
                "Failed to download Gliffy diagram %r",
                node.name,
                exc_info=True,
            )
            new_node.local_path = None

        return new_node

    # ------------------------------------------------------------------
    # Gliffy attachment resolution
    # ------------------------------------------------------------------

    def _resolve_gliffy_attachment(
        self,
        node: GliffyNode,
        attachments: list[AttachmentData],
    ) -> AttachmentData | None:
        """Find the PNG preview attachment for a Gliffy diagram.

        Searches attachments by:
        1. Exact match on ``{diagram_name}.png``
        2. Partial match — filename contains the diagram name and ends
           with ``.png``
        3. Match on media type ``image/png`` with ``gliffy`` in the filename

        Returns:
            The matching ``AttachmentData``, or ``None`` if no preview found.
        """
        name = node.name

        # 1. Exact match: "{name}.png"
        exact_target = f"{name}.png"
        for att in attachments:
            if att.filename == exact_target:
                return att

        # 2. Partial match: filename contains name and ends with .png
        name_lower = name.lower()
        for att in attachments:
            fname_lower = att.filename.lower()
            if name_lower in fname_lower and fname_lower.endswith(".png"):
                return att

        # 3. Media type match: image/png with "gliffy" in filename
        for att in attachments:
            if (
                att.media_type == "image/png"
                and "gliffy" in att.filename.lower()
            ):
                return att

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_attachment_by_filename(
        filename: str,
        attachments: list[AttachmentData],
    ) -> AttachmentData | None:
        """Find an attachment by exact filename match."""
        for att in attachments:
            if att.filename == filename:
                return att
        return None

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a filename for safe filesystem use.

        - Replaces spaces with underscores
        - Removes special characters (keeps alphanumeric, underscores,
          hyphens, and dots)
        - Preserves the file extension
        - Appends a numeric suffix if a file with the same name already
          exists (collision resolution)

        Args:
            name: Original filename.

        Returns:
            Sanitized, unique filename.
        """
        # Split into stem and extension
        dot_idx = name.rfind(".")
        if dot_idx > 0:
            stem = name[:dot_idx]
            ext = name[dot_idx:]  # includes the dot
        else:
            stem = name
            ext = ""

        # Replace spaces with underscores
        stem = stem.replace(" ", "_")

        # Remove special characters — keep alphanumeric, underscores, hyphens
        stem = re.sub(r"[^a-zA-Z0-9_\-]", "", stem)

        # Sanitize extension similarly (keep the dot)
        if ext:
            ext_body = ext[1:]  # strip leading dot
            ext_body = re.sub(r"[^a-zA-Z0-9]", "", ext_body)
            ext = f".{ext_body}" if ext_body else ""

        # Fallback for empty stem
        if not stem:
            stem = "file"

        # Resolve collisions
        candidate = f"{stem}{ext}"
        if candidate not in self._used_filenames:
            self._used_filenames.add(candidate)
            return candidate

        counter = 1
        while True:
            candidate = f"{stem}_{counter}{ext}"
            if candidate not in self._used_filenames:
                self._used_filenames.add(candidate)
                return candidate
            counter += 1
