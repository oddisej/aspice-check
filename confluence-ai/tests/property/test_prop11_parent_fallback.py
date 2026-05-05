"""Feature: confluence-calendar-export, Property 11: Parent → children fallback triggers on the no-events response and aggregates deduped child events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.calendar_client import CalendarClient
from confluence_ai.models import Calendar, DateRange, SubCalendar


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
        "subCalendarId": "child-cal",
        "subCalendarName": "Child Calendar",
    }


def st_raw_event(prefix: str = "") -> st.SearchStrategy[dict]:
    """Generate a single raw event dict with an optional ID prefix."""
    return st.builds(
        _build_raw_event,
        event_id=st.text(min_size=1, max_size=12, alphabet="abcdef0123456789").map(
            lambda s: f"{prefix}{s}" if prefix else s
        ),
        title=st.text(min_size=1, max_size=30),
        start=_tz_aware_dt_st,
        duration_hours=st.integers(min_value=1, max_value=48),
    )


@st.composite
def st_parent_with_children(draw: st.DrawFn) -> tuple[str, list[SubCalendar], list[list[dict]]]:
    """Generate a parent ID, K children, and event lists per child.

    Some event_ids may overlap across children to test deduplication.
    """
    parent_id = draw(st.text(min_size=4, max_size=12, alphabet="abcdef0123456789"))
    num_children = draw(st.integers(min_value=1, max_value=4))

    children: list[SubCalendar] = []
    event_lists: list[list[dict]] = []

    # Build a shared pool of event IDs that may appear in multiple children
    shared_pool_size = draw(st.integers(min_value=0, max_value=3))
    shared_events: list[dict] = draw(
        st.lists(st_raw_event(prefix="shared-"), min_size=shared_pool_size, max_size=shared_pool_size)
    )

    for i in range(num_children):
        child_id = f"{parent_id}-child-{i}"
        children.append(
            SubCalendar(
                calendar_id=child_id,
                name=f"Child {i}",
                type="custom",
                parent_id=parent_id,
            )
        )
        # Each child gets its own unique events plus possibly some shared ones
        unique_events = draw(
            st.lists(st_raw_event(prefix=f"c{i}-"), min_size=0, max_size=4)
        )
        # Randomly include some shared events in this child
        included_shared = draw(
            st.lists(
                st.sampled_from(shared_events) if shared_events else st.nothing(),
                min_size=0,
                max_size=len(shared_events),
            )
        ) if shared_events else []
        event_lists.append(unique_events + included_shared)

    return parent_id, children, event_lists


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


class TestProperty11ParentFallback:
    """Property 11: Parent → children fallback triggers on the no-events response and aggregates deduped child events."""

    @given(data=st_parent_with_children())
    @settings(max_examples=100)
    def test_parent_triggers_fallback_and_deduplicates(
        self,
        data: tuple[str, list[SubCalendar], list[list[dict]]],
    ) -> None:
        """When get_events receives {"success": true} (no events key), it resolves
        children via list_subcalendars and aggregates deduped events.

        **Validates: Requirements 2.2, 2.3, 5.6**
        """
        parent_id, children, event_lists = data
        client = _make_client()
        date_range = DateRange(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )

        # Build the Calendar object that list_subcalendars would return
        parent_calendar = Calendar(
            calendar_id=parent_id,
            name="Parent Calendar",
            type="custom",
            space_key="ENG",
            sub_calendars=children,
        )

        # Build response sequence: first call returns parent response,
        # subsequent calls return child events
        responses = [_make_success_response({"success": True})]
        for events in event_lists:
            responses.append(_make_success_response({"events": events}))

        client._session.get.side_effect = responses

        # Mock list_subcalendars to return the parent calendar with children
        with patch.object(client, "list_subcalendars", return_value=parent_calendar):
            result = client.get_events(parent_id, date_range)

        # Compute expected: union of all events, deduplicated by event_id (first wins)
        seen_ids: set[str] = set()
        expected_ids: list[str] = []
        for events in event_lists:
            for evt in events:
                eid = evt["id"]
                if eid not in seen_ids:
                    seen_ids.add(eid)
                    expected_ids.append(eid)

        result_ids = [e.event_id for e in result]
        assert result_ids == expected_ids

    @given(
        raw_events=st.lists(st_raw_event(), min_size=0, max_size=8),
    )
    @settings(max_examples=100)
    def test_events_key_present_does_not_trigger_fallback(
        self,
        raw_events: list[dict],
    ) -> None:
        """When response has an "events" key (even empty list), no fallback is triggered.

        **Validates: Requirements 2.2, 2.3, 5.6**
        """
        client = _make_client()
        date_range = DateRange(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )

        # Response with "events" key — should NOT trigger fallback
        client._session.get.return_value = _make_success_response(
            {"events": raw_events}
        )

        # Mock list_subcalendars — should NOT be called
        with patch.object(client, "list_subcalendars") as mock_list_sub:
            result = client.get_events("some-child-id", date_range)

        # Verify no fallback was triggered
        mock_list_sub.assert_not_called()

        # Verify events are returned directly
        assert len(result) == len(raw_events)
        result_ids = [e.event_id for e in result]
        input_ids = [r["id"] for r in raw_events]
        assert result_ids == input_ids
