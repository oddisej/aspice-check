"""Unit tests for CalendarMarkdownRenderer show_subcalendar behavior.

Requirements: 3.3
"""

from __future__ import annotations

import datetime

from confluence_ai.calendar_renderer import CalendarMarkdownRenderer
from confluence_ai.models import CalendarMetadata, DateRange, Event


def _make_metadata() -> CalendarMetadata:
    """Create a sample CalendarMetadata for testing."""
    return CalendarMetadata(
        calendar_id="cal-001",
        calendar_name="Team Calendar",
        export_timestamp="2025-01-15T10:00:00+00:00",
        exporter_version="0.2.0",
        date_range=DateRange(
            start=datetime.datetime(2024, 12, 16, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2025, 4, 15, tzinfo=datetime.timezone.utc),
        ),
        event_count=0,
    )


def _make_event_with_subcalendar(
    event_id: str = "evt-001",
    summary: str = "Alice out",
    sub_calendar_name: str = "Leaves",
) -> Event:
    """Create an event with a sub_calendar_name."""
    return Event(
        event_id=event_id,
        summary=summary,
        start=datetime.datetime(2025, 1, 2, 0, 0, tzinfo=datetime.timezone.utc),
        end=datetime.datetime(2025, 1, 3, 0, 0, tzinfo=datetime.timezone.utc),
        all_day=True,
        description="",
        location="",
        organizer="alice@acme.com",
        sub_calendar_id="cal-001-leaves",
        sub_calendar_name=sub_calendar_name,
    )


class TestShowSubcalendarTrue:
    """Test that show_subcalendar=True includes Calendar: sub-bullets."""

    def test_includes_calendar_sub_bullet_for_event(self) -> None:
        renderer = CalendarMarkdownRenderer(show_subcalendar=True)
        metadata = _make_metadata()
        events = [_make_event_with_subcalendar(sub_calendar_name="Leaves")]

        output = renderer.render(events, metadata)

        assert "  - Calendar: Leaves" in output

    def test_includes_calendar_sub_bullet_for_multiple_events(self) -> None:
        renderer = CalendarMarkdownRenderer(show_subcalendar=True)
        metadata = _make_metadata()
        events = [
            _make_event_with_subcalendar(
                event_id="evt-001", summary="Alice out", sub_calendar_name="Leaves"
            ),
            _make_event_with_subcalendar(
                event_id="evt-002", summary="Bob travel", sub_calendar_name="Travel"
            ),
        ]

        output = renderer.render(events, metadata)

        assert "  - Calendar: Leaves" in output
        assert "  - Calendar: Travel" in output

    def test_calendar_sub_bullet_appears_after_event_line(self) -> None:
        renderer = CalendarMarkdownRenderer(show_subcalendar=True)
        metadata = _make_metadata()
        events = [_make_event_with_subcalendar(sub_calendar_name="Leaves")]

        output = renderer.render(events, metadata)
        lines = output.split("\n")

        # Find the event bullet line and the Calendar sub-bullet
        event_line_idx = None
        calendar_line_idx = None
        for i, line in enumerate(lines):
            if "Alice out" in line and line.startswith("- **"):
                event_line_idx = i
            if "  - Calendar: Leaves" in line:
                calendar_line_idx = i

        assert event_line_idx is not None
        assert calendar_line_idx is not None
        assert calendar_line_idx == event_line_idx + 1


class TestShowSubcalendarFalse:
    """Test that show_subcalendar=False does NOT include Calendar: sub-bullets."""

    def test_no_calendar_sub_bullet_with_default(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_event_with_subcalendar(sub_calendar_name="Leaves")]

        output = renderer.render(events, metadata)

        assert "  - Calendar:" not in output

    def test_no_calendar_sub_bullet_with_explicit_false(self) -> None:
        renderer = CalendarMarkdownRenderer(show_subcalendar=False)
        metadata = _make_metadata()
        events = [_make_event_with_subcalendar(sub_calendar_name="Leaves")]

        output = renderer.render(events, metadata)

        assert "  - Calendar:" not in output

    def test_no_calendar_sub_bullet_even_with_multiple_subcalendars(self) -> None:
        renderer = CalendarMarkdownRenderer(show_subcalendar=False)
        metadata = _make_metadata()
        events = [
            _make_event_with_subcalendar(
                event_id="evt-001", summary="Alice out", sub_calendar_name="Leaves"
            ),
            _make_event_with_subcalendar(
                event_id="evt-002", summary="Bob travel", sub_calendar_name="Travel"
            ),
        ]

        output = renderer.render(events, metadata)

        assert "  - Calendar:" not in output


