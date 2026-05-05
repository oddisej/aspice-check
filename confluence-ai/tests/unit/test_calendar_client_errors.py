"""Unit tests for CalendarClient error mapping.

Verifies that HTTP status codes from the calendar REST API are correctly
translated to the project's custom exception hierarchy.

Requirements: 1.3, 1.4, 2.5, 7.1, 7.2
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from confluence_ai.calendar_client import CalendarClient
from confluence_ai.exceptions import (
    AuthenticationError,
    CalendarAPIError,
    CalendarNotFoundError,
    ConfluenceConnectionError,
)
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


def _make_response(status_code: int, json_data=None, text=""):
    """Create a mock Response object with the given status code."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


class TestListSubcalendarsErrors:
    """Error mapping for list_subcalendars endpoint."""

    def test_401_raises_authentication_error(self, client):
        client._session.get.return_value = _make_response(401)

        with pytest.raises(AuthenticationError) as exc_info:
            client.list_subcalendars("parent-1", "ENG")

        assert exc_info.value.status_code == 401

    def test_403_raises_calendar_not_found_error(self, client):
        client._session.get.return_value = _make_response(403)

        with pytest.raises(CalendarNotFoundError) as exc_info:
            client.list_subcalendars("parent-secret", "SECRET")

        assert exc_info.value.calendar_id == "parent-secret"
        assert exc_info.value.status_code == 403

    def test_404_raises_calendar_not_found_error(self, client):
        client._session.get.return_value = _make_response(404)

        with pytest.raises(CalendarNotFoundError) as exc_info:
            client.list_subcalendars("parent-missing", "MISSING")

        assert exc_info.value.calendar_id == "parent-missing"
        assert exc_info.value.status_code == 404

    def test_500_raises_calendar_api_error(self, client):
        client._session.get.return_value = _make_response(500)

        with pytest.raises(CalendarAPIError) as exc_info:
            client.list_subcalendars("parent-1", "ENG")

        assert exc_info.value.status_code == 500
        assert "calendar" in exc_info.value.endpoint.lower()

    def test_connection_error_raises_confluence_connection_error(self, client):
        from requests.exceptions import ConnectionError as ReqConnError

        client._session.get.side_effect = ReqConnError("unreachable")

        with pytest.raises(ConfluenceConnectionError):
            client.list_subcalendars("parent-1", "ENG")


class TestGetEventsErrors:
    """Error mapping for get_events endpoint."""

    @pytest.fixture
    def date_range(self):
        return DateRange(
            start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 4, 1, tzinfo=timezone.utc),
        )

    def test_401_raises_authentication_error(self, client, date_range):
        client._session.get.return_value = _make_response(401)

        with pytest.raises(AuthenticationError) as exc_info:
            client.get_events("cal-123", date_range)

        assert exc_info.value.status_code == 401

    def test_403_raises_calendar_not_found_error(self, client, date_range):
        client._session.get.return_value = _make_response(403)

        with pytest.raises(CalendarNotFoundError) as exc_info:
            client.get_events("cal-secret", date_range)

        assert exc_info.value.calendar_id == "cal-secret"
        assert exc_info.value.status_code == 403

    def test_404_raises_calendar_not_found_error(self, client, date_range):
        client._session.get.return_value = _make_response(404)

        with pytest.raises(CalendarNotFoundError) as exc_info:
            client.get_events("cal-missing", date_range)

        assert exc_info.value.calendar_id == "cal-missing"
        assert exc_info.value.status_code == 404

    def test_500_raises_calendar_api_error(self, client, date_range):
        client._session.get.return_value = _make_response(500)

        with pytest.raises(CalendarAPIError) as exc_info:
            client.get_events("cal-123", date_range)

        assert exc_info.value.status_code == 500
        assert "events" in exc_info.value.endpoint.lower()

    def test_500_with_bad_start_datetime_raises_calendar_api_error_with_hint(
        self, client, date_range
    ):
        client._session.get.return_value = _make_response(
            500, text="BAD_START_DATETIME"
        )

        with pytest.raises(CalendarAPIError) as exc_info:
            client.get_events("cal-123", date_range)

        assert exc_info.value.status_code == 500
        assert "ISO 8601 timestamps" in str(exc_info.value)

    def test_connection_error_raises_confluence_connection_error(
        self, client, date_range
    ):
        from requests.exceptions import ConnectionError as ReqConnError

        client._session.get.side_effect = ReqConnError("unreachable")

        with pytest.raises(ConfluenceConnectionError):
            client.get_events("cal-123", date_range)
