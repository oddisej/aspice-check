"""Smoke tests for the confluence_ai public API surface.

Validates that all calendar-related names are importable and present in __all__,
and that no existing public names were removed.
"""

from __future__ import annotations

import confluence_ai


class TestCalendarImports:
    """Assert new calendar names are importable from the top-level package."""

    def test_import_export_calendar(self) -> None:
        from confluence_ai import export_calendar

        assert callable(export_calendar)

    def test_import_calendar_models(self) -> None:
        from confluence_ai import (
            Calendar,
            CalendarExportResult,
            CalendarMetadata,
            DateRange,
            Event,
            SubCalendar,
        )

        # Verify they are the expected dataclass types
        assert Calendar is not None
        assert SubCalendar is not None
        assert Event is not None
        assert DateRange is not None
        assert CalendarMetadata is not None
        assert CalendarExportResult is not None

    def test_import_calendar_exceptions(self) -> None:
        from confluence_ai import CalendarAPIError, CalendarNotFoundError

        assert issubclass(CalendarNotFoundError, Exception)
        assert issubclass(CalendarAPIError, Exception)


class TestAllContainsNewNames:
    """Assert each new calendar name is present in confluence_ai.__all__."""

    def test_export_calendar_in_all(self) -> None:
        assert "export_calendar" in confluence_ai.__all__

    def test_calendar_in_all(self) -> None:
        assert "Calendar" in confluence_ai.__all__

    def test_sub_calendar_in_all(self) -> None:
        assert "SubCalendar" in confluence_ai.__all__

    def test_event_in_all(self) -> None:
        assert "Event" in confluence_ai.__all__

    def test_date_range_in_all(self) -> None:
        assert "DateRange" in confluence_ai.__all__

    def test_calendar_metadata_in_all(self) -> None:
        assert "CalendarMetadata" in confluence_ai.__all__

    def test_calendar_export_result_in_all(self) -> None:
        assert "CalendarExportResult" in confluence_ai.__all__

    def test_calendar_not_found_error_in_all(self) -> None:
        assert "CalendarNotFoundError" in confluence_ai.__all__

    def test_calendar_api_error_in_all(self) -> None:
        assert "CalendarAPIError" in confluence_ai.__all__


class TestExistingNamesPreserved:
    """Spot-check that existing public names were not removed."""

    def test_export_page_in_all(self) -> None:
        assert "export_page" in confluence_ai.__all__

    def test_publish_page_in_all(self) -> None:
        assert "publish_page" in confluence_ai.__all__

    def test_export_result_in_all(self) -> None:
        assert "ExportResult" in confluence_ai.__all__

    def test_page_metadata_in_all(self) -> None:
        assert "PageMetadata" in confluence_ai.__all__

    def test_export_page_importable(self) -> None:
        from confluence_ai import export_page

        assert callable(export_page)

    def test_publish_page_importable(self) -> None:
        from confluence_ai import publish_page

        assert callable(publish_page)

    def test_export_result_importable(self) -> None:
        from confluence_ai import ExportResult

        assert ExportResult is not None

    def test_page_metadata_importable(self) -> None:
        from confluence_ai import PageMetadata

        assert PageMetadata is not None