class TestEmptySubcalendarName:
    """Test that empty sub_calendar_name does not produce Calendar: sub-bullet."""

    def test_no_calendar_sub_bullet_when_name_empty(self) -> None:
        renderer = CalendarMarkdownRenderer(show_subcalendar=True)
        metadata = _make_metadata()
        events = [_make_event_with_subcalendar(sub_calendar_name="")]

        output = renderer.render(events, metadata)

        assert "  - Calendar:" not in output

    def test_mixed_empty_and_nonempty_subcalendar_names(self) -> None:
        renderer = CalendarMarkdownRenderer(show_subcalendar=True)
        metadata = _make_metadata()
        events = [
            _make_event_with_subcalendar(
                event_id="evt-001", summary="Alice out", sub_calendar_name="Leaves"
            ),
            _make_event_with_subcalendar(
                event_id="evt-002", summary="Unknown event", sub_calendar_name=""
            ),
        ]

        output = renderer.render(events, metadata)

        # The event with a name gets the sub-bullet
        assert "  - Calendar: Leaves" in output
        # Count occurrences — should be exactly one Calendar: line
        calendar_lines = [
            line for line in output.split("\n") if "  - Calendar:" in line
        ]
        assert len(calendar_lines) == 1


# ---------------------------------------------------------------------------
# Unit tests for _resolve_calendar_name and export_calendar_grouped
# Requirements: 1.1, 1.2, 1.3, 1.4, 5.3, 5.4, 5.5, 5.6, 6.4
# ---------------------------------------------------------------------------

import json
import os
from datetime import timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from confluence_ai.calendar_export import (
    _resolve_calendar_name,
    export_calendar,
    export_calendar_grouped,
)
from confluence_ai.exceptions import CalendarNotFoundError
from confluence_ai.models import Calendar, CalendarExportResult, DateRange, SubCalendar


def _make_test_event(
    event_id: str = "evt-001",
    summary: str = "Test Event",
    sub_calendar_id: str = "sub-cal-001",
    sub_calendar_name: str = "Leaves",
) -> Event:
    """Create a minimal Event for grouped export tests."""
    return Event(
        event_id=event_id,
        summary=summary,
        start=datetime.datetime(2025, 1, 15, 9, 0, tzinfo=datetime.timezone.utc),
        end=datetime.datetime(2025, 1, 15, 10, 0, tzinfo=datetime.timezone.utc),
        all_day=False,
        description="",
        location="",
        organizer="user@example.com",
        sub_calendar_id=sub_calendar_id,
        sub_calendar_name=sub_calendar_name,
    )


class TestResolveCalendarNameParentID:
    """Test _resolve_calendar_name when calendar_id is a parent."""

    def test_returns_parent_name_from_list_subcalendars(self, mocker) -> None:
        """When list_subcalendars returns a Calendar with a name, use it."""
        mock_client = MagicMock()
        mock_client.list_subcalendars.return_value = Calendar(
            calendar_id="parent-001",
            name="Team Calendar",
            type="custom",
            space_key="ENG",
            description="",
            sub_calendars=[],
        )
        events = [_make_test_event()]

        result = _resolve_calendar_name(mock_client, "parent-001", events)

        assert result == "Team Calendar"
        mock_client.list_subcalendars.assert_called_once_with("parent-001", space_key="")


class TestResolveCalendarNameChildID:
    """Test _resolve_calendar_name when calendar_id is a child subcalendar."""

    def test_falls_back_to_event_sub_calendar_name(self, mocker) -> None:
        """When list_subcalendars raises CalendarNotFoundError, fall back to event name."""
        mock_client = MagicMock()
        mock_client.list_subcalendars.side_effect = CalendarNotFoundError(
            calendar_id="child-001", status_code=404
        )
        events = [
            _make_test_event(sub_calendar_name="Team Leave"),
            _make_test_event(event_id="evt-002", sub_calendar_name="Team Leave"),
        ]

        result = _resolve_calendar_name(mock_client, "child-001", events)

        assert result == "Team Leave"


