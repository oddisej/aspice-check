"""Feature: confluence-calendar-export, Property 12: Every calendar REST request carries the required headers and parameters."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.calendar_client import CalendarClient
from confluence_ai.models import DateRange


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Calendar IDs and space keys: alphanumeric with dashes
_id_alphabet = "abcdefghijklmnopqrstuvwxyz0123456789-"

st_calendar_id = st.text(min_size=3, max_size=20, alphabet=_id_alphabet)
st_space_key = st.text(
    min_size=2, max_size=8, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"
)


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


def _assert_mandatory_headers(call_args) -> None:
    """Assert that the mandatory calendar headers are present in the call."""
    # call_args is the mock's call_args (args, kwargs)
    _, kwargs = call_args
    headers = kwargs.get("headers", {})
    assert headers.get("X-Requested-With") == "XMLHttpRequest", (
        f"Missing or wrong X-Requested-With header: {headers}"
    )
    assert headers.get("Accept") == "application/json, text/javascript, */*; q=0.01", (
        f"Missing or wrong Accept header: {headers}"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty12RequestInvariants:
    """Property 12: Every calendar REST request carries the required headers and parameters."""

    @given(calendar_id=st_calendar_id, space_key=st_space_key)
    @settings(max_examples=100)
    def test_list_subcalendars_sends_mandatory_headers(
        self,
        calendar_id: str,
        space_key: str,
    ) -> None:
        """list_subcalendars sends X-Requested-With and Accept headers.

        **Validates: Requirements 1.8, 2.8, 2.9**
        """
        client = _make_client()

        # Mock response for subcalendars.json
        subcal_response = {
            "success": True,
            "payload": [
                {
                    "subCalendar": {
                        "id": calendar_id,
                        "name": "Test Calendar",
                        "type": "custom",
                        "spaceKey": space_key,
                        "description": "",
                    },
                    "childSubCalendars": [],
                }
            ],
        }
        client._session.get.return_value = _make_success_response(subcal_response)

        client.list_subcalendars(calendar_id, space_key)

        # Verify headers on the request
        assert client._session.get.call_count == 1
        _assert_mandatory_headers(client._session.get.call_args)

    @given(calendar_id=st_calendar_id)
    @settings(max_examples=100)
    def test_get_events_sends_mandatory_headers(
        self,
        calendar_id: str,
    ) -> None:
        """get_events sends X-Requested-With and Accept headers.

        **Validates: Requirements 1.8, 2.8, 2.9**
        """
        client = _make_client()
        date_range = DateRange(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )

        # Mock response for events.json (child calendar response)
        client._session.get.return_value = _make_success_response({"events": []})

        client.get_events(calendar_id, date_range)

        # Verify headers on the request
        assert client._session.get.call_count == 1
        _assert_mandatory_headers(client._session.get.call_args)

    @given(calendar_id=st_calendar_id)
    @settings(max_examples=100)
    def test_get_events_includes_user_timezone_utc(
        self,
        calendar_id: str,
    ) -> None:
        """get_events URL includes userTimeZoneId=UTC query parameter.

        **Validates: Requirements 1.8, 2.8, 2.9**
        """
        client = _make_client()
        date_range = DateRange(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )

        # Mock response for events.json
        client._session.get.return_value = _make_success_response({"events": []})

        client.get_events(calendar_id, date_range)

        # Extract the URL from the call
        call_args = client._session.get.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        assert "userTimeZoneId" in query_params, (
            f"userTimeZoneId not found in URL query: {url}"
        )
        assert query_params["userTimeZoneId"] == ["UTC"], (
            f"userTimeZoneId is not UTC: {query_params['userTimeZoneId']}"
        )

    @given(calendar_id=st_calendar_id, space_key=st_space_key)
    @settings(max_examples=100)
    def test_subcalendars_url_does_not_include_timezone(
        self,
        calendar_id: str,
        space_key: str,
    ) -> None:
        """subcalendars.json URL does NOT include userTimeZoneId (only events.json does).

        **Validates: Requirements 1.8, 2.8, 2.9**
        """
        client = _make_client()

        subcal_response = {
            "success": True,
            "payload": [
                {
                    "subCalendar": {
                        "id": calendar_id,
                        "name": "Test Calendar",
                        "type": "custom",
                        "spaceKey": space_key,
                        "description": "",
                    },
                    "childSubCalendars": [],
                }
            ],
        }
        client._session.get.return_value = _make_success_response(subcal_response)

        client.list_subcalendars(calendar_id, space_key)

        # Extract the URL
        call_args = client._session.get.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")

        # subcalendars.json should NOT have userTimeZoneId
        assert "userTimeZoneId" not in url, (
            f"userTimeZoneId should not be in subcalendars.json URL: {url}"
        )
        # But it should be a subcalendars.json URL
        assert "subcalendars.json" in url
