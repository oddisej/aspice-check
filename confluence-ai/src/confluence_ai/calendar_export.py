"""Calendar export orchestration module.

Coordinates calendar event retrieval, rendering, and file output into a
single convenience function: ``export_calendar()``.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone

import confluence_ai
from confluence_ai.calendar_client import CalendarClient
from confluence_ai.calendar_renderer import (
    CalendarJSONRenderer,
    CalendarMarkdownRenderer,
)
from confluence_ai.exceptions import AuthenticationError
from confluence_ai.models import CalendarExportResult, CalendarMetadata, DateRange


def _sanitize_calendar_name(name: str) -> str:
    """Sanitize a calendar name for use as a filename.

    Replaces spaces with underscores and strips any character not in
    ``[A-Za-z0-9_\\-]``. Falls back to the literal ``"calendar"`` when
    the result would be empty.

    Args:
        name: The raw calendar name string.

    Returns:
        A filesystem-safe string suitable for use as a filename stem.
    """
    sanitized = name.replace(" ", "_")
    sanitized = re.sub(r"[^A-Za-z0-9_\-]", "", sanitized)
    return sanitized or "calendar"


def export_calendar(
    *,
    base_url: str,
    calendar_id: str,
    output_dir: str,
    email: str,
    api_token: str,
    output_format: str = "json",
    date_range: DateRange | None = None,
) -> CalendarExportResult:
    """Discover the calendar name, fetch events, render, and write file.

    This is the main orchestration entry point for calendar export. It
    validates credentials, resolves defaults, fetches events, renders
    them in the requested format, and writes the output file.

    Args:
        base_url: Confluence Cloud base URL.
        calendar_id: The calendar or sub-calendar ID to export.
        output_dir: Directory where the output file will be written.
        email: User email for Basic Auth.
        api_token: Confluence Cloud API token.
        output_format: Output format — ``"json"`` or ``"markdown"``.
        date_range: Optional time window; defaults to now-30d → now+90d.

    Returns:
        A ``CalendarExportResult`` with the output path, event count,
        and any warnings.

    Raises:
        AuthenticationError: If email or api_token is empty.
        ValueError: If output_format is not ``"json"`` or ``"markdown"``.
        CalendarNotFoundError: If the calendar is not found.
        CalendarAPIError: On unexpected API errors.
        ConfluenceConnectionError: If the server is unreachable.
    """
    # Step 1: Credential validation
    if not email:
        raise AuthenticationError(base_url, message="email required")
    if not api_token:
        raise AuthenticationError(base_url, message="api_token required")

    # Step 2: Resolve default DateRange when None
    if date_range is None:
        now = datetime.now(timezone.utc)
        date_range = DateRange(
            start=now - timedelta(days=30),
            end=now + timedelta(days=90),
        )

    # Step 3: Construct CalendarClient
    client = CalendarClient(base_url=base_url, email=email, api_token=api_token)

    # Step 4: Fetch events
    events = client.get_events(calendar_id, date_range)

    # Step 5: Resolve calendar_name
    calendar_name = calendar_id
    if events and events[0].sub_calendar_name:
        calendar_name = events[0].sub_calendar_name

    # Step 6: Select renderer based on output_format
    valid_formats = ("json", "markdown")
    if output_format == "json":
        renderer = CalendarJSONRenderer()
        extension = "json"
    elif output_format == "markdown":
        renderer = CalendarMarkdownRenderer()
        extension = "md"
    else:
        raise ValueError(
            f"Unknown output_format {output_format!r}. "
            f"Valid formats: {', '.join(valid_formats)}"
        )

    # Step 7: Build CalendarMetadata
    metadata = CalendarMetadata(
        calendar_id=calendar_id,
        calendar_name=calendar_name,
        export_timestamp=datetime.now(timezone.utc).isoformat(),
        exporter_version=confluence_ai.__version__,
        date_range=date_range,
        event_count=len(events),
    )

    # Step 8: Write output file
    os.makedirs(output_dir, exist_ok=True)
    filename = _sanitize_calendar_name(calendar_name) + "." + extension
    output_path = os.path.join(output_dir, filename)

    content = renderer.render(events, metadata)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Step 9: Return result
    return CalendarExportResult(
        output_path=output_path,
        event_count=len(events),
        warnings=[],
    )