class TestResolveCalendarNameFallbackChain:
    """Test _resolve_calendar_name fallback when no events are available."""

    def test_returns_raw_calendar_id_when_no_events(self, mocker) -> None:
        """When list_subcalendars fails and no events exist, return calendar_id."""
        mock_client = MagicMock()
        mock_client.list_subcalendars.side_effect = CalendarNotFoundError(
            calendar_id="orphan-id", status_code=404
        )
        events: list[Event] = []

        result = _resolve_calendar_name(mock_client, "orphan-id", events)

        assert result == "orphan-id"


class TestExportCalendarGroupedParentID:
    """Test export_calendar_grouped with a parent calendar ID."""

    def test_output_uses_resolved_parent_name(self, tmp_path, mocker) -> None:
        """Output file uses the resolved parent name and metadata has correct calendar_name."""
        events = [
            _make_test_event(event_id="evt-1", sub_calendar_name="Leaves"),
            _make_test_event(event_id="evt-2", sub_calendar_name="Travel"),
        ]

        mock_client_cls = mocker.patch(
            "confluence_ai.calendar_export.CalendarClient"
        )
        mock_client_instance = MagicMock()
        mock_client_instance.get_events.return_value = events
        mock_client_instance.list_subcalendars.return_value = Calendar(
            calendar_id="parent-001",
            name="Team Calendar",
            type="custom",
            space_key="ENG",
            description="",
            sub_calendars=[],
        )
        mock_client_cls.return_value = mock_client_instance

        result = export_calendar_grouped(
            base_url="https://acme.atlassian.net/wiki",
            calendar_id="parent-001",
            output_dir=str(tmp_path),
            email="user@example.com",
            api_token="token-123",
            output_format="json",
        )

        assert isinstance(result, CalendarExportResult)
        assert os.path.exists(result.output_path)
        assert "Team_Calendar" in os.path.basename(result.output_path)

        # Verify JSON metadata has correct calendar_name
        with open(result.output_path, "r") as f:
            data = json.load(f)
        assert data["metadata"]["calendar_name"] == "Team Calendar"


class TestExportCalendarGroupedChildID:
    """Test export_calendar_grouped with a child subcalendar ID."""

    def test_behaves_like_export_calendar_for_child_id(self, tmp_path, mocker) -> None:
        """When list_subcalendars raises CalendarNotFoundError, behaves like export_calendar."""
        events = [
            _make_test_event(event_id="evt-1", sub_calendar_name="Team Leave"),
            _make_test_event(event_id="evt-2", sub_calendar_name="Team Leave"),
        ]

        mock_client_cls = mocker.patch(
            "confluence_ai.calendar_export.CalendarClient"
        )
        mock_client_instance = MagicMock()
        mock_client_instance.get_events.return_value = events
        mock_client_instance.list_subcalendars.side_effect = CalendarNotFoundError(
            calendar_id="child-001", status_code=404
        )
        mock_client_cls.return_value = mock_client_instance

        result = export_calendar_grouped(
            base_url="https://acme.atlassian.net/wiki",
            calendar_id="child-001",
            output_dir=str(tmp_path),
            email="user@example.com",
            api_token="token-123",
            output_format="json",
        )

        assert isinstance(result, CalendarExportResult)
        assert result.event_count == 2
        assert os.path.exists(result.output_path)

        # Verify it falls back to the event's sub_calendar_name
        with open(result.output_path, "r") as f:
            data = json.load(f)
        assert data["metadata"]["calendar_name"] == "Team Leave"


