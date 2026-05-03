"""Confluence Cloud client for page and attachment retrieval.

Wraps ``atlassian-python-api`` to provide a focused interface for the
exporter's needs.  Maps HTTP errors to the project's custom exception
hierarchy so callers never need to handle raw HTTP details.
"""

from __future__ import annotations

import logging
import pathlib

from atlassian import Confluence
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError

from confluence_exporter.exceptions import (
    AuthenticationError,
    ConfluenceConnectionError,
    DownloadError,
    PageNotFoundError,
)
from confluence_exporter.models import AttachmentData, PageData

logger = logging.getLogger(__name__)


class ConfluenceClient:
    """Authenticated client for Confluence Cloud page and attachment retrieval."""

    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        """Initialize and authenticate with Confluence Cloud.

        Args:
            base_url: Confluence Cloud base URL
                (e.g., ``https://acme.atlassian.net/wiki``).
            email: User email for Basic Auth.
            api_token: Confluence Cloud API token.
        """
        self._base_url = base_url
        try:
            self._confluence = Confluence(
                url=base_url,
                username=email,
                password=api_token,
                cloud=True,
            )
        except RequestsConnectionError as exc:
            raise ConfluenceConnectionError(base_url) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_page(self, page_id: str) -> PageData:
        """Retrieve page content in storage format with metadata.

        Args:
            page_id: Confluence page ID.

        Returns:
            PageData containing title, storage format body, version,
            and labels.

        Raises:
            PageNotFoundError: If the page doesn't exist or user lacks
                access.
            AuthenticationError: If credentials are invalid.
            ConfluenceConnectionError: If the server is unreachable.
        """
        try:
            page = self._confluence.get_page_by_id(
                page_id,
                expand="body.storage,metadata.labels,version,space",
            )
        except HTTPError as exc:
            self._handle_http_error(exc, page_id=page_id)
            raise  # pragma: no cover — _handle_http_error always raises
        except RequestsConnectionError as exc:
            raise ConfluenceConnectionError(self._base_url) from exc

        return self._map_page(page, page_id)

    def get_attachments(self, page_id: str) -> list[AttachmentData]:
        """Retrieve all attachments for a page.

        Args:
            page_id: Confluence page ID.

        Returns:
            List of AttachmentData with filename, media type, download
            URL, and size.

        Raises:
            PageNotFoundError: If the page doesn't exist or user lacks
                access.
            AuthenticationError: If credentials are invalid.
            ConfluenceConnectionError: If the server is unreachable.
        """
        try:
            response = self._confluence.get_attachments_from_content(
                page_id,
                limit=250,
            )
        except HTTPError as exc:
            self._handle_http_error(exc, page_id=page_id)
            raise  # pragma: no cover
        except RequestsConnectionError as exc:
            raise ConfluenceConnectionError(self._base_url) from exc

        results: list[dict] = response.get("results", []) if isinstance(response, dict) else []
        return [self._map_attachment(att) for att in results]

    def download_attachment(self, download_url: str, dest_path: str) -> None:
        """Download an attachment to a local file path.

        Args:
            download_url: Relative or absolute URL for the attachment.
            dest_path: Local filesystem path to write the file.

        Raises:
            DownloadError: If the download fails.
        """
        filename = pathlib.PurePosixPath(download_url).name
        try:
            response = self._confluence.request(
                method="GET",
                path=download_url,
            )
            # The request method may return a Response object directly
            # when the Confluence instance is not in advanced_mode.
            if hasattr(response, "content"):
                content = response.content
            else:
                content = response  # type: ignore[assignment]

            dest = pathlib.Path(dest_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)  # type: ignore[arg-type]
            logger.info("Downloaded attachment to %s", dest_path)
        except HTTPError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            raise DownloadError(
                filename=filename,
                url=download_url,
                status_code=status,
            ) from exc
        except RequestsConnectionError as exc:
            raise DownloadError(
                filename=filename,
                url=download_url,
                message=f"Connection error downloading {filename!r} from {download_url}.",
            ) from exc
        except OSError as exc:
            raise DownloadError(
                filename=filename,
                url=download_url,
                message=f"Failed to write {dest_path!r}: {exc}",
            ) from exc

    def get_user_display_name(self, account_id: str) -> str | None:
        """Resolve a Confluence Cloud account ID to a display name.

        Uses the Atlassian Cloud user API directly via requests.

        Args:
            account_id: The Confluence Cloud account ID (e.g.
                ``"622a0356302c6b006af6617b"``).

        Returns:
            The user's display name, or ``None`` if the lookup fails.
        """
        try:
            # Use the underlying session from atlassian-python-api
            # to make a direct REST call with proper auth
            url = f"{self._base_url}/rest/api/user?accountId={account_id}"
            session = self._confluence._session
            response = session.get(url)
            if response.status_code == 200:
                data = response.json()
                return data.get("displayName") or data.get("publicName") or None
            logger.debug(
                "User lookup returned status %d for %s",
                response.status_code,
                account_id,
            )
            return None
        except Exception as exc:
            logger.debug(
                "Failed to resolve user account ID %s: %s", account_id, exc
            )
            return None

    def resolve_user_ids(self, account_ids: set[str]) -> dict[str, str]:
        """Resolve multiple account IDs to display names.

        Args:
            account_ids: Set of Confluence Cloud account IDs.

        Returns:
            Dict mapping account_id → display_name for successfully
            resolved users. Failed lookups are omitted.
        """
        resolved: dict[str, str] = {}
        for aid in account_ids:
            name = self.get_user_display_name(aid)
            if name:
                resolved[aid] = name
                logger.debug("Resolved user %s → %s", aid, name)
        return resolved

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_http_error(
        exc: HTTPError,
        *,
        page_id: str | None = None,
    ) -> None:
        """Translate an ``HTTPError`` into the appropriate custom exception.

        Mapping:
            401 → AuthenticationError
            403 → PageNotFoundError (access denied)
            404 → PageNotFoundError
        """
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None) if response is not None else None

        if status == 401:
            raise AuthenticationError(
                base_url="",
                status_code=status,
            ) from exc

        if status in (403, 404):
            raise PageNotFoundError(
                page_id=page_id or "",
                status_code=status,
            ) from exc

        # Re-raise unhandled HTTP errors as-is
        raise exc

    @staticmethod
    def _map_page(raw: dict, page_id: str) -> PageData:
        """Map a raw Confluence API page response to ``PageData``."""
        title: str = raw.get("title", "")
        storage_format: str = (
            raw.get("body", {}).get("storage", {}).get("value", "")
        )
        version: int = raw.get("version", {}).get("number", 0)

        labels_container = raw.get("metadata", {}).get("labels", {})
        label_results: list[dict] = labels_container.get("results", []) if isinstance(labels_container, dict) else []
        labels: list[str] = [lbl.get("name", "") for lbl in label_results]

        space_key: str = raw.get("space", {}).get("key", "")

        return PageData(
            page_id=page_id,
            title=title,
            storage_format=storage_format,
            version=version,
            labels=labels,
            space_key=space_key,
        )

    @staticmethod
    def _map_attachment(raw: dict) -> AttachmentData:
        """Map a raw Confluence API attachment response to ``AttachmentData``."""
        title: str = raw.get("title", "")
        media_type: str = raw.get("metadata", {}).get("mediaType", "")
        download_url: str = raw.get("_links", {}).get("download", "")
        file_size: int = raw.get("extensions", {}).get("fileSize", 0)
        comment: str = raw.get("metadata", {}).get("comment", "")

        return AttachmentData(
            filename=title,
            media_type=media_type,
            download_url=download_url,
            file_size=int(file_size) if file_size else 0,
            comment=comment,
        )
