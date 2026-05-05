"""Feature: confluence-calendar-export, Property 3: Event response mapping is field-complete and timezone-aware."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.calendar_client import CalendarClient


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_tz_aware_dt_st = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)


def st_plugin_event_dict() -> st.SearchStrategy[dict]:
    """Generate a raw event dict as returned by the Confluence plugin."""
    return st.builds(
        _build_event_dict,
        event_id=st.text(min_size=1, max_size=20, alphabet="abcdef0123456789-"),
        title=st.text(min_size=1, max_size=50),
        start=_tz_aware_dt_st,
        duration_hours=st.integers(min_value=0, max_value=72),
        all_day=st.booleans(),
        description=st.text(min_size=0, max_size=100),
        location=st.text(min_size=0, max_size=50),
        organizer_email=st.emails(),
        sub_calendar_id=st.text(min_size=1, max_size=20),
        sub_calendar_name=st.text(min_size=1, max_size=30),
    )


def _build_event_dict(
    event_id: str,
    title: str,
    start: datetime,
    duration_hours: int,
    all_day: bool,
    description: str,
    location: str,
    organizer_email: str,
    sub_calendar_id: str,
    sub_calendar_name: str,
) -> dict:
    """Build a raw event dict matching the plugin response shape."""
    end = start + timedelta(hours=max(duration_hours, 1))
    return {
        "id": event_id,
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "allDay": all_day,
        "description": description,
        "location": location,
        "organizer": {"email": organizer_email, "displayName": "User"},
        "subCalendarId": sub_calendar_id,
        "subCalendarName": sub_calendar_name,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty03EventMapping:
    """Property 3: Event response mapping is field-complete and timezone-aware."""

    @given(raw=st_plugin_event_dict())
    @settings(max_examples=100)
    def test_mapped_event_fields_non_none(self, raw: dict) -> None:
        """Every mapped Event has non-None required fields.

        **Validates: Requirements 2.4**
        """
        event = CalendarClient._map_event(raw)
        assert event.event_id is not None
        assert isinstance(event.event_id, str)
        assert event.summary is not None
        assert isinstance(event.summary, str)
        assert event.start is not None
        assert event.end is not None
        assert event.description is not None
        assert isinstance(event.description, str)
        assert event.location is not None
        assert isinstance(event.location, str)
        assert event.organizer is not None
        assert isinstance(event.organizer, str)

    @given(raw=st_plugin_event_dict())
    @settings(max_examples=100)
    def test_mapped_event_tz_aware(self, raw: dict) -> None:
        """start and end are timezone-aware.

        **Validates: Requirements 2.4**
        """
        event = CalendarClient._map_event(raw)
        assert event.start.tzinfo is not None
        assert event.end.tzinfo is not None

    @given(raw=st_plugin_event_dict())
    @settings(max_examples=100)
    def test_mapped_event_end_gte_start(self, raw: dict) -> None:
        """end >= start for every mapped event.

        **Validates: Requirements 2.4**
        """
        event = CalendarClient._map_event(raw)
        assert event.end >= event.start

    @given(raw=st_plugin_event_dict())
    @settings(max_examples=100)
    def test_mapped_event_all_day_is_bool(self, raw: dict) -> None:
        """all_day is a bool reflecting the allDay input flag.

        **Validates: Requirements 2.4**
        """
        event = CalendarClient._map_event(raw)
        assert isinstance(event.all_day, bool)
        assert event.all_day == bool(raw["allDay"])

    @given(events=st.lists(st_plugin_event_dict(), min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_one_event_per_occurrence(self, events: list[dict]) -> None:
        """K raw event dicts produce exactly K Event instances.

        **Validates: Requirements 2.4**
        """
        mapped = [CalendarClient._map_event(raw) for raw in events]
        assert len(mapped) == len(events)
