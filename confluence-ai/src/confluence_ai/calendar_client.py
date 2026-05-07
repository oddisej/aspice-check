"""Confluence Team Calendar REST client.

Wraps the unofficial ``/rest/calendar-services/1.0/`` endpoints to provide
page-driven calendar discovery and event retrieval.  Uses the authenticated
``requests.Session`` from ``atlassian-python-api`` for calendar REST calls
and delegates page fetching to ``ConfluenceClient``.

Requirements: 1.1–1.10, 2.1–2.9, 7.1–7.4
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import ClassVar

from atlassian import Confluence
from requests.exceptions import ConnectionError as RequestsConnectionError

from confluence_ai.client import ConfluenceClient
from confluence_ai.exceptions import (
    AuthenticationError,
    CalendarAPIError,
    CalendarNotFoundError,
    ConfluenceConnectionError,
)
from confluence_ai.models import Calendar, DateRange, Event, SubCalendar
from confluence_ai.url_parser import URLParser

logger = logging.getLogger(__name__)


class CalendarClient:
    """Authenticated client for Confluence Team Calendar discovery and event retrieval."""

    _CALENDAR_HEADERS: ClassVar[dict[str, str]] = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    }

    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        """Initialize and authenticate with Confluence Cloud.

        Constructs an internal ``atlassian.Confluence`` object purely to
        reuse its authenticated ``requests.Session`` for calendar REST calls.
        Also constructs a ``ConfluenceClient`` for page fetching and a
        ``URLParser`` for URL parsing.

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
        self._confluence_client = ConfluenceClient(
            base_url=base_url,
            email=email,
            api_token=api_token,
        )
        self._url_parser = URLParser()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_calendars_from_page(self, page_url: str) -> list[Calendar]:
        """Discover calendars referenced by a Confluence page.

        Protocol:
          1. URLParser.parse(page_url) → (base_url, page_id)
          2. ConfluenceClient.get_page(page_id) → PageData (storage body, space_key)
          3. _extract_parent_ids_from_body(storage) → list of parent IDs
          4. For each parent ID: list_subcalendars(parent_id, space_key)
          5. Merge into Calendar objects, sort both levels case-insensitively.

        Args:
            page_url: Full Confluence Cloud page URL containing calendar macros.

        Returns:
            Sorted list of Calendar instances with nested sub-calendars.
            Returns empty list if the page contains no calendar macros.

        Raises:
            InvalidURLError: If the page URL is invalid.
            PageNotFoundError: If the page does not exist.
            AuthenticationError: If credentials are invalid (HTTP 401).
            CalendarAPIError: On subcalendars.json failures.
            ConfluenceConnectionError: If the server is unreachable.
        """
        parsed = self._url_parser.parse(page_url)
        page_data = self._confluence_client.get_page(parsed.page_id)

        parent_ids = _extract_parent_ids_from_body(page_data.storage_format)
        if not parent_ids:
            return []

        calendars: list[Calendar] = []
        for parent_id in parent_ids:
            cal = self.list_subcalendars(parent_id, page_data.space_key)
            calendars.append(cal)

        return _sort_calendars_case_insensitive(calendars)

    def list_subcalendars(self, parent_id: str, space_key: str) -> Calendar:
        """Resolve a parent calendar ID to its full metadata including children.

        Performs ``GET /rest/calendar-services/1.0/calendar/subcalendars.json``
        with ``include={parent_id}``, ``calendarContext=spaceCalendars``,
        and ``viewingSpaceKey={space_key}``.

        Args:
            parent_id: The parent calendar ID to resolve.
            space_key: The Confluence space key for context.

        Returns:
            A Calendar populated from the payload with sub_calendars filled.

        Raises:
            CalendarNotFoundError: If the payload is empty.
            AuthenticationError: If credentials are invalid (HTTP 401).
            CalendarAPIError: On other non-2xx responses.
            ConfluenceConnectionError: If the server is unreachable.
        """
        url = (
            f"{self._base_url}/rest/calendar-services/1.0/calendar/subcalendars.json"
            f"?include={parent_id}"
            f"&calendarContext=spaceCalendars"
            f"&viewingSpaceKey={space_key}"
        )
        try:
            response = self._session.get(url, headers=self._CALENDAR_HEADERS)
        except RequestsConnectionError as exc:
            raise ConfluenceConnectionError(self._base_url) from exc

        if not response.ok:
            self._handle_http_error(
                response,
                calendar_id=parent_id,
                endpoint="/rest/calendar-services/1.0/calendar/subcalendars.json",
            )

        data = response.json()
        payload = data.get("payload", []) if isinstance(data, dict) else []
        calendars = _map_subcalendars_payload(payload)

        if not calendars:
            raise CalendarNotFoundError(
                calendar_id=parent_id,
                message=f"No calendar found for parent ID {parent_id!r}.",
            )

        return calendars[0]

    def get_events(
        self,
        calendar_id: str,
        date_range: DateRange,
        space_key: str = "",
    ) -> list[Event]:
        """Retrieve events from a calendar within a date range.

        Performs ``GET /rest/calendar-services/1.0/calendar/events.json``
        with ``subCalendarId``, ``userTimeZoneId=UTC``, ``start``, and
        ``end`` query parameters.

        Accepts either a parent calendar ID or a sub-calendar ID. If the
        response indicates a parent calendar (no ``events`` key), the
        client auto-resolves to child sub-calendars and aggregates events.

        Args:
            calendar_id: The calendar or sub-calendar ID.
            date_range: Time window for event retrieval.
            space_key: Optional space key for subcalendars resolution.

        Returns:
            Flat list of Event instances (recurring events already expanded).

        Raises:
            AuthenticationError: If credentials are invalid (HTTP 401).
            CalendarNotFoundError: If the calendar is not found or access
                is denied (HTTP 403/404).
            CalendarAPIError: On other non-2xx responses.
            ConfluenceConnectionError: If the server is unreachable.
        """
        start_iso = date_range.start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = date_range.end.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = (
            f"{self._base_url}/rest/calendar-services/1.0/calendar/events.json"
            f"?subCalendarId={calendar_id}"
            f"&userTimeZoneId=UTC"
            f"&start={start_iso}&end={end_iso}"
        )
        try:
            response = self._session.get(url, headers=self._CALENDAR_HEADERS)
        except RequestsConnectionError as exc:
            raise ConfluenceConnectionError(self._base_url) from exc

        if not response.ok:
            self._handle_http_error(
                response,
                calendar_id=calendar_id,
                endpoint="/rest/calendar-services/1.0/calendar/events.json",
            )

        data = response.json()

        # Parent → children auto-resolution
        if _is_parent_response(data):
            parent_cal = self.list_subcalendars(calendar_id, space_key)
            all_events: list[Event] = []
            seen_ids: set[str] = set()
            for child in parent_cal.sub_calendars:
                child_events = self.get_events(
                    child.calendar_id,
                    date_range,
                    space_key=parent_cal.space_key,
                )
                for evt in child_events:
                    if evt.event_id not in seen_ids:
                        seen_ids.add(evt.event_id)
                        all_events.append(evt)
            return all_events

        # Direct child calendar response
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
            500 with BAD_START_DATETIME → CalendarAPIError with hint
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

        if status == 500:
            body = ""
            try:
                body = response.text
            except Exception:
                pass
            if "BAD_START_DATETIME" in body:
                raise CalendarAPIError(
                    endpoint=endpoint or "",
                    status_code=500,
                    message=(
                        "Calendar API error: date range must use full ISO 8601 "
                        "timestamps (YYYY-MM-DDTHH:MM:SSZ), not date-only"
                    ),
                )

        # All other non-2xx
        raise CalendarAPIError(
            endpoint=endpoint or "",
            status_code=status,
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
        # Parse organizer — prefer organizer dict, then first invitee, then empty
        organizer_raw = raw.get("organizer")
        if isinstance(organizer_raw, dict):
            organizer = (
                organizer_raw.get("email")
                or organizer_raw.get("displayName")
                or ""
            )
        elif raw.get("invitees"):
            organizer = raw["invitees"][0].get("displayName", "")
        else:
            organizer = ""

        # Normalize "Last, First" → "First Last"
        organizer = _normalize_display_name(organizer)
        summary = _normalize_display_name(raw.get("title", ""))

        # Parse timestamps
        start = _parse_datetime(raw.get("start", ""))
        end = _parse_datetime(raw.get("end", ""))

        return Event(
            event_id=raw.get("id", ""),
            summary=summary,
            start=start,
            end=end,
            all_day=bool(raw.get("allDay", False)),
            description=raw.get("description", ""),
            location=raw.get("location", ""),
            organizer=organizer,
            sub_calendar_id=raw.get("subCalendarId", ""),
            sub_calendar_name=raw.get("subCalendarName", ""),
        )


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _extract_parent_ids_from_body(storage_body: str) -> list[str]:
    """Extract parent calendar IDs from Confluence storage format body.

    Finds all ``<ac:structured-macro ac:name="calendar">`` elements and
    extracts the ``<ac:parameter ac:name="id">`` value from each.
    Splits comma-separated IDs, strips whitespace, deduplicates while
    preserving order, and skips empty segments.

    Args:
        storage_body: The page's storage format XHTML body.

    Returns:
        Deduplicated list of parent calendar IDs in order of appearance.
        Empty list if no calendar macros are found.
    """
    # Match calendar macros and extract their id parameter
    macro_pattern = re.compile(
        r'<ac:structured-macro[^>]*ac:name="calendar"[^>]*>'
        r'(.*?)'
        r'</ac:structured-macro>',
        re.DOTALL,
    )
    id_param_pattern = re.compile(
        r'<ac:parameter\s+ac:name="id">(.*?)</ac:parameter>',
        re.DOTALL,
    )

    seen: set[str] = set()
    result: list[str] = []

    for macro_match in macro_pattern.finditer(storage_body):
        macro_body = macro_match.group(1)
        id_match = id_param_pattern.search(macro_body)
        if id_match:
            raw_ids = id_match.group(1)
            for segment in raw_ids.split(","):
                cal_id = segment.strip()
                if cal_id and cal_id not in seen:
                    seen.add(cal_id)
                    result.append(cal_id)

    return result


def _map_subcalendars_payload(payload: list[dict]) -> list[Calendar]:
    """Map the subcalendars.json payload to Calendar objects.

    Maps the ``{payload: [{subCalendar: {...}, childSubCalendars: [{subCalendar: {...}}]}]}``
    response shape to a list of ``Calendar`` objects with populated ``sub_calendars``.

    Args:
        payload: The ``payload`` array from the subcalendars.json response.

    Returns:
        List of Calendar instances with nested SubCalendar children.
    """
    calendars: list[Calendar] = []

    for entry in payload:
        parent_raw = entry.get("subCalendar", {})
        children_raw = entry.get("childSubCalendars", [])

        sub_calendars: list[SubCalendar] = []
        for child_entry in children_raw:
            child_raw = child_entry.get("subCalendar", {})
            sub_calendars.append(
                SubCalendar(
                    calendar_id=child_raw.get("id", ""),
                    name=child_raw.get("name", ""),
                    type=child_raw.get("type", ""),
                    color=child_raw.get("color", ""),
                    description=child_raw.get("description", ""),
                    parent_id=child_raw.get("parentId", ""),
                )
            )

        calendars.append(
            Calendar(
                calendar_id=parent_raw.get("id", ""),
                name=parent_raw.get("name", ""),
                type=parent_raw.get("type", ""),
                space_key=parent_raw.get("spaceKey", ""),
                description=parent_raw.get("description", ""),
                sub_calendars=sub_calendars,
            )
        )

    return calendars


def _is_parent_response(data: dict) -> bool:
    """Detect a parent-calendar response from events.json.

    Returns True iff ``data.get("success") is True`` and ``"events" not in data``.
    This indicates the calendar ID is a parent that holds no events directly.
    """
    return data.get("success") is True and "events" not in data


def _sort_calendars_case_insensitive(cals: list[Calendar]) -> list[Calendar]:
    """Sort calendars and their sub-calendars by name (case-insensitive).

    Sorts the top-level list by ``cal.name.casefold()`` and within each
    calendar, sorts ``cal.sub_calendars`` by ``sc.name.casefold()``.

    Args:
        cals: List of Calendar instances to sort.

    Returns:
        Sorted list of Calendar instances.
    """
    for cal in cals:
        cal.sub_calendars.sort(key=lambda sc: sc.name.casefold())
    cals.sort(key=lambda c: c.name.casefold())
    return cals


def _normalize_display_name(name: str) -> str:
    """Normalize a display name from 'Last, First' to 'First Last'.

    If the name contains exactly one comma, assumes 'Last, First' format
    and flips to 'First Last'. Otherwise returns the name unchanged.

    Args:
        name: The raw display name string.

    Returns:
        The normalized name.
    """
    if "," in name:
        parts = name.split(",", 1)
        if len(parts) == 2:
            last = parts[0].strip()
            first = parts[1].strip()
            if first and last:
                return f"{first} {last}"
    return name


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO 8601 datetime string, normalising naive values to UTC.

    Accepts the ``Z`` UTC marker suffix (e.g. ``2025-01-05T09:00:00Z``) by
    converting it to ``+00:00`` — ``datetime.fromisoformat`` only accepts
    ``Z`` natively from Python 3.11 onwards.
    """
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    # Normalize Z suffix to +00:00 for Python 3.10 compatibility
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
