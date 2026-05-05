"""Feature: confluence-calendar-export, Property 9: export_calendar result invariants."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.calendar_export import export_calendar
from confluence_ai.models import DateRange, Event


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_tz_aware_dt_st = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)


def st_event() -> st.SearchStrategy[Event]:
    """Generate a valid Event instance."""
    return st.builds(
        _build_event,
        event_id=st.text(min_size=1, max_size=10, alphabet="abcdef0123456789"),
        summary=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N"))),
        start=_tz_aware_dt_st,
        duration_hours=st.integers(min_value=1, max_value=24),
        all_day=st.booleans(),
    )


def _build_event(
    event_id: str, summary: str, start: datetime, duration_hours: int, all_day: bool
) -> Event:
    return Event(
        event_id=event_id,
        summary=summary,
        start=start,
        end=start + timedelta(hours=duration_hours),
        all_day=all_day,
        sub_calendar_name="TestCal",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty09ExportResult:
    """Property 9: export_calendar result invariants."""

    @given(events=st.lists(st_event(), min_size=0, max_size=10))
    @settings(max_examples=100)
    def test_json_export_result_invariants(self, events: list[Event]) -> None:
        """JSON export: file exists, event_count matches, warnings is list, file parses.

        **Validates: Requirements 5.3, 6.6**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Patch CalendarClient to return our events
            with patch("confluence_ai.calendar_export.CalendarClient") as mock_client_cls:
                mock_client = MagicMock()
                mock_client.get_events.return_value = events
                mock_client_cls.return_value = mock_client

                date_range = DateRange(
                    start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    end=datetime(2024, 6, 1, tzinfo=timezone.utc),
                )

                result = export_calendar(
                    base_url="https://test.atlassian.net/wiki",
                    calendar_id="cal-123",
                    output_dir=tmp_dir,
                    email="test@example.com",
                    api_token="token123",
                    output_format="json",
                    date_range=date_range,
                )

            # Invariants
            assert os.path.exists(result.output_path)
            assert result.event_count == len(events)
            assert isinstance(result.warnings, list)

            # File parses as valid JSON
            with open(result.output_path, "r", encoding="utf-8") as f:
                parsed = json.loads(f.read())
            assert "metadata" in parsed
            assert "events" in parsed
            assert len(parsed["events"]) == len(events)

    @given(events=st.lists(st_event(), min_size=0, max_size=10))
    @settings(max_examples=100)
    def test_markdown_export_result_invariants(self, events: list[Event]) -> None:
        """Markdown export: file exists, event_count matches, warnings is list, file has YAML block.

        **Validates: Requirements 5.3, 6.6**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Patch CalendarClient to return our events
            with patch("confluence_ai.calendar_export.CalendarClient") as mock_client_cls:
                mock_client = MagicMock()
                mock_client.get_events.return_value = events
                mock_client_cls.return_value = mock_client

                date_range = DateRange(
                    start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    end=datetime(2024, 6, 1, tzinfo=timezone.utc),
                )

                result = export_calendar(
                    base_url="https://test.atlassian.net/wiki",
                    calendar_id="cal-123",
                    output_dir=tmp_dir,
                    email="test@example.com",
                    api_token="token123",
                    output_format="markdown",
                    date_range=date_range,
                )

            # Invariants
            assert os.path.exists(result.output_path)
            assert result.event_count == len(events)
            assert isinstance(result.warnings, list)

            # File contains YAML front-matter block
            with open(result.output_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert content.startswith("---\n")
            # Find closing ---
            lines = content.split("\n")
            closing_idx = lines.index("---", 1)
            assert closing_idx > 0, "No closing --- found in markdown output"
