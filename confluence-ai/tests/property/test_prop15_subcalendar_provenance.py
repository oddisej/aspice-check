"""Feature: calendar-subcalendar-grouping, Property 15: Markdown subcalendar provenance sub-bullet appears when events come from multiple subcalendars."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.calendar_renderer import CalendarMarkdownRenderer
from confluence_ai.models import CalendarMetadata, DateRange, Event


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_tz_aware_dt_st = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)

# Non-empty printable subcalendar names (no newlines to avoid breaking Markdown lines)
_subcalendar_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"), blacklist_characters="\n\r"),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip() != "")


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
def st_multi_subcalendar_events(draw: st.DrawFn) -> tuple[list[Event], str, str]:
    """Generate events from at least 2 distinct subcalendars.

    Returns (events, name_a, name_b) so the test can verify provenance strings.
    """
    name_a = draw(_subcalendar_name_st)
    name_b = draw(_subcalendar_name_st.filter(lambda s: s != name_a))

    events_a = draw(st.lists(st_event("sub-a", name_a), min_size=1, max_size=4))
    events_b = draw(st.lists(st_event("sub-b", name_b), min_size=1, max_size=4))
    return events_a + events_b, name_a, name_b


@st.composite
def st_single_subcalendar_events(draw: st.DrawFn) -> tuple[list[Event], str]:
    """Generate events all sharing one subcalendar name.

    Returns (events, shared_name).
    """
    shared_name = draw(_subcalendar_name_st)
    events = draw(st.lists(st_event("sub-only", shared_name), min_size=1, max_size=6))
    return events, shared_name


def _build_metadata() -> CalendarMetadata:
    """Build a minimal CalendarMetadata for rendering."""
    return CalendarMetadata(
        calendar_id="cal-test-123",
        calendar_name="Test Calendar",
        export_timestamp=datetime.now(tz=timezone.utc).isoformat(),
        exporter_version="1.0.0",
        date_range=DateRange(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 12, 31, tzinfo=timezone.utc),
        ),
        event_count=0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty15SubcalendarProvenance:
    """Property 15: Markdown subcalendar provenance sub-bullet appears when events come from multiple subcalendars."""

    @given(data=st_multi_subcalendar_events())
    @settings(max_examples=50)
    def test_show_subcalendar_true_includes_calendar_lines(
        self,
        data: tuple[list[Event], str, str],
    ) -> None:
        """When events come from multiple subcalendars and show_subcalendar=True,
        the rendered Markdown contains 'Calendar: {sub_calendar_name}' for every
        event with a non-empty sub_calendar_name.

        **Validates: Requirements 3.3**
        """
        events, name_a, name_b = data
        renderer = CalendarMarkdownRenderer(show_subcalendar=True)
        metadata = _build_metadata()

        output = renderer.render(events, metadata)

        # For every event with a non-empty sub_calendar_name, the output must
        # contain the substring "Calendar: {event.sub_calendar_name}"
        for event in events:
            if event.sub_calendar_name:
                expected_substring = f"Calendar: {event.sub_calendar_name}"
                assert expected_substring in output, (
                    f"Expected '{expected_substring}' in rendered output but not found.\n"
                    f"Event: {event.summary}, sub_calendar_name: {event.sub_calendar_name!r}"
                )

    @given(data=st_single_subcalendar_events())
    @settings(max_examples=50)
    def test_show_subcalendar_false_excludes_calendar_lines(
        self,
        data: tuple[list[Event], str],
    ) -> None:
        """When all events share one sub_calendar_name and show_subcalendar=False,
        the rendered Markdown does NOT include any 'Calendar:' lines.

        **Validates: Requirements 3.3**
        """
        events, _shared_name = data
        renderer = CalendarMarkdownRenderer(show_subcalendar=False)
        metadata = _build_metadata()

        output = renderer.render(events, metadata)

        # No "Calendar:" sub-bullet should appear
        assert "Calendar:" not in output, (
            "Found 'Calendar:' in rendered output when show_subcalendar=False.\n"
            f"Output snippet: {output[:500]}"
        )
