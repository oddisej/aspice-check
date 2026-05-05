"""Unit tests for CalendarMarkdownRenderer.

Requirements: 4.1, 4.2, 4.3, 4.4
"""

from __future__ import annotations

import datetime
import re

import yaml

from confluence_ai.calendar_renderer import CalendarMarkdownRenderer
from confluence_ai.models import CalendarMetadata, DateRange, Event


def _make_metadata() -> CalendarMetadata:
    """Create a sample CalendarMetadata for testing."""
    return CalendarMetadata(
        calendar_id="cal-001",
        calendar_name="Team Leave",
        export_timestamp="2025-01-15T10:00:00+00:00",
        exporter_version="0.2.0",
        date_range=DateRange(
            start=datetime.datetime(2024, 12, 16, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2025, 4, 15, tzinfo=datetime.timezone.utc),
        ),
        event_count=0,
    )


def _make_all_day_event() -> Event:
    """Create an all-day event."""
    return Event(
        event_id="evt-001",
        summary="Alice out",
        start=datetime.datetime(2025, 1, 2, 0, 0, tzinfo=datetime.timezone.utc),
        end=datetime.datetime(2025, 1, 3, 0, 0, tzinfo=datetime.timezone.utc),
        all_day=True,
        description="",
        location="",
        organizer="alice@acme.com",
        sub_calendar_id="cal-001-leaves",
        sub_calendar_name="Leaves",
    )


def _make_timed_event() -> Event:
    """Create a timed event."""
    return Event(
        event_id="evt-002",
        summary="Sprint planning",
        start=datetime.datetime(2025, 1, 5, 9, 0, tzinfo=datetime.timezone.utc),
        end=datetime.datetime(2025, 1, 5, 10, 30, tzinfo=datetime.timezone.utc),
        all_day=False,
        description="Agenda link in wiki.",
        location="Room 3 / Zoom",
        organizer="bob@acme.com",
        sub_calendar_id="cal-001",
        sub_calendar_name="Team Leave",
    )


def _extract_yaml_block(output: str) -> str:
    """Extract the YAML front-matter content between --- markers."""
    parts = output.split("---\n")
    # parts[0] is empty (before first ---), parts[1] is the YAML content
    assert len(parts) >= 3, f"Expected at least 3 parts, got {len(parts)}"
    return parts[1]


class TestMarkdownFrontMatter:
    """Test YAML front-matter block."""

    def test_output_starts_with_triple_dash(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_all_day_event()]

        output = renderer.render(events, metadata)

        assert output.startswith("---\n")

    def test_output_contains_closing_triple_dash(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_all_day_event()]

        output = renderer.render(events, metadata)

        # Should have at least two --- lines
        lines = output.split("\n")
        dash_lines = [i for i, line in enumerate(lines) if line == "---"]
        assert len(dash_lines) >= 2

    def test_yaml_block_parses_with_required_keys(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_all_day_event(), _make_timed_event()]

        output = renderer.render(events, metadata)
        yaml_content = _extract_yaml_block(output)
        parsed = yaml.safe_load(yaml_content)

        assert "calendar_id" in parsed
        assert "calendar_name" in parsed
        assert "export_timestamp" in parsed
        assert "exporter_version" in parsed
        assert "date_range" in parsed
        assert "start" in parsed["date_range"]
        assert "end" in parsed["date_range"]
        assert "event_count" in parsed

    def test_yaml_values_match_metadata(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_all_day_event(), _make_timed_event()]

        output = renderer.render(events, metadata)
        yaml_content = _extract_yaml_block(output)
        parsed = yaml.safe_load(yaml_content)

        assert parsed["calendar_id"] == metadata.calendar_id
        assert parsed["calendar_name"] == metadata.calendar_name
        assert parsed["export_timestamp"] == metadata.export_timestamp
        assert parsed["exporter_version"] == metadata.exporter_version
        assert parsed["event_count"] == len(events)
        assert parsed["date_range"]["start"] == "2024-12-16"
        assert parsed["date_range"]["end"] == "2025-04-15"


class TestMarkdownHeading:
    """Test H1 heading."""

    def test_h1_heading_present(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_all_day_event()]

        output = renderer.render(events, metadata)

        assert f"# {metadata.calendar_name}" in output


class TestMarkdownAllDayEvents:
    """Test all-day event rendering."""

    def test_all_day_event_contains_all_day_text(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_all_day_event()]

        output = renderer.render(events, metadata)

        assert "All day" in output

    def test_all_day_event_no_hhmm_time(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_all_day_event()]

        output = renderer.render(events, metadata)

        # Find the event bullet line
        for line in output.split("\n"):
            if "Alice out" in line and line.startswith("- **"):
                # Should not contain HH:MM pattern
                assert not re.search(r"\d{2}:\d{2}", line)
                break


