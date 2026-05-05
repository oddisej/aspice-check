"""Feature: confluence-calendar-export, Property 7: Markdown events render grouped and chronologically ordered."""

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

# Use printable ASCII for summaries to make regex matching reliable
_summary_st = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=" "),
).filter(lambda s: s.strip() != "")


def st_event() -> st.SearchStrategy[Event]:
    """Generate a valid Event instance with a unique-ish summary."""
    return st.builds(
        _build_event,
        event_id=st.text(min_size=1, max_size=10, alphabet="abcdef0123456789"),
        summary=_summary_st,
        start=_tz_aware_dt_st,
        duration_hours=st.integers(min_value=1, max_value=12),
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

_DATE_HEADER_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})$", re.MULTILINE)


def _extract_date_headers(text: str) -> list[str]:
    """Extract all ## YYYY-MM-DD headers from the markdown output."""
    return _DATE_HEADER_RE.findall(text)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty07MarkdownOrdering:
    """Property 7: Markdown events render grouped and chronologically ordered."""

    @given(events=st.lists(st_event(), min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_one_header_per_distinct_date(self, events: list[Event]) -> None:
        """One ## YYYY-MM-DD header per distinct local date of events.

        **Validates: Requirements 4.2, 4.3**
        """
        metadata = _make_metadata()
        renderer = CalendarMarkdownRenderer()
        output = renderer.render(events, metadata)

        headers = _extract_date_headers(output)
        expected_dates = sorted({e.start.date().isoformat() for e in events})

        assert headers == expected_dates

    @given(events=st.lists(st_event(), min_size=2, max_size=10))
    @settings(max_examples=100)
    def test_headers_strictly_ascending(self, events: list[Event]) -> None:
        """Date headers appear in strictly ascending order.

        **Validates: Requirements 4.2, 4.3**
        """
        metadata = _make_metadata()
        renderer = CalendarMarkdownRenderer()
        output = renderer.render(events, metadata)

        headers = _extract_date_headers(output)
        for i in range(1, len(headers)):
            assert headers[i] > headers[i - 1], (
                f"Headers not ascending: {headers[i-1]} >= {headers[i]}"
            )

    @given(events=st.lists(st_event(), min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_every_summary_appears_in_output(self, events: list[Event]) -> None:
        """Every event summary appears at least once in the rendered output.

        **Validates: Requirements 4.2, 4.3**
        """
        metadata = _make_metadata()
        renderer = CalendarMarkdownRenderer()
        output = renderer.render(events, metadata)

        for event in events:
            assert event.summary in output, (
                f"Summary {event.summary!r} not found in output"
            )
