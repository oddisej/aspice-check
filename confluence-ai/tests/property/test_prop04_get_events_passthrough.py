"""Feature: confluence-calendar-export, Property 4: get_events passes through the plugin's event list for a child calendar."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.calendar_client import CalendarClient, _normalize_display_name
from confluence_ai.models import DateRange


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_tz_aware_dt_st = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)


def _build_raw_event(
    event_id: str,
    title: str,
    start: datetime,
    duration_hours: int,
) -> dict:
    """Build a minimal raw event dict matching the plugin response shape."""
    end = start + timedelta(hours=max(duration_hours, 1))
    return {
        "id": event_id,
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "allDay": False,
        "description": "",
        "location": "",
        "organizer": {"email": "test@example.com", "displayName": "Test"},
        "subCalendarId": "child-cal-1",
        "subCalendarName": "Child Calendar",
    }


def st_raw_event() -> st.SearchStrategy[dict]:
    """Generate a single raw event dict."""
    return st.builds(
        _build_raw_event,
        event_id=st.text(min_size=1, max_size=20, alphabet="abcdef0123456789-"),
        title=st.text(min_size=1, max_size=50),
        start=_tz_aware_dt_st,
        duration_hours=st.integers(min_value=1, max_value=72),
    )


def st_raw_event_list() -> st.SearchStrategy[list[dict]]:
    """Generate a list of raw event dicts (0 to 10 events)."""
    return st.lists(st_raw_event(), min_size=0, max_size=10)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_client() -> CalendarClient:
    """Create a CalendarClient with mocked Confluence connection."""
    with patch("confluence_ai.calendar_client.Confluence") as mock_confluence, \
         patch("confluence_ai.calendar_client.ConfluenceClient"):
        mock_instance = MagicMock()
        mock_instance._session = MagicMock()
        mock_confluence.return_value = mock_instance
        client = CalendarClient(
            base_url="https://acme.atlassian.net/wiki",
            email="user@acme.com",
            api_token="token123",
        )
    return client


def _make_success_response(json_data: dict) -> MagicMock:
    """Create a mock Response object with 200 status."""
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.return_value = json_data
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty04GetEventsPassthrough:
    """Property 4: get_events passes through the plugin's event list for a child calendar."""

    @given(raw_events=st_raw_event_list())
    @settings(max_examples=100)
    def test_passthrough_count(self, raw_events: list[dict]) -> None:
        """get_events returns exactly len(D) events for a child calendar response.

        **Validates: Requirements 2.1**
        """
        client = _make_client()
        date_range = DateRange(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )

        client._session.get.return_value = _make_success_response(
            {"events": raw_events}
        )

        result = client.get_events("child-cal-1", date_range)

        assert len(result) == len(raw_events)

    @given(raw_events=st_raw_event_list())
    @settings(max_examples=100)
    def test_passthrough_order_preserved(self, raw_events: list[dict]) -> None:
        """get_events preserves the order of events from the plugin response.

        **Validates: Requirements 2.1**
        """
        client = _make_client()
        date_range = DateRange(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )

        client._session.get.return_value = _make_success_response(
            {"events": raw_events}
        )

        result = client.get_events("child-cal-1", date_range)

        for i, event in enumerate(result):
            assert event.event_id == raw_events[i]["id"]
            # Summary is normalized: "Last, First" → "First Last" (see
            # _normalize_display_name in calendar_client.py). For inputs
            # without comma-name format, the title passes through unchanged.
            assert event.summary == _normalize_display_name(raw_events[i]["title"])

    @given(raw_events=st_raw_event_list())
    @settings(max_examples=100)
    def test_passthrough_no_filtering(self, raw_events: list[dict]) -> None:
        """get_events does not filter or deduplicate events from a child calendar.

        **Validates: Requirements 2.1**
        """
        client = _make_client()
        date_range = DateRange(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )

        client._session.get.return_value = _make_success_response(
            {"events": raw_events}
        )

        result = client.get_events("child-cal-1", date_range)

        # All event IDs from input appear in output in same order
        result_ids = [e.event_id for e in result]
        input_ids = [r["id"] for r in raw_events]
        assert result_ids == input_ids
