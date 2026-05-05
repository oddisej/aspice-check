"""Unit tests for CalendarNotFoundError and CalendarAPIError."""

from __future__ import annotations

from confluence_ai.exceptions import (
    CalendarAPIError,
    CalendarNotFoundError,
    ExporterError,
)


class TestCalendarNotFoundError:
    """Tests for CalendarNotFoundError."""

    def test_subclasses_exporter_error(self) -> None:
        exc = CalendarNotFoundError(calendar_id="cal-123")
        assert isinstance(exc, ExporterError)

    def test_exposes_calendar_id_attribute(self) -> None:
        exc = CalendarNotFoundError(calendar_id="cal-abc", status_code=404)
        assert exc.calendar_id == "cal-abc"

    def test_exposes_status_code_attribute(self) -> None:
        exc = CalendarNotFoundError(calendar_id="cal-abc", status_code=404)
        assert exc.status_code == 404

    def test_status_code_none_by_default(self) -> None:
        exc = CalendarNotFoundError(calendar_id="cal-xyz")
        assert exc.status_code is None

    def test_http_403_message_mentions_access_denied(self) -> None:
        exc = CalendarNotFoundError(calendar_id="my-cal", status_code=403)
        msg = str(exc)
        assert "Access denied" in msg
        assert "'my-cal'" in msg
        assert "HTTP 403" in msg

    def test_non_403_message_mentions_not_found(self) -> None:
        exc = CalendarNotFoundError(calendar_id="cal-99", status_code=404)
        msg = str(exc)
        assert "not found" in msg
        assert "'cal-99'" in msg
        assert "HTTP 404" in msg

    def test_custom_message_overrides_default(self) -> None:
        exc = CalendarNotFoundError(
            calendar_id="cal-1", status_code=403, message="Custom error"
        )
        assert str(exc) == "Custom error"


class TestCalendarAPIError:
    """Tests for CalendarAPIError."""

    def test_subclasses_exporter_error(self) -> None:
        exc = CalendarAPIError(endpoint="/rest/calendar-services/1.0/calendar")
        assert isinstance(exc, ExporterError)

    def test_exposes_endpoint_attribute(self) -> None:
        exc = CalendarAPIError(endpoint="/api/endpoint", status_code=500)
        assert exc.endpoint == "/api/endpoint"

    def test_exposes_status_code_attribute(self) -> None:
        exc = CalendarAPIError(endpoint="/api/endpoint", status_code=502)
        assert exc.status_code == 502

    def test_status_code_none_by_default(self) -> None:
        exc = CalendarAPIError(endpoint="/api/endpoint")
        assert exc.status_code is None

    def test_default_message_includes_endpoint_and_status(self) -> None:
        exc = CalendarAPIError(endpoint="/rest/cal", status_code=500)
        msg = str(exc)
        assert "'/rest/cal'" in msg
        assert "HTTP 500" in msg

    def test_custom_message_overrides_default(self) -> None:
        exc = CalendarAPIError(
            endpoint="/rest/cal", status_code=500, message="Server exploded"
        )
        assert str(exc) == "Server exploded"
