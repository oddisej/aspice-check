"""Feature: confluence-calendar-export, Property 8: All-day vs timed event rendering dichotomy."""

from __future__ import annotations

import re
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

_summary_st = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=" "),
).filter(lambda s: s.strip() != "")


def st_event(all_day: bool) -> st.SearchStrategy[Event]:
    """Generate an Event with a specific all_day value."""
    return st.builds(
        _build_event,
        event_id=st.text(min_size=1, max_size=10, alphabet="abcdef0123456789"),
        summary=_summary_st,
        start=_tz_aware_dt_st,
        duration_hours=st.integers(min_value=1, max_value=24),
        all_day=st.just(all_day),
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
    )


def _make_metadata() -> CalendarMetadata:
    """Create a simple metadata instance for rendering."""
    now = datetime.now(timezone.utc)
    return CalendarMetadata(
        calendar_id="test-cal",
        calendar_name="Test Calendar",
        export_timestamp=now.isoformat(),
        exporter_version="0.3.0",
        date_range=DateRange(start=now - timedelta(days=30), end=now + timedelta(days=90)),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HHMM_RE = re.compile(r"\d{2}:\d{2}")


def _find_event_bullet_line(output: str, summary: str) -> str:
    """Find the bullet line containing the event summary."""
    for line in output.split("\n"):
        if line.startswith("- **") and summary in line:
            return line
    raise AssertionError(f"Could not find bullet line for summary {summary!r}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty08AllDayDichotomy:
    """Property 8: All-day vs timed event rendering dichotomy."""

    @given(event=st_event(all_day=True))
    @settings(max_examples=100)
    def test_all_day_event_contains_all_day_text(self, event: Event) -> None:
        """all_day=True → line contains 'All day' and no HH:MM.

        **Validates: Requirements 4.4**
        """
        metadata = _make_metadata()
        renderer = CalendarMarkdownRenderer()
        output = renderer.render([event], metadata)

        line = _find_event_bullet_line(output, event.summary)
        assert "All day" in line, f"Expected 'All day' in line: {line!r}"
        assert not _HHMM_RE.search(line), f"Unexpected HH:MM in all-day line: {line!r}"

    @given(event=st_event(all_day=False))
    @settings(max_examples=100)
    def test_timed_event_contains_hhmm_no_all_day(self, event: Event) -> None:
        """all_day=False → line contains two HH:MM substrings and no 'All day'.

        **Validates: Requirements 4.4**
        """
        metadata = _make_metadata()
        renderer = CalendarMarkdownRenderer()
        output = renderer.render([event], metadata)

        line = _find_event_bullet_line(output, event.summary)
        assert "All day" not in line, f"Unexpected 'All day' in timed line: {line!r}"
        times = _HHMM_RE.findall(line)
        assert len(times) >= 2, f"Expected at least 2 HH:MM in timed line: {line!r}"
