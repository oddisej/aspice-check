"""Custom exception classes for the Confluence Page Exporter.

Each exception carries structured context (URL, status code, filename, etc.)
to provide descriptive error messages for diagnosis.
"""

from __future__ import annotations


class ExporterError(Exception):
    """Base exception for all Confluence Exporter errors."""

    pass


class InvalidURLError(ExporterError):
    """Raised when a URL does not match the expected Confluence Cloud pattern."""

    def __init__(self, url: str, message: str | None = None) -> None:
        self.url = url
        msg = message or (
            f"Invalid Confluence Cloud URL: {url!r}. "
            "Expected format: https://{{domain}}.atlassian.net/wiki"
            "/spaces/{{space}}/pages/{{page_id}}/{{optional_title}}"
        )
        super().__init__(msg)


class AuthenticationError(ExporterError):
    """Raised when Confluence authentication fails."""

    def __init__(
        self,
        base_url: str,
        status_code: int | None = None,
        message: str | None = None,
    ) -> None:
        self.base_url = base_url
        self.status_code = status_code
        msg = message or (
            f"Authentication failed for {base_url}"
            f"{f' (HTTP {status_code})' if status_code else ''}. "
            "Check your email and API token."
        )
        super().__init__(msg)


class ConfluenceConnectionError(ExporterError):
    """Raised when the Confluence base URL is unreachable.

    Named ``ConfluenceConnectionError`` to avoid shadowing the builtin
    ``ConnectionError``.
    """

    def __init__(
        self,
        base_url: str,
        message: str | None = None,
    ) -> None:
        self.base_url = base_url
        msg = message or (
            f"Could not connect to {base_url}. "
            "Verify the URL is correct and the server is reachable."
        )
        super().__init__(msg)


class PageNotFoundError(ExporterError):
    """Raised when a Confluence page cannot be found or accessed."""

    def __init__(
        self,
        page_id: str,
        status_code: int | None = None,
        message: str | None = None,
    ) -> None:
        self.page_id = page_id
        self.status_code = status_code
        if message:
            msg = message
        elif status_code == 403:
            msg = (
                f"Access denied for page {page_id} (HTTP 403). "
                "The authenticated user may lack read permission."
            )
        else:
            msg = (
                f"Page {page_id} not found"
                f"{f' (HTTP {status_code})' if status_code else ''}."
            )
        super().__init__(msg)


class ParseError(ExporterError):
    """Raised when Confluence storage format XHTML cannot be parsed."""

    def __init__(self, message: str | None = None) -> None:
        msg = message or "Failed to parse Confluence storage format XHTML."
        super().__init__(msg)


class DownloadError(ExporterError):
    """Raised when an image or attachment download fails."""

    def __init__(
        self,
        filename: str,
        url: str | None = None,
        status_code: int | None = None,
        message: str | None = None,
    ) -> None:
        self.filename = filename
        self.url = url
        self.status_code = status_code
        msg = message or (
            f"Failed to download {filename!r}"
            f"{f' from {url}' if url else ''}"
            f"{f' (HTTP {status_code})' if status_code else ''}."
        )
        super().__init__(msg)


class ImageDescriptionError(ExporterError):
    """Raised when AI image description generation fails."""

    def __init__(
        self,
        image_path: str,
        provider: str | None = None,
        message: str | None = None,
    ) -> None:
        self.image_path = image_path
        self.provider = provider
        msg = message or (
            f"Failed to generate description for {image_path!r}"
            f"{f' using {provider} provider' if provider else ''}."
        )
        super().__init__(msg)


class FileSystemError(ExporterError):
    """Raised when a filesystem operation fails (create dir, write file)."""

    def __init__(
        self,
        path: str,
        operation: str = "access",
        message: str | None = None,
    ) -> None:
        self.path = path
        self.operation = operation
        msg = message or f"Filesystem error: could not {operation} {path!r}."
        super().__init__(msg)


class CalendarNotFoundError(ExporterError):
    """Raised when a calendar ID is not found or the user lacks access."""

    def __init__(
        self,
        calendar_id: str,
        status_code: int | None = None,
        message: str | None = None,
    ) -> None:
        self.calendar_id = calendar_id
        self.status_code = status_code
        if message:
            msg = message
        elif status_code == 403:
            msg = (
                f"Access denied for calendar {calendar_id!r} (HTTP 403). "
                "The authenticated user may lack read permission."
            )
        else:
            msg = (
                f"Calendar {calendar_id!r} not found"
                f"{f' (HTTP {status_code})' if status_code else ''}."
            )
        super().__init__(msg)


class CalendarAPIError(ExporterError):
    """Raised when the Team Calendars REST API returns an unexpected error."""

    def __init__(
        self,
        endpoint: str,
        status_code: int | None = None,
        message: str | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.status_code = status_code
        msg = message or (
            f"Calendar API error at {endpoint!r}"
            f"{f' (HTTP {status_code})' if status_code else ''}."
        )
        super().__init__(msg)
