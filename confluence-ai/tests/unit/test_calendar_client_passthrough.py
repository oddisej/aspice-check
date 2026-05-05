"""Unit tests for CalendarClient query-string and sub-calendar passthrough.

Verifies that the correct query parameters are passed to the calendar REST
API endpoints and that sub-calendar IDs are accepted as calendar_id.

Requirements: 1.8, 2.1, 2.2, 2.8, 2.9
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from confluence_ai.calendar_client import CalendarClient
from confluence_ai.models import DateRange


@pytest.fixture
def client():
    """Create a CalendarClient with a mocked Confluence connection."""
    with patch("confluence_ai.calendar_client.Confluence") as mock_confluence, \
         patch("confluence_ai.calendar_client.ConfluenceClient"):
        mock_instance = MagicMock()
        mock_instance._session = MagicMock()
        mock_confluence.return_value = mock_instance
        c = CalendarClient(
            base_url="https://acme.atlassian.net/wiki",
            email="user@acme.com",
            api_token="token123",
        )
    return c


def _make_success_response(json_data):
    """Create a mock Response object with 200 status."""
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.return_value = json_data
    return resp


class TestListSubcalendarsQueryString:
    """Verify list_subcalendars passes the correct query parameters."""

    def test_include_param_passed_in_url(self, client):
        payload = {
            "success": True,
            "payload": [
                {
                    "subCalendar": {
                        "id": "parent-1",
                        "name": "Team Calendar",
                        "type": "custom",
                        "spaceKey": "ENG",
                        "description": "",
                    },
                    "childSubCalendars": [],
                }
            ],
        }
        client._session.get.return_value = _make_success_response(payload)

        client.list_subcalendars("parent-1", "ENG")

        called_url = client._session.get.call_args[0][0]
        parsed = urlparse(called_url)
        params = parse_qs(parsed.query)
        assert params["include"] == ["parent-1"]

    def test_viewing_space_key_passed_in_url(self, client):
        payload = {
            "success": True,
            "payload": [
                {
                    "subCalendar": {
                        "id": "parent-1",
                        "name": "Team Calendar",
                        "type": "custom",
                        "spaceKey": "ENGINEERING",
                        "description": "",
                    },
                    "childSubCalendars": [],
                }
            ],
        }
        client._session.get.return_value = _make_success_response(payload)

        client.list_subcalendars("parent-1", "ENGINEERING")

        called_url = client._session.get.call_args[0][0]
        parsed = urlparse(called_url)
        params = parse_qs(parsed.query)
        assert params["viewingSpaceKey"] == ["ENGINEERING"]

    def test_calendar_context_passed_in_url(self, client):
        payload = {
            "success": True,
            "payload": [
                {
                    "subCalendar": {
                        "id": "parent-1",
                        "name": "Team Calendar",
                        "type": "custom",
                        "spaceKey": "ENG",
                        "description": "",
                    },
                    "childSubCalendars": [],
                }
            ],
        }
        client._session.get.return_value = _make_success_response(payload)

        client.list_subcalendars("parent-1", "ENG")

        called_url = client._session.get.call_args[0][0]
        parsed = urlparse(called_url)
        params = parse_qs(parsed.query)
        assert params["calendarContext"] == ["spaceCalendars"]

    def test_correct_endpoint_path(self, client):
        payload = {
            "success": True,
            "payload": [
                {
                    "subCalendar": {
                        "id": "parent-1",
                        "name": "Team Calendar",
                        "type": "custom",
                        "spaceKey": "ENG",
                        "description": "",
                    },
                    "childSubCalendars": [],
                }
            ],
        }
        client._session.get.return_value = _make_success_response(payload)

        client.list_subcalendars("parent-1", "ENG")

        called_url = client._session.get.call_args[0][0]
        parsed = urlparse(called_url)
        assert "/rest/calendar-services/1.0/calendar/subcalendars.json" in parsed.path

    def test_headers_passed_on_request(self, client):
        payload = {
            "success": True,
            "payload": [
                {
                    "subCalendar": {
                        "id": "parent-1",
                        "name": "Team Calendar",
                        "type": "custom",
                        "spaceKey": "ENG",
                        "description": "",
                    },
                    "childSubCalendars": [],
                }
            ],
        }
        client._session.get.return_value = _make_success_response(payload)

        client.list_subcalendars("parent-1", "ENG")

        call_kwargs = client._session.get.call_args[1]
        assert call_kwargs["headers"]["X-Requested-With"] == "XMLHttpRequest"
        assert "application/json" in call_kwargs["headers"]["Accept"]

    def test_maps_subcalendar_response(self, client):
        payload = {
            "success": True,
            "payload": [
                {
                    "subCalendar": {
                        "id": "parent-1",
                        "name": "Team Leave",
                        "type": "custom",
                        "spaceKey": "ENG",
                        "description": "Out of office",
                    },
                    "childSubCalendars": [
                        {
                            "subCalendar": {
                                "id": "child-leaves",
                                "name": "Leaves",
                                "type": "leaves",
                                "parentId": "parent-1",
                                "color": "#ff0000",
                                "description": "Leave calendar",
                            }
                        },
                        {
                            "subCalendar": {
                                "id": "child-travel",
                                "name": "Travel",
                                "type": "travel",
                                "parentId": "parent-1",
                                "color": "#00ff00",
                                "description": "",
                            }
                        },
                    ],
                }
            ],
        }
        client._session.get.return_value = _make_success_response(payload)

        result = client.list_subcalendars("parent-1", "ENG")

        assert result.calendar_id == "parent-1"
        assert result.name == "Team Leave"
        assert result.type == "custom"
        assert result.space_key == "ENG"
        assert result.description == "Out of office"
        assert len(result.sub_calendars) == 2
        assert result.sub_calendars[0].calendar_id == "child-leaves"
        assert result.sub_calendars[0].name == "Leaves"
        assert result.sub_calendars[0].parent_id == "parent-1"
        assert result.sub_calendars[1].calendar_id == "child-travel"
        assert result.sub_calendars[1].name == "Travel"
        assert result.sub_calendars[1].parent_id == "parent-1"


class TestGetEventsQueryString:
    """Verify get_events passes the correct query parameters."""

    @pytest.fixture
    def date_range(self):
        return DateRange(
            start=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end=datetime(2025, 4, 15, 0, 0, 0, tzinfo=timezone.utc),
        )

    def test_calendar_id_passed_as_sub_calendar_id(self, client, date_range):
        client._session.get.return_value = _make_success_response({"events": []})

        client.get_events("abc-123", date_range)

        called_url = client._session.get.call_args[0][0]
        parsed = urlparse(called_url)
        params = parse_qs(parsed.query)
        assert params["subCalendarId"] == ["abc-123"]

    def test_user_time_zone_id_utc_passed(self, client, date_range):
        client._session.get.return_value = _make_success_response({"events": []})

        client.get_events("cal-1", date_range)

        called_url = client._session.get.call_args[0][0]
        parsed = urlparse(called_url)
        params = parse_qs(parsed.query)
        assert params["userTimeZoneId"] == ["UTC"]

    def test_start_and_end_iso_format(self, client, date_range):
        client._session.get.return_value = _make_success_response({"events": []})

        client.get_events("cal-1", date_range)

        called_url = client._session.get.call_args[0][0]
        assert date_range.start.isoformat() in called_url
        assert date_range.end.isoformat() in called_url

    def test_headers_passed_on_request(self, client, date_range):
        client._session.get.return_value = _make_success_response({"events": []})

        client.get_events("cal-1", date_range)

        call_kwargs = client._session.get.call_args[1]
        assert call_kwargs["headers"]["X-Requested-With"] == "XMLHttpRequest"
        assert "application/json" in call_kwargs["headers"]["Accept"]

    def test_sub_calendar_id_accepted_as_calendar_id(self, client, date_range):
        """A sub-calendar ID is accepted as the calendar_id parameter."""
        sub_cal_id = "abc-123-leaves"
        client._session.get.return_value = _make_success_response({"events": []})

        client.get_events(sub_cal_id, date_range)

        called_url = client._session.get.call_args[0][0]
        parsed = urlparse(called_url)
        params = parse_qs(parsed.query)
        assert params["subCalendarId"] == [sub_cal_id]

    def test_correct_endpoint_path(self, client, date_range):
        client._session.get.return_value = _make_success_response({"events": []})

        client.get_events("cal-1", date_range)

        called_url = client._session.get.call_args[0][0]
        parsed = urlparse(called_url)
        assert "/rest/calendar-services/1.0/calendar/events.json" in parsed.path

    def test_maps_event_response(self, client, date_range):
        raw_events = {
            "events": [
                {
                    "id": "evt-001",
                    "title": "Sprint Planning",
                    "start": "2025-01-05T09:00:00.000Z",
                    "end": "2025-01-05T10:30:00.000Z",
                    "allDay": False,
                    "description": "Weekly sprint planning",
                    "location": "Room 3",
                    "organizer": {
                        "displayName": "Alice",
                        "email": "alice@acme.com",
                    },
                    "subCalendarId": "cal-sub-1",
                    "subCalendarName": "Meetings",
                },
                {
                    "id": "evt-002",
                    "title": "Alice out",
                    "start": "2025-01-02T00:00:00.000Z",
                    "end": "2025-01-03T00:00:00.000Z",
                    "allDay": True,
                    "description": "",
                    "location": "",
                    "organizer": {"displayName": "Alice"},
                    "subCalendarId": "cal-sub-leaves",
                    "subCalendarName": "Leaves",
                },
            ]
        }
        client._session.get.return_value = _make_success_response(raw_events)

        result = client.get_events("cal-parent", date_range)

        assert len(result) == 2

        evt1 = result[0]
        assert evt1.event_id == "evt-001"
        assert evt1.summary == "Sprint Planning"
        assert evt1.all_day is False
        assert evt1.organizer == "alice@acme.com"
        assert evt1.sub_calendar_id == "cal-sub-1"
        assert evt1.sub_calendar_name == "Meetings"
        assert evt1.start.tzinfo is not None
        assert evt1.end.tzinfo is not None
        assert evt1.end >= evt1.start

        evt2 = result[1]
        assert evt2.event_id == "evt-002"
        assert evt2.summary == "Alice out"
        assert evt2.all_day is True
        assert evt2.organizer == "Alice"  # falls back to displayName
        assert evt2.start.tzinfo is not None

    def test_event_with_missing_fields_defaults(self, client, date_range):
        """Missing fields default to empty strings or False."""
        raw_events = {
            "events": [
                {
                    "id": "evt-minimal",
                    "title": "Minimal Event",
                    "start": "2025-01-10T14:00:00Z",
                    "end": "2025-01-10T15:00:00Z",
                }
            ]
        }
        client._session.get.return_value = _make_success_response(raw_events)

        result = client.get_events("cal-1", date_range)

        assert len(result) == 1
        evt = result[0]
        assert evt.event_id == "evt-minimal"
        assert evt.summary == "Minimal Event"
        assert evt.all_day is False
        assert evt.description == ""
        assert evt.location == ""
        assert evt.organizer == ""
        assert evt.sub_calendar_id == ""
        assert evt.sub_calendar_name == ""

    def test_naive_datetime_normalized_to_utc(self, client, date_range):
        """Naive timestamps (no timezone) are normalised to UTC."""
        raw_events = {
            "events": [
                {
                    "id": "evt-naive",
                    "title": "Naive Time",
                    "start": "2025-02-01T10:00:00",
                    "end": "2025-02-01T11:00:00",
                }
            ]
        }
        client._session.get.return_value = _make_success_response(raw_events)

        result = client.get_events("cal-1", date_range)

        evt = result[0]
        assert evt.start.tzinfo is not None
        assert evt.end.tzinfo is not None