class TestShowSubcalendarGroupedExport:
    """Test show_subcalendar logic in export_calendar_grouped."""

    def test_show_subcalendar_true_with_multiple_sub_calendar_names(
        self, tmp_path, mocker
    ) -> None:
        """Markdown output contains Calendar: sub-bullets when events have multiple sub_calendar_names."""
        events = [
            _make_test_event(event_id="evt-1", sub_calendar_name="Leaves"),
            _make_test_event(event_id="evt-2", sub_calendar_name="Travel"),
        ]

        mock_client_cls = mocker.patch(
            "confluence_ai.calendar_export.CalendarClient"
        )
        mock_client_instance = MagicMock()
        mock_client_instance.get_events.return_value = events
        mock_client_instance.list_subcalendars.return_value = Calendar(
            calendar_id="parent-001",
            name="Team Calendar",
            type="custom",
            space_key="ENG",
            description="",
            sub_calendars=[],
        )
        mock_client_cls.return_value = mock_client_instance

        result = export_calendar_grouped(
            base_url="https://acme.atlassian.net/wiki",
            calendar_id="parent-001",
            output_dir=str(tmp_path),
            email="user@example.com",
            api_token="token-123",
            output_format="markdown",
        )

        with open(result.output_path, "r") as f:
            content = f.read()

        assert "  - Calendar: Leaves" in content
        assert "  - Calendar: Travel" in content

    def test_show_subcalendar_false_with_single_sub_calendar_name(
        self, tmp_path, mocker
    ) -> None:
        """Markdown output does NOT contain Calendar: sub-bullets when events have single sub_calendar_name."""
        events = [
            _make_test_event(event_id="evt-1", sub_calendar_name="Leaves"),
            _make_test_event(event_id="evt-2", sub_calendar_name="Leaves"),
        ]

        mock_client_cls = mocker.patch(
            "confluence_ai.calendar_export.CalendarClient"
        )
        mock_client_instance = MagicMock()
        mock_client_instance.get_events.return_value = events
        mock_client_instance.list_subcalendars.return_value = Calendar(
            calendar_id="parent-001",
            name="Team Calendar",
            type="custom",
            space_key="ENG",
            description="",
            sub_calendars=[],
        )
        mock_client_cls.return_value = mock_client_instance

        result = export_calendar_grouped(
            base_url="https://acme.atlassian.net/wiki",
            calendar_id="parent-001",
            output_dir=str(tmp_path),
            email="user@example.com",
            api_token="token-123",
            output_format="markdown",
        )

        with open(result.output_path, "r") as f:
            content = f.read()

        assert "  - Calendar:" not in content


class TestExportCalendarUnchanged:
    """Non-regression: export_calendar() does NOT call list_subcalendars."""

    def test_export_calendar_does_not_call_list_subcalendars(
        self, tmp_path, mocker
    ) -> None:
        """export_calendar() should not use list_subcalendars for name resolution."""
        events = [
            _make_test_event(event_id="evt-1", sub_calendar_name="Leaves"),
        ]

        mock_client_cls = mocker.patch(
            "confluence_ai.calendar_export.CalendarClient"
        )
        mock_client_instance = MagicMock()
        mock_client_instance.get_events.return_value = events
        mock_client_cls.return_value = mock_client_instance

        export_calendar(
            base_url="https://acme.atlassian.net/wiki",
            calendar_id="cal-123",
            output_dir=str(tmp_path),
            email="user@example.com",
            api_token="token-123",
        )

        mock_client_instance.list_subcalendars.assert_not_called()


class TestMCPHandlerCallsGroupedExport:
    """Test that the MCP handler calls export_calendar_grouped, not export_calendar."""

    def test_mcp_handler_uses_export_calendar_grouped(self, mocker) -> None:
        """_handle_export_calendar calls confluence_ai.export_calendar_grouped."""
        from aspice_check.mcp_server import AspiceMCPServer

        mock_grouped = mocker.patch(
            "confluence_ai.export_calendar_grouped",
            return_value=CalendarExportResult(
                output_path="/tmp/out.json",
                event_count=5,
                warnings=[],
            ),
        )

        server = AspiceMCPServer()
        params = {
            "base_url": "https://acme.atlassian.net/wiki",
            "calendar_id": "cal-parent-001",
            "output_dir": "/tmp/output",
            "output_format": "json",
        }

        # Set env vars for credentials
        mocker.patch.dict(
            os.environ,
            {"CONFLUENCE_EMAIL": "user@example.com", "CONFLUENCE_API_TOKEN": "tok"},
        )

        result = server._handle_export_calendar(params)

        mock_grouped.assert_called_once()
        assert result["output_path"] == "/tmp/out.json"
        assert result["event_count"] == 5
