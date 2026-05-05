"""Confluence Team Calendar REST client.

Wraps the unofficial ``/rest/calendar-services/1.0/`` endpoints to provide
calendar discovery and event retrieval.  Reuses the authenticated
``requests.Session`` from ``atlassian-python-api`` so credentials are
managed in one place.

Requirements: 1.1–1.4, 2.1–2.6, 7.1–7.4
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from atlassian import Confluence
from requests.exceptions import ConnectionError as RequestsConnectionError

from confluence_ai.exceptions import (
    AuthenticationError,
    CalendarAPIError,
    CalendarNotFoundError,
    ConfluenceConnectionError,
)
from confluence_ai.models import Calendar, DateRange, Event, SubCalendar

logger = logging.getLogger(__name__)


class CalendarClient:
    """Authenticated client for Confluence Team Calendar discovery and event retrieval."""

    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        """Initialize and authenticate with Confluence Cloud.

        Constructs an internal ``atlassian.Confluence`` object purely to
        reuse its authenticated ``requests.Session`` for calendar REST calls.

        Args:
            base_url: Confluence Cloud base URL
                (e.g., ``https://acme.atlassian.net/wiki``).
            email: User email for Basic Auth.
            api_token: Confluence Cloud API token.

        Raises:
            ConfluenceConnectionError: If the server is unreachable.
        """
        self._base_url = base_url.rstrip("/")
        try:
            self._confluence = Confluence(
                url=base_url,
                username=email,
                password=api_token,
                cloud=True,
            )
        except RequestsConnectionError as exc:
            raise ConfluenceConnectionError(base_url) from exc

        self._session = self._confluence._session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_calendars(self, space_key: str) -> list[Calendar]:
        """List calendars available in a Confluence space.

        Performs ``GET /rest/calendar-services/1.0/calendar?spaceKey={space_key}``.

        Args:
            space_key: The Confluence space key to query.

        Returns:
            List of Calendar instances with nested sub-calendars.

        Raises:
            AuthenticationError: If credentials are invalid (HTTP 401).
            CalendarNotFoundError: If the space is not found or access
                is denied (HTTP 403/404).
            CalendarAPIError: On other non-2xx responses.
            ConfluenceConnectionError: If the server is unreachable.
        """
        url = (
            f"{self._base_url}/rest/calendar-services/1.0/calendar"
            f"?spaceKey={space_key}"
        )
        try:
            response = self._session.get(url)
        except RequestsConnectionError as exc:
            raise ConfluenceConnectionError(self._base_url) from exc

        if not response.ok:
            self._handle_http_error(
                response,
                calendar_id=space_key,
                endpoint=f"/rest/calendar-services/1.0/calendar?spaceKey={space_key}",
            )

        data = response.json()
        # The endpoint returns an array of calendar objects
        if isinstance(data, list):
            return [self._map_calendar(raw) for raw in data]
        return []

    def get_events(
        self,
        calendar_id: str,
        date_range: DateRange,
    ) -> list[Event]:
        """Retrieve events from a calendar within a date range.

        Performs ``GET /rest/calendar-services/1.0/calendar/events.json``
        with ``subCalendarId``, ``start``, and ``end`` query parameters.

        Accepts either a parent calendar ID or a sub-calendar ID — the
        plugin uses the same parameter name for both.

        Args:
            calendar_id: The calendar or sub-calendar ID.
            date_range: Time window for event retrieval.

        Returns:
            Flat list of Event instances (recurring events already expanded).

        Raises:
            AuthenticationError: If credentials are invalid (HTTP 401).
            CalendarNotFoundError: If the calendar is not found or access
                is denied (HTTP 403/404).
            CalendarAPIError: On other non-2xx responses.
            ConfluenceConnectionError: If the server is unreachable.
        """
        start_iso = date_range.start.isoformat()
        end_iso = date_range.end.isoformat()
        url = (
            f"{self._base_url}/rest/calendar-services/1.0/calendar/events.json"
            f"?subCalendarId={calendar_id}&start={start_iso}&end={end_iso}"
        )
        try:
            response = self._session.get(url)
        except RequestsConnectionError as exc:
            raise ConfluenceConnectionError(self._base_url) from exc

        if not response.ok:
            self._handle_http_error(
                response,
                calendar_id=calendar_id,
                endpoint=f"/rest/calendar-services/1.0/calendar/events.json",
            )

        data = response.json()
        events_raw = data.get("events", []) if isinstance(data, dict) else []
        return [self._map_event(raw) for raw in events_raw]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_http_error(
        self,
        response,
        *,
        calendar_id: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        """Translate a non-2xx response into the appropriate custom exception.

        Mapping:
            401 → AuthenticationError
            403 → CalendarNotFoundError (access denied)
            404 → CalendarNotFoundError
            Other → CalendarAPIError
        """
        status = response.status_code

        if status == 401:
            raise AuthenticationError(
                base_url=self._base_url,
                status_code=401,
            )

        if status in (403, 404):
            raise CalendarNotFoundError(
                calendar_id=calendar_id or "",
                status_code=status,
            )

        # All other non-2xx
        raise CalendarAPIError(
            endpoint=endpoint or "",
            status_code=status,
        )

    @staticmethod
    def _map_calendar(raw: dict) -> Calendar:
        """Map a raw plugin calendar response to a ``Calendar`` instance.

        Maps ``subCalendarId`` → ``calendar_id``, preserves ``name``,
        ``type``, ``spaceKey``, ``description``, and recursively maps
        nested ``subCalendars`` to ``SubCalendar`` instances.
        """
        sub_calendars = [
            SubCalendar(
                calendar_id=sc.get("subCalendarId", ""),
                name=sc.get("name", ""),
                type=sc.get("type", ""),
                color=sc.get("color", ""),
                description=sc.get("description", ""),
            )
            for sc in raw.get("subCalendars", [])
        ]

        return Calendar(
            calendar_id=raw.get("subCalendarId", ""),
            name=raw.get("name", ""),
            type=raw.get("type", ""),
            space_key=raw.get("spaceKey", ""),
            description=raw.get("description", ""),
            sub_calendars=sub_calendars,
        )

    @staticmethod
    def _map_event(raw: dict) -> Event:
        """Map a raw plugin event response to an ``Event`` instance.

        Field mapping:
            id → event_id
            title → summary
            allDay → all_day
            organizer.email or .displayName → organizer
            subCalendarId / subCalendarName → sub_calendar_id / sub_calendar_name

        Parses ``start``/``end`` as tz-aware datetime; normalises naive
        timestamps to UTC. Defaults missing string fields to ``""`` and
        missing booleans to ``False``.
        """
        # Parse organizer — prefer email, fall back to displayName
        organizer_raw = raw.get("organizer")
        if isinstance(organizer_raw, dict):
            organizer = (
                organizer_raw.get("email")
                or organizer_raw.get("displayName")
                or ""
            )
        else:
            organizer = ""

        # Parse timestamps
        start = _parse_datetime(raw.get("start", ""))
        end = _parse_datetime(raw.get("end", ""))

        return Event(
            event_id=raw.get("id", ""),
            summary=raw.get("title", ""),
            start=start,
            end=end,
            all_day=bool(raw.get("allDay", False)),
            description=raw.get("description", ""),
            location=raw.get("location", ""),
            organizer=organizer,
            sub_calendar_id=raw.get("subCalendarId", ""),
            sub_calendar_name=raw.get("subCalendarName", ""),
        )


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO 8601 datetime string, normalising naive values to UTC."""
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
