"""Calendar export orchestration module.

Coordinates calendar event retrieval, rendering, and file output into a
single convenience function: ``export_calendar()``.

Also provides ``export_calendar_grouped()`` which resolves the parent
calendar's descriptive name and produces a unified view of all subcalendar
events.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
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
from confluence_ai.exceptions import (
    AuthenticationError,
    CalendarAPIError,
    CalendarNotFoundError,
)
from confluence_ai.models import (
    CalendarExportResult,
    CalendarMetadata,
    DateRange,
    Event,
)


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
    # If events come from multiple sub-calendars (parent was auto-resolved
    # to children), fall back to calendar_id since we can't easily get the
    # parent name without space_key. If all events share one sub_calendar_name,
    # use that. Otherwise fall back to calendar_id.
    calendar_name = calendar_id
    if events:
        unique_names = {e.sub_calendar_name for e in events if e.sub_calendar_name}
        if len(unique_names) == 1:
            calendar_name = unique_names.pop()
        # len(unique_names) > 1 means parent resolved to multiple children;
        # len(unique_names) == 0 means no sub_calendar_name on any event;
        # both cases fall back to calendar_id (already set above).

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


def _resolve_calendar_name(
    client: CalendarClient,
    calendar_id: str,
    events: list[Event],
) -> str:
    """Resolve the calendar name for grouped export.

    Attempts to get the parent calendar's descriptive name via
    ``list_subcalendars``. If that fails (because ``calendar_id`` is a
    child), falls back to event-based name resolution.

    Args:
        client: The CalendarClient instance.
        calendar_id: The calendar ID being exported.
        events: The fetched events list.

    Returns:
        The resolved calendar name string.

    Requirements: 1.1, 1.2, 1.3, 1.4
    """
    # Try to resolve as parent calendar
    try:
        parent_cal = client.list_subcalendars(calendar_id, space_key="")
        if parent_cal.name:
            return parent_cal.name
    except (CalendarNotFoundError, CalendarAPIError):
        pass

    # Fall back to event-based resolution
    if events:
        unique_names = {e.sub_calendar_name for e in events if e.sub_calendar_name}
        if len(unique_names) == 1:
            return unique_names.pop()

    return calendar_id


def export_calendar_grouped(
    *,
    base_url: str,
    calendar_id: str,
    output_dir: str,
    email: str,
    api_token: str,
    output_format: str = "json",
    date_range: DateRange | None = None,
) -> CalendarExportResult:
    """Export a calendar with unified subcalendar grouping.

    When given a parent calendar ID, resolves the parent's descriptive
    name and uses it as the ``calendar_name`` in the output. All events
    from child subcalendars are merged into a single output file.

    When given a child subcalendar ID, behaves identically to
    ``export_calendar()`` (single subcalendar export).

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

    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 3.2, 4.1, 4.2, 4.3
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

    # Step 5: Resolve calendar name via helper
    calendar_name = _resolve_calendar_name(client, calendar_id, events)

    # Step 6: Determine show_subcalendar
    unique_sub_names = {e.sub_calendar_name for e in events if e.sub_calendar_name}
    show_subcalendar = len(unique_sub_names) > 1

    # Step 7: Select renderer based on output_format
    valid_formats = ("json", "markdown")
    if output_format == "json":
        renderer = CalendarJSONRenderer()
        extension = "json"
    elif output_format == "markdown":
        renderer = CalendarMarkdownRenderer(show_subcalendar=show_subcalendar)
        extension = "md"
    else:
        raise ValueError(
            f"Unknown output_format {output_format!r}. "
            f"Valid formats: {', '.join(valid_formats)}"
        )

    # Step 8: Build CalendarMetadata
    metadata = CalendarMetadata(
        calendar_id=calendar_id,
        calendar_name=calendar_name,
        export_timestamp=datetime.now(timezone.utc).isoformat(),
        exporter_version=confluence_ai.__version__,
        date_range=date_range,
        event_count=len(events),
    )

    # Step 8b: Sort events chronologically by start time (Requirement 2.2)
    events.sort(key=lambda e: e.start)

    # Step 9: Render, sanitize filename, write to output_dir
    os.makedirs(output_dir, exist_ok=True)
    filename = _sanitize_calendar_name(calendar_name) + "." + extension
    output_path = os.path.join(output_dir, filename)

    content = renderer.render(events, metadata)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Step 10: Return result
    return CalendarExportResult(
        output_path=output_path,
        event_count=len(events),
        warnings=[],
    )
