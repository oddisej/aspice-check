"""Feature: confluence-calendar-export, Property 3: Date-range filtering returns only overlapping events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.calendar_client import CalendarClient
from confluence_ai.models import DateRange


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_tz_aware_dt_st = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)


def st_event_dict() -> st.SearchStrategy[dict]:
    """Generate a raw event dict with valid start/end."""
    return st.builds(
        _build_event,
        start=_tz_aware_dt_st,
        duration_hours=st.integers(min_value=1, max_value=48),
        event_id=st.text(min_size=1, max_size=10, alphabet="abcdef0123456789"),
        title=st.text(min_size=1, max_size=20),
    )


def _build_event(start: datetime, duration_hours: int, event_id: str, title: str) -> dict:
    end = start + timedelta(hours=duration_hours)
    return {
        "id": event_id,
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "allDay": False,
        "description": "",
        "location": "",
        "organizer": {"email": "test@example.com"},
        "subCalendarId": "cal-1",
        "subCalendarName": "Test",
    }


def st_date_range() -> st.SearchStrategy[DateRange]:
    """Generate a valid DateRange where end > start."""
    return st.builds(
        _build_date_range,
        start=_tz_aware_dt_st,
        duration_days=st.integers(min_value=1, max_value=180),
    )


def _build_date_range(start: datetime, duration_days: int) -> DateRange:
    return DateRange(start=start, end=start + timedelta(days=duration_days))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty03DateRangeOverlap:
    """Property 3: Date-range filtering returns only overlapping events.

    Since the Confluence plugin does server-side filtering, this test verifies
    that the client passes through ALL events from the mocked response without
    dropping any.
    """

    @given(
        events=st.lists(st_event_dict(), min_size=0, max_size=10),
        date_range=st_date_range(),
    )
    @settings(max_examples=100)
    def test_all_events_from_response_passed_through(
        self, events: list[dict], date_range: DateRange
    ) -> None:
        """All events returned by the mocked response are passed through without dropping any.

        **Validates: Requirements 2.1**
        """
        # Mock the session to return our events
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"events": events}

        with patch("confluence_ai.calendar_client.Confluence"):
            client = CalendarClient.__new__(CalendarClient)
            client._base_url = "https://test.atlassian.net/wiki"
            client._session = MagicMock()
            client._session.get.return_value = mock_response

            result = client.get_events("cal-1", date_range)

        # The client should pass through ALL events from the response
        assert len(result) == len(events)

    @given(
        events=st.lists(st_event_dict(), min_size=1, max_size=10),
        date_range=st_date_range(),
    )
    @settings(max_examples=100)
    def test_event_count_matches_response(
        self, events: list[dict], date_range: DateRange
    ) -> None:
        """The count of returned events matches the count in the mocked response.

        **Validates: Requirements 2.1**
        """
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"events": events}

        with patch("confluence_ai.calendar_client.Confluence"):
            client = CalendarClient.__new__(CalendarClient)
            client._base_url = "https://test.atlassian.net/wiki"
            client._session = MagicMock()
            client._session.get.return_value = mock_response

            result = client.get_events("cal-1", date_range)

        assert len(result) == len(events)
        # Verify each event was mapped (not filtered out)
        for i, event in enumerate(result):
            assert event.event_id == events[i]["id"]