class TestMarkdownTimedEvents:
    """Test timed event rendering."""

    def test_timed_event_contains_two_hhmm_times(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_timed_event()]

        output = renderer.render(events, metadata)

        # Find the event bullet line
        for line in output.split("\n"):
            if "Sprint planning" in line and line.startswith("- **"):
                times = re.findall(r"\d{2}:\d{2}", line)
                assert len(times) == 2
                assert times[0] == "09:00"
                assert times[1] == "10:30"
                break

    def test_timed_event_no_all_day_text(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_timed_event()]

        output = renderer.render(events, metadata)

        # Find the event bullet line
        for line in output.split("\n"):
            if "Sprint planning" in line and line.startswith("- **"):
                assert "All day" not in line
                break

    def test_timed_event_uses_en_dash(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_timed_event()]

        output = renderer.render(events, metadata)

        # Find the event bullet line — should contain en-dash (U+2013)
        for line in output.split("\n"):
            if "Sprint planning" in line and line.startswith("- **"):
                assert "\u2013" in line
                break


class TestMarkdownGroupingAndOrdering:
    """Test event grouping by date and chronological ordering."""

    def test_events_grouped_by_date_with_h2_headers(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_all_day_event(), _make_timed_event()]

        output = renderer.render(events, metadata)

        assert "## 2025-01-02" in output
        assert "## 2025-01-05" in output

    def test_date_headers_in_ascending_order(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        # Provide events in reverse order
        events = [_make_timed_event(), _make_all_day_event()]

        output = renderer.render(events, metadata)

        # 2025-01-02 should appear before 2025-01-05
        pos_jan2 = output.index("## 2025-01-02")
        pos_jan5 = output.index("## 2025-01-05")
        assert pos_jan2 < pos_jan5

    def test_events_within_group_sorted_by_start(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        # Two events on the same day, provided in reverse order
        event_late = Event(
            event_id="evt-late",
            summary="Late meeting",
            start=datetime.datetime(2025, 1, 5, 14, 0, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2025, 1, 5, 15, 0, tzinfo=datetime.timezone.utc),
            all_day=False,
        )
        event_early = Event(
            event_id="evt-early",
            summary="Early standup",
            start=datetime.datetime(2025, 1, 5, 9, 0, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2025, 1, 5, 9, 15, tzinfo=datetime.timezone.utc),
            all_day=False,
        )
        events = [event_late, event_early]

        output = renderer.render(events, metadata)

        pos_early = output.index("Early standup")
        pos_late = output.index("Late meeting")
        assert pos_early < pos_late


class TestMarkdownSubBullets:
    """Test optional sub-bullets for location, organizer, description."""

    def test_location_sub_bullet_when_present(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_timed_event()]

        output = renderer.render(events, metadata)

        assert "  - Location: Room 3 / Zoom" in output

    def test_organizer_sub_bullet_when_present(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_timed_event()]

        output = renderer.render(events, metadata)

        assert "  - Organizer: bob@acme.com" in output

    def test_description_sub_bullet_when_present(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events = [_make_timed_event()]

        output = renderer.render(events, metadata)

        assert "  - Description: Agenda link in wiki." in output

    def test_no_sub_bullets_when_fields_empty(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        event = Event(
            event_id="evt-empty",
            summary="Minimal event",
            start=datetime.datetime(2025, 1, 10, 8, 0, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2025, 1, 10, 9, 0, tzinfo=datetime.timezone.utc),
            all_day=False,
            description="",
            location="",
            organizer="",
        )
        events = [event]

        output = renderer.render(events, metadata)

        assert "  - Location:" not in output
        assert "  - Organizer:" not in output
        assert "  - Description:" not in output

    def test_multiline_description_uses_blockquote(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        event = Event(
            event_id="evt-multi",
            summary="Multi-line desc",
            start=datetime.datetime(2025, 1, 10, 8, 0, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2025, 1, 10, 9, 0, tzinfo=datetime.timezone.utc),
            all_day=False,
            description="First line\nSecond line\nThird line",
        )
        events = [event]

        output = renderer.render(events, metadata)

        assert "  - Description: First line" in output
        assert "    > Second line" in output
        assert "    > Third line" in output


class TestMarkdownEmptyEvents:
    """Test rendering with no events."""

    def test_empty_events_still_has_frontmatter_and_heading(self) -> None:
        renderer = CalendarMarkdownRenderer()
        metadata = _make_metadata()
        events: list[Event] = []

        output = renderer.render(events, metadata)

        assert output.startswith("---\n")
        assert f"# {metadata.calendar_name}" in output
        yaml_content = _extract_yaml_block(output)
        parsed = yaml.safe_load(yaml_content)
        assert parsed["event_count"] == 0
