"""Feature: confluence-calendar-export, Property 5: JSON render + parse round-trips events and metadata."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.calendar_renderer import CalendarJSONRenderer
from confluence_ai.models import CalendarMetadata, DateRange, Event


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_tz_aware_dt_st = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)

_text_st = st.text(min_size=1, max_size=50)


def st_event() -> st.SearchStrategy[Event]:
    """Generate a valid Event instance."""
    return st.builds(
        _build_event,
        event_id=st.text(min_size=1, max_size=20, alphabet="abcdef0123456789-"),
        summary=_text_st,
        start=_tz_aware_dt_st,
        duration_hours=st.integers(min_value=1, max_value=48),
        all_day=st.booleans(),
        description=st.text(min_size=0, max_size=100),
        location=st.text(min_size=0, max_size=50),
        organizer=st.text(min_size=0, max_size=30),
        sub_calendar_id=st.text(min_size=0, max_size=20),
        sub_calendar_name=st.text(min_size=0, max_size=30),
    )


def _build_event(
    event_id: str,
    summary: str,
    start: datetime,
    duration_hours: int,
    all_day: bool,
    description: str,
    location: str,
    organizer: str,
    sub_calendar_id: str,
    sub_calendar_name: str,
) -> Event:
    end = start + timedelta(hours=duration_hours)
    return Event(
        event_id=event_id,
        summary=summary,
        start=start,
        end=end,
        all_day=all_day,
        description=description,
        location=location,
        organizer=organizer,
        sub_calendar_id=sub_calendar_id,
        sub_calendar_name=sub_calendar_name,
    )


def st_metadata() -> st.SearchStrategy[CalendarMetadata]:
    """Generate a valid CalendarMetadata instance."""
    return st.builds(
        _build_metadata,
        calendar_id=st.text(min_size=1, max_size=20),
        calendar_name=_text_st,
        start=_tz_aware_dt_st,
        range_days=st.integers(min_value=1, max_value=180),
    )


def _build_metadata(
    calendar_id: str,
    calendar_name: str,
    start: datetime,
    range_days: int,
) -> CalendarMetadata:
    return CalendarMetadata(
        calendar_id=calendar_id,
        calendar_name=calendar_name,
        export_timestamp=datetime.now(timezone.utc).isoformat(),
        exporter_version="0.3.0",
        date_range=DateRange(start=start, end=start + timedelta(days=range_days)),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty05JSONRoundtrip:
    """Property 5: JSON render + parse round-trips events and metadata."""

    @given(
        metadata=st_metadata(),
        events=st.lists(st_event(), min_size=0, max_size=10),
    )
    @settings(max_examples=100)
    def test_json_parses_successfully(
        self, metadata: CalendarMetadata, events: list[Event]
    ) -> None:
        """Rendered JSON parses back via json.loads without error.

        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        renderer = CalendarJSONRenderer()
        output = renderer.render(events, metadata)
        parsed = json.loads(output)
        assert "metadata" in parsed
        assert "events" in parsed

    @given(
        metadata=st_metadata(),
        events=st.lists(st_event(), min_size=0, max_size=10),
    )
    @settings(max_examples=100)
    def test_event_count_matches(
        self, metadata: CalendarMetadata, events: list[Event]
    ) -> None:
        """events array length equals len(E) and metadata.event_count matches.

        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        renderer = CalendarJSONRenderer()
        output = renderer.render(events, metadata)
        parsed = json.loads(output)
        assert len(parsed["events"]) == len(events)
        assert parsed["metadata"]["event_count"] == len(events)

    @given(
        metadata=st_metadata(),
        events=st.lists(st_event(), min_size=1, max_size=5),
    )
    @settings(max_examples=100)
    def test_event_fields_roundtrip(
        self, metadata: CalendarMetadata, events: list[Event]
    ) -> None:
        """Each event's fields match the original Event by value.

        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        renderer = CalendarJSONRenderer()
        output = renderer.render(events, metadata)
        parsed = json.loads(output)

        for i, event in enumerate(events):
            parsed_event = parsed["events"][i]
            assert parsed_event["event_id"] == event.event_id
            assert parsed_event["summary"] == event.summary
            assert parsed_event["all_day"] == event.all_day
            assert parsed_event["description"] == event.description
            assert parsed_event["location"] == event.location
            assert parsed_event["organizer"] == event.organizer
            # Datetime fields: parse and compare by UTC instant
            parsed_start = datetime.fromisoformat(parsed_event["start"])
            parsed_end = datetime.fromisoformat(parsed_event["end"])
            assert parsed_start == event.start
            assert parsed_end == event.end

    @given(
        metadata=st_metadata(),
        events=st.lists(st_event(), min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_metadata_fields_roundtrip(
        self, metadata: CalendarMetadata, events: list[Event]
    ) -> None:
        """metadata dict contains every field of M with correct values.

        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        renderer = CalendarJSONRenderer()
        output = renderer.render(events, metadata)
        parsed = json.loads(output)
        meta = parsed["metadata"]

        assert meta["calendar_id"] == metadata.calendar_id
        assert meta["calendar_name"] == metadata.calendar_name
        assert meta["exporter_version"] == metadata.exporter_version
        # Date range: compare by UTC instant
        parsed_start = datetime.fromisoformat(meta["date_range"]["start"])
        parsed_end = datetime.fromisoformat(meta["date_range"]["end"])
        assert parsed_start == metadata.date_range.start
        assert parsed_end == metadata.date_range.end
