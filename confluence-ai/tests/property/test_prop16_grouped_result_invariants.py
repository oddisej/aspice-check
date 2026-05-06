"""Feature: calendar-subcalendar-grouping, Property 16: Grouped export result invariants match export_calendar invariants."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.calendar_export import export_calendar_grouped
from confluence_ai.models import Calendar, DateRange, Event, SubCalendar


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_tz_aware_dt_st = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)

# Non-empty printable calendar names
_calendar_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=40,
).filter(lambda s: s.strip() != "")

# Alphanumeric calendar IDs
_calendar_id_st = st.text(
    alphabet="abcdef0123456789",
    min_size=4,
    max_size=16,
)


def _build_event(
    event_id: str,
    summary: str,
    start: datetime,
    duration_hours: int,
    sub_calendar_id: str,
    sub_calendar_name: str,
) -> Event:
    """Build a valid Event instance with subcalendar provenance."""
    return Event(
        event_id=event_id,
        summary=summary,
        start=start,
        end=start + timedelta(hours=max(duration_hours, 1)),
        all_day=False,
        sub_calendar_id=sub_calendar_id,
        sub_calendar_name=sub_calendar_name,
    )


def st_event(sub_cal_id: str = "sub-1", sub_cal_name: str = "SubCal A") -> st.SearchStrategy[Event]:
    """Generate a valid Event with a fixed subcalendar identity."""
    return st.builds(
        _build_event,
        event_id=st.text(min_size=1, max_size=12, alphabet="abcdef0123456789"),
        summary=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
        start=_tz_aware_dt_st,
        duration_hours=st.integers(min_value=1, max_value=24),
        sub_calendar_id=st.just(sub_cal_id),
        sub_calendar_name=st.just(sub_cal_name),
    )


@st.composite
def st_event_list(draw: st.DrawFn) -> list[Event]:
    """Generate a list of 1-10 events from one or two subcalendars."""
    # Decide whether to use one or two subcalendars
    use_two = draw(st.booleans())
    if use_two:
        events_a = draw(st.lists(st_event("sub-a", "SubCal A"), min_size=1, max_size=5))
        events_b = draw(st.lists(st_event("sub-b", "SubCal B"), min_size=1, max_size=5))
        return events_a + events_b
    else:
        return draw(st.lists(st_event("sub-a", "SubCal A"), min_size=1, max_size=10))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty16GroupedResultInvariants:
    """Property 16: Grouped export result invariants match export_calendar invariants."""

    @given(
        calendar_name=_calendar_name_st,
        calendar_id=_calendar_id_st,
        events=st_event_list(),
    )
    @settings(max_examples=50)
    def test_grouped_export_json_result_invariants(
        self,
        calendar_name: str,
        calendar_id: str,
        events: list[Event],
    ) -> None:
        """For any generated event list and calendar name, calling
        export_calendar_grouped with format="json" produces a result where:
        (a) output_path exists, (b) event_count == len(events),
        (c) warnings is a list, (d) file is non-empty and parseable as JSON.

        **Validates: Requirements 5.3, 5.6**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            parent_calendar = Calendar(
                calendar_id=calendar_id,
                name=calendar_name,
                type="custom",
                space_key="ENG",
                sub_calendars=[
                    SubCalendar(
                        calendar_id="sub-a",
                        name="SubCal A",
                        type="custom",
                        parent_id=calendar_id,
                    ),
                    SubCalendar(
                        calendar_id="sub-b",
                        name="SubCal B",
                        type="custom",
                        parent_id=calendar_id,
                    ),
                ],
            )

            with patch("confluence_ai.calendar_export.CalendarClient") as mock_client_cls:
                mock_client = MagicMock()
                mock_client.get_events.return_value = events
                mock_client.list_subcalendars.return_value = parent_calendar
                mock_client_cls.return_value = mock_client

                date_range = DateRange(
                    start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    end=datetime(2024, 12, 31, tzinfo=timezone.utc),
                )

                result = export_calendar_grouped(
                    base_url="https://test.atlassian.net/wiki",
                    calendar_id=calendar_id,
                    output_dir=tmp_dir,
                    email="user@example.com",
                    api_token="token123",
                    output_format="json",
                    date_range=date_range,
                )

            # (a) output_path exists
            assert os.path.exists(result.output_path)

            # (b) event_count == len(events)
            assert result.event_count == len(events)

            # (c) warnings is a list
            assert isinstance(result.warnings, list)

            # (d) file is non-empty and parseable as JSON
            with open(result.output_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert len(content) > 0
            parsed = json.loads(content)  # Should not raise
            assert isinstance(parsed, dict)

    @given(
        calendar_name=_calendar_name_st,
        calendar_id=_calendar_id_st,
        events=st_event_list(),
    )
    @settings(max_examples=50)
    def test_grouped_export_markdown_result_invariants(
        self,
        calendar_name: str,
        calendar_id: str,
        events: list[Event],
    ) -> None:
        """For any generated event list and calendar name, calling
        export_calendar_grouped with format="markdown" produces a result where:
        (a) output_path exists, (b) event_count == len(events),
        (c) warnings is a list, (d) file is non-empty and starts with '---'.

        **Validates: Requirements 5.3, 5.6**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            parent_calendar = Calendar(
                calendar_id=calendar_id,
                name=calendar_name,
                type="custom",
                space_key="ENG",
                sub_calendars=[
                    SubCalendar(
                        calendar_id="sub-a",
                        name="SubCal A",
                        type="custom",
                        parent_id=calendar_id,
                    ),
                    SubCalendar(
                        calendar_id="sub-b",
                        name="SubCal B",
                        type="custom",
                        parent_id=calendar_id,
                    ),
                ],
            )

            with patch("confluence_ai.calendar_export.CalendarClient") as mock_client_cls:
                mock_client = MagicMock()
                mock_client.get_events.return_value = events
                mock_client.list_subcalendars.return_value = parent_calendar
                mock_client_cls.return_value = mock_client

                date_range = DateRange(
                    start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    end=datetime(2024, 12, 31, tzinfo=timezone.utc),
                )

                result = export_calendar_grouped(
                    base_url="https://test.atlassian.net/wiki",
                    calendar_id=calendar_id,
                    output_dir=tmp_dir,
                    email="user@example.com",
                    api_token="token123",
                    output_format="markdown",
                    date_range=date_range,
                )

            # (a) output_path exists
            assert os.path.exists(result.output_path)

            # (b) event_count == len(events)
            assert result.event_count == len(events)

            # (c) warnings is a list
            assert isinstance(result.warnings, list)

            # (d) file is non-empty and starts with '---' (YAML front-matter)
            with open(result.output_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert len(content) > 0
            assert content.startswith("---"), (
                f"Markdown output should start with '---' (YAML front-matter), "
                f"but starts with: {content[:20]!r}"
            )
