"""Calendar renderers for the Confluence Calendar export feature.

Provides two renderers:
- CalendarJSONRenderer: machine-readable JSON output
- CalendarMarkdownRenderer: human-readable Markdown output with YAML front-matter

These renderers are NOT registered in the page OutputRenderer registry; they
operate on calendar Event/CalendarMetadata models rather than ContentNode IR.

Requirements: 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4
"""

from __future__ import annotations

import datetime
import json
from typing import Any

from confluence_ai.models import CalendarMetadata, DateRange, Event


def _ensure_tz_aware(dt: datetime.datetime) -> datetime.datetime:
    """Return a tz-aware datetime; normalise naive datetimes to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def _serialize_event(event: Event) -> dict[str, Any]:
    """Serialize a single Event to a JSON-compatible dict."""
    return {
        "event_id": event.event_id,
        "summary": event.summary,
        "start": _ensure_tz_aware(event.start).isoformat(),
        "end": _ensure_tz_aware(event.end).isoformat(),
        "all_day": event.all_day,
        "description": event.description,
        "location": event.location,
        "organizer": event.organizer,
        "sub_calendar_id": event.sub_calendar_id,
        "sub_calendar_name": event.sub_calendar_name,
    }


def _serialize_metadata(metadata: CalendarMetadata) -> dict[str, Any]:
    """Serialize CalendarMetadata to a JSON-compatible dict."""
    return {
        "calendar_id": metadata.calendar_id,
        "calendar_name": metadata.calendar_name,
        "export_timestamp": metadata.export_timestamp,
        "exporter_version": metadata.exporter_version,
        "date_range": {
            "start": _ensure_tz_aware(metadata.date_range.start).isoformat(),
            "end": _ensure_tz_aware(metadata.date_range.end).isoformat(),
        },
        "event_count": metadata.event_count,
    }


class CalendarJSONRenderer:
    """Renders calendar events and metadata as a structured JSON document.

    Output shape::

        {
          "metadata": { calendar_id, calendar_name, export_timestamp,
                        exporter_version, date_range: {start, end},
                        event_count },
          "events": [ { event_id, summary, start, end, all_day,
                        description, location, organizer,
                        sub_calendar_id, sub_calendar_name }, ... ]
        }

    The JSON is pretty-printed with ``indent=2`` for readability.
    """

    def render(self, events: list[Event], metadata: CalendarMetadata) -> str:
        """Serialise events + metadata as JSON.

        Parameters
        ----------
        events:
            List of calendar events to render.
        metadata:
            Calendar metadata block.

        Returns
        -------
        str
            The JSON-serialised document.
        """
        # Invariant 4: event_count must equal len(events)
        metadata.event_count = len(events)

        payload: dict[str, Any] = {
            "metadata": _serialize_metadata(metadata),
            "events": [_serialize_event(e) for e in events],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)


class CalendarMarkdownRenderer:
    """Renders calendar events as a Markdown document with YAML front-matter.

    Output structure:
    1. YAML front-matter block (---...---)
    2. H1 heading with calendar name
    3. Events grouped by date (H2 headers), sorted chronologically
    """

    def render(self, events: list[Event], metadata: CalendarMetadata) -> str:
        """Serialise events + metadata as Markdown.

        Parameters
        ----------
        events:
            List of calendar events to render.
        metadata:
            Calendar metadata block.

        Returns
        -------
        str
            The Markdown document.
        """
        # Invariant 4: event_count must equal len(events)
        metadata.event_count = len(events)

        lines: list[str] = []

        # --- YAML front-matter ---
        lines.append("---")
        lines.append(f"calendar_id: \"{metadata.calendar_id}\"")
        lines.append(f"calendar_name: \"{metadata.calendar_name}\"")
        lines.append(f"export_timestamp: \"{metadata.export_timestamp}\"")
        lines.append(f"exporter_version: \"{metadata.exporter_version}\"")
        lines.append("date_range:")
        start_date = _ensure_tz_aware(metadata.date_range.start).strftime("%Y-%m-%d")
        end_date = _ensure_tz_aware(metadata.date_range.end).strftime("%Y-%m-%d")
        lines.append(f"  start: \"{start_date}\"")
        lines.append(f"  end: \"{end_date}\"")
        lines.append(f"event_count: {metadata.event_count}")
        lines.append("---")
        lines.append("")

        # --- H1 heading ---
        lines.append(f"# {metadata.calendar_name}")
        lines.append("")

        # --- Group events by local date ---
        if not events:
            return "\n".join(lines) + "\n"

        # Group by the local date of event.start
        groups: dict[datetime.date, list[Event]] = {}
        for event in events:
            aware_start = _ensure_tz_aware(event.start)
            local_date = aware_start.date()
            if local_date not in groups:
                groups[local_date] = []
            groups[local_date].append(event)

        # Sort groups ascending by date
        sorted_dates = sorted(groups.keys())

        for date in sorted_dates:
            # H2 date header
            lines.append(f"## {date.isoformat()}")
            lines.append("")

            # Sort events within group: ascending by start, then by summary
            group_events = sorted(
                groups[date],
                key=lambda e: (_ensure_tz_aware(e.start), e.summary),
            )

            for event in group_events:
                lines.append(self._render_event_line(event))

                # Optional sub-bullets (only when non-empty)
                if event.location:
                    lines.append(f"  - Location: {event.location}")
                if event.organizer:
                    lines.append(f"  - Organizer: {event.organizer}")
                if event.description:
                    self._render_description(lines, event.description)

            lines.append("")

        return "\n".join(lines) + "\n"

    def _render_event_line(self, event: Event) -> str:
        """Render the main bullet line for an event."""
        if event.all_day:
            return f"- **{event.summary}**  \u2014  All day"
        else:
            start = _ensure_tz_aware(event.start)
            end = _ensure_tz_aware(event.end)
            start_time = start.strftime("%H:%M")
            end_time = end.strftime("%H:%M")
            tz_name = start.tzname() or "UTC"
            # Use en-dash (U+2013) between times
            return f"- **{event.summary}**  \u2014  {start_time} \u2013 {end_time} {tz_name}"

    def _render_description(self, lines: list[str], description: str) -> None:
        """Render description as a sub-bullet, with blockquote for multi-line."""
        desc_lines = description.split("\n")
        if len(desc_lines) == 1:
            lines.append(f"  - Description: {desc_lines[0]}")
        else:
            lines.append(f"  - Description: {desc_lines[0]}")
            for extra_line in desc_lines[1:]:
                lines.append(f"    > {extra_line}")
