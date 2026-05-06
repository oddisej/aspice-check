"""Feature: calendar-subcalendar-grouping, Property 13: Grouped export resolves parent calendar name for unified output."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.calendar_export import _sanitize_calendar_name, export_calendar_grouped
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
def st_multi_subcalendar_events(draw: st.DrawFn) -> list[Event]:
    """Generate events from at least 2 distinct subcalendars."""
    # Generate events from subcalendar A
    events_a = draw(st.lists(st_event("sub-a", "SubCal A"), min_size=1, max_size=4))
    # Generate events from subcalendar B
    events_b = draw(st.lists(st_event("sub-b", "SubCal B"), min_size=1, max_size=4))
    return events_a + events_b


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty13GroupedNameResolution:
    """Property 13: Grouped export resolves parent calendar name for unified output."""

    @given(
        parent_name=_calendar_name_st,
        calendar_id=_calendar_id_st,
        events=st_multi_subcalendar_events(),
    )
    @settings(max_examples=50)
    def test_grouped_export_uses_parent_calendar_name(
        self,
        parent_name: str,
        calendar_id: str,
        events: list[Event],
    ) -> None:
        """When list_subcalendars resolves a parent name, the JSON metadata
        calendar_name equals that parent name and the output filename stem
        equals _sanitize_calendar_name(parent_name).

        **Validates: Requirements 1.1, 1.2, 4.1**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Build the Calendar object that list_subcalendars returns
            parent_calendar = Calendar(
                calendar_id=calendar_id,
                name=parent_name,
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

            # Parse the JSON output
            assert os.path.exists(result.output_path)
            with open(result.output_path, "r", encoding="utf-8") as f:
                parsed = json.loads(f.read())

            # Assert: metadata calendar_name equals the parent name
            assert parsed["metadata"]["calendar_name"] == parent_name

            # Assert: output filename stem equals _sanitize_calendar_name(parent_name)
            expected_stem = _sanitize_calendar_name(parent_name)
            actual_stem = os.path.splitext(os.path.basename(result.output_path))[0]
            assert actual_stem == expected_stem
