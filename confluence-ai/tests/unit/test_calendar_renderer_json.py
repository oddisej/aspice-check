"""Unit tests for CalendarJSONRenderer.

Requirements: 3.1, 3.2, 3.3, 3.4
"""

from __future__ import annotations

import datetime
import json

from confluence_ai.calendar_renderer import CalendarJSONRenderer
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
        event_count=0,  # Will be set by renderer
    )


def _make_events() -> list[Event]:
    """Create a sample list of events for testing."""
    return [
        Event(
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
        ),
        Event(
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
        ),
    ]


class TestCalendarJSONRendererRoundTrip:
    """Test that JSON output round-trips through json.loads."""

    def test_output_has_metadata_and_events_keys(self) -> None:
        renderer = CalendarJSONRenderer()
        metadata = _make_metadata()
        events = _make_events()

        output = renderer.render(events, metadata)
        parsed = json.loads(output)

        assert "metadata" in parsed
        assert "events" in parsed

    def test_event_count_equals_len_events(self) -> None:
        renderer = CalendarJSONRenderer()
        metadata = _make_metadata()
        events = _make_events()

        output = renderer.render(events, metadata)
        parsed = json.loads(output)

        assert parsed["metadata"]["event_count"] == len(events)

    def test_event_count_with_empty_list(self) -> None:
        renderer = CalendarJSONRenderer()
        metadata = _make_metadata()
        events: list[Event] = []

        output = renderer.render(events, metadata)
        parsed = json.loads(output)

        assert parsed["metadata"]["event_count"] == 0
        assert parsed["events"] == []

    def test_datetime_fields_roundtrip_to_same_utc_instant(self) -> None:
        renderer = CalendarJSONRenderer()
        metadata = _make_metadata()
        events = _make_events()

        output = renderer.render(events, metadata)
        parsed = json.loads(output)

        for i, event in enumerate(events):
            parsed_start = datetime.datetime.fromisoformat(parsed["events"][i]["start"])
            parsed_end = datetime.datetime.fromisoformat(parsed["events"][i]["end"])

            assert parsed_start == event.start
            assert parsed_end == event.end

    def test_metadata_date_range_roundtrips(self) -> None:
        renderer = CalendarJSONRenderer()
        metadata = _make_metadata()
        events = _make_events()

        output = renderer.render(events, metadata)
        parsed = json.loads(output)

        dr = parsed["metadata"]["date_range"]
        parsed_start = datetime.datetime.fromisoformat(dr["start"])
        parsed_end = datetime.datetime.fromisoformat(dr["end"])

        assert parsed_start == metadata.date_range.start
        assert parsed_end == metadata.date_range.end

    def test_all_event_fields_present(self) -> None:
        renderer = CalendarJSONRenderer()
        metadata = _make_metadata()
        events = _make_events()

        output = renderer.render(events, metadata)
        parsed = json.loads(output)

        expected_fields = {
            "event_id", "summary", "start", "end", "all_day",
            "description", "location", "organizer",
            "sub_calendar_id", "sub_calendar_name",
        }

        for parsed_event in parsed["events"]:
            assert set(parsed_event.keys()) == expected_fields

    def test_event_field_values_match(self) -> None:
        renderer = CalendarJSONRenderer()
        metadata = _make_metadata()
        events = _make_events()

        output = renderer.render(events, metadata)
        parsed = json.loads(output)

        for i, event in enumerate(events):
            pe = parsed["events"][i]
            assert pe["event_id"] == event.event_id
            assert pe["summary"] == event.summary
            assert pe["all_day"] == event.all_day
            assert pe["description"] == event.description
            assert pe["location"] == event.location
            assert pe["organizer"] == event.organizer
            assert pe["sub_calendar_id"] == event.sub_calendar_id
            assert pe["sub_calendar_name"] == event.sub_calendar_name

    def test_naive_datetime_normalized_to_utc(self) -> None:
        """Naive datetimes should be serialized with UTC timezone."""
        renderer = CalendarJSONRenderer()
        metadata = _make_metadata()
        # Create an event with naive datetime
        events = [
            Event(
                event_id="evt-naive",
                summary="Naive event",
                start=datetime.datetime(2025, 3, 1, 14, 0),  # naive
                end=datetime.datetime(2025, 3, 1, 15, 0),  # naive
                all_day=False,
            ),
        ]

        output = renderer.render(events, metadata)
        parsed = json.loads(output)

        parsed_start = datetime.datetime.fromisoformat(parsed["events"][0]["start"])
        parsed_end = datetime.datetime.fromisoformat(parsed["events"][0]["end"])

        # Should be tz-aware (UTC)
        assert parsed_start.tzinfo is not None
        assert parsed_end.tzinfo is not None
        assert parsed_start == datetime.datetime(
            2025, 3, 1, 14, 0, tzinfo=datetime.timezone.utc
        )

    def test_metadata_fields_present(self) -> None:
        renderer = CalendarJSONRenderer()
        metadata = _make_metadata()
        events = _make_events()

        output = renderer.render(events, metadata)
        parsed = json.loads(output)

        expected_meta_fields = {
            "calendar_id", "calendar_name", "export_timestamp",
            "exporter_version", "date_range", "event_count",
        }
        assert set(parsed["metadata"].keys()) == expected_meta_fields
