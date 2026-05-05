"""Unit tests for export_calendar() defaults and orchestration.

Tests credential validation, default date range resolution, output format
selection, and result structure.

Requirements: 2.4, 5.1, 5.2, 5.3, 5.4, 5.5
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from confluence_ai.calendar_export import _sanitize_calendar_name, export_calendar
from confluence_ai.exceptions import AuthenticationError
from confluence_ai.models import CalendarExportResult, DateRange, Event


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_event(
    event_id: str = "evt-1",
    summary: str = "Test Event",
    sub_calendar_name: str = "Team Leave",
) -> Event:
    """Create a minimal Event for testing."""
    now = datetime.now(timezone.utc)
    return Event(
        event_id=event_id,
        summary=summary,
        start=now,
        end=now + timedelta(hours=1),
        all_day=False,
        description="A test event",
        location="Room 1",
        organizer="alice@example.com",
        sub_calendar_id="sub-cal-1",
        sub_calendar_name=sub_calendar_name,
    )


# ---------------------------------------------------------------------------
# Credential validation tests
# ---------------------------------------------------------------------------


class TestCredentialValidation:
    """Tests for credential validation in export_calendar."""

    def test_empty_email_raises_authentication_error(self, tmp_path):
        """Empty email raises AuthenticationError with 'email required' message."""
        with pytest.raises(AuthenticationError, match="email required"):
            export_calendar(
                base_url="https://acme.atlassian.net/wiki",
                calendar_id="cal-123",
                output_dir=str(tmp_path),
                email="",
                api_token="valid-token",
            )

    def test_empty_api_token_raises_authentication_error(self, tmp_path):
        """Empty api_token raises AuthenticationError with 'api_token required' message."""
        with pytest.raises(AuthenticationError, match="api_token required"):
            export_calendar(
                base_url="https://acme.atlassian.net/wiki",
                calendar_id="cal-123",
                output_dir=str(tmp_path),
                email="user@example.com",
                api_token="",
            )


# ---------------------------------------------------------------------------
# Default date range tests
# ---------------------------------------------------------------------------


class TestDefaultDateRange:
    """Tests for default date range resolution when date_range=None."""

    def test_default_date_range_resolves_to_now_minus_30_plus_90(
        self, tmp_path, mocker
    ):
        """When date_range=None, resolves to now-30d → now+90d within tolerance."""
        mock_events = [_make_event()]

        # Mock CalendarClient so no real HTTP is attempted
        mock_client_cls = mocker.patch(
            "confluence_ai.calendar_export.CalendarClient"
        )
        mock_client_instance = MagicMock()
        mock_client_instance.get_events.return_value = mock_events
        mock_client_cls.return_value = mock_client_instance

        before = datetime.now(timezone.utc)

        export_calendar(
            base_url="https://acme.atlassian.net/wiki",
            calendar_id="cal-123",
            output_dir=str(tmp_path),
            email="user@example.com",
            api_token="token-123",
            date_range=None,
        )

        after = datetime.now(timezone.utc)

        # Extract the DateRange passed to get_events
        call_args = mock_client_instance.get_events.call_args
        actual_range: DateRange = call_args[0][1]

        # Verify start is approximately now - 30 days (within 5 seconds tolerance)
        expected_start_min = before - timedelta(days=30)
        expected_start_max = after - timedelta(days=30)
        assert expected_start_min <= actual_range.start <= expected_start_max

        # Verify end is approximately now + 90 days (within 5 seconds tolerance)
        expected_end_min = before + timedelta(days=90)
        expected_end_max = after + timedelta(days=90)
        assert expected_end_min <= actual_range.end <= expected_end_max


# ---------------------------------------------------------------------------
# Result structure tests
# ---------------------------------------------------------------------------


class TestExportResult:
    """Tests for CalendarExportResult structure and file output."""

    def test_returns_calendar_export_result_with_existing_file(
        self, tmp_path, mocker
    ):
        """export_calendar returns a CalendarExportResult with valid output_path."""
        mock_events = [_make_event(), _make_event(event_id="evt-2")]

        mock_client_cls = mocker.patch(
            "confluence_ai.calendar_export.CalendarClient"
        )
        mock_client_instance = MagicMock()
        mock_client_instance.get_events.return_value = mock_events
        mock_client_cls.return_value = mock_client_instance

        result = export_calendar(
            base_url="https://acme.atlassian.net/wiki",
            calendar_id="cal-123",
            output_dir=str(tmp_path),
            email="user@example.com",
            api_token="token-123",
        )

        assert isinstance(result, CalendarExportResult)
        assert os.path.exists(result.output_path)
        assert result.event_count == len(mock_events)
        assert isinstance(result.warnings, list)

    def test_json_format_writes_json_file(self, tmp_path, mocker):
        """output_format='json' writes a .json file."""
        mock_events = [_make_event()]

        mock_client_cls = mocker.patch(
            "confluence_ai.calendar_export.CalendarClient"
        )
        mock_client_instance = MagicMock()
        mock_client_instance.get_events.return_value = mock_events
        mock_client_cls.return_value = mock_client_instance

        result = export_calendar(
            base_url="https://acme.atlassian.net/wiki",
            calendar_id="cal-123",
            output_dir=str(tmp_path),
            email="user@example.com",
            api_token="token-123",
            output_format="json",
        )

        assert result.output_path.endswith(".json")
        assert os.path.exists(result.output_path)

    def test_markdown_format_writes_md_file(self, tmp_path, mocker):
        """output_format='markdown' writes a .md file."""
        mock_events = [_make_event()]

        mock_client_cls = mocker.patch(
            "confluence_ai.calendar_export.CalendarClient"
        )
        mock_client_instance = MagicMock()
        mock_client_instance.get_events.return_value = mock_events
        mock_client_cls.return_value = mock_client_instance

        result = export_calendar(
            base_url="https://acme.atlassian.net/wiki",
            calendar_id="cal-123",
            output_dir=str(tmp_path),
            email="user@example.com",
            api_token="token-123",
            output_format="markdown",
        )

        assert result.output_path.endswith(".md")
        assert os.path.exists(result.output_path)

    def test_invalid_format_raises_value_error(self, tmp_path, mocker):
        """Unknown output_format raises ValueError listing valid formats."""
        mock_client_cls = mocker.patch(
            "confluence_ai.calendar_export.CalendarClient"
        )
        mock_client_instance = MagicMock()
        mock_client_instance.get_events.return_value = [_make_event()]
        mock_client_cls.return_value = mock_client_instance

        with pytest.raises(ValueError, match="Unknown output_format"):
            export_calendar(
                base_url="https://acme.atlassian.net/wiki",
                calendar_id="cal-123",
                output_dir=str(tmp_path),
                email="user@example.com",
                api_token="token-123",
                output_format="ical",
            )

    def test_creates_output_directory_if_not_exists(self, tmp_path, mocker):
        """export_calendar creates the output directory if it doesn't exist."""
        mock_events = [_make_event()]

        mock_client_cls = mocker.patch(
            "confluence_ai.calendar_export.CalendarClient"
        )
        mock_client_instance = MagicMock()
        mock_client_instance.get_events.return_value = mock_events
        mock_client_cls.return_value = mock_client_instance

        nested_dir = str(tmp_path / "nested" / "output")
        result = export_calendar(
            base_url="https://acme.atlassian.net/wiki",
            calendar_id="cal-123",
            output_dir=nested_dir,
            email="user@example.com",
            api_token="token-123",
        )

        assert os.path.exists(nested_dir)
        assert os.path.exists(result.output_path)


# ---------------------------------------------------------------------------
# Sanitize calendar name tests
# ---------------------------------------------------------------------------


class TestSanitizeCalendarName:
    """Tests for _sanitize_calendar_name helper."""

    def test_replaces_spaces_with_underscores(self):
        assert _sanitize_calendar_name("Team Leave") == "Team_Leave"

    def test_strips_special_characters(self):
        assert _sanitize_calendar_name("My Cal!@#$%") == "My_Cal"

    def test_preserves_allowed_characters(self):
        assert _sanitize_calendar_name("cal-123_test") == "cal-123_test"

    def test_falls_back_to_calendar_on_empty_result(self):
        assert _sanitize_calendar_name("!!!") == "calendar"
        assert _sanitize_calendar_name("") == "calendar"

    def test_handles_unicode_characters(self):
        # Unicode chars are stripped; only ASCII alphanumeric, _, - remain
        result = _sanitize_calendar_name("日本語カレンダー")
        assert result == "calendar"
