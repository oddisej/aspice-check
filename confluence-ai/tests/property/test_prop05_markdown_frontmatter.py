"""Feature: confluence-calendar-export, Property 5: Markdown front-matter parses to the original metadata."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import yaml
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

# Use simple ASCII text to avoid YAML quoting issues in assertions
_safe_text_st = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=" _-"),
).filter(lambda s: s.strip() != "")


def st_event() -> st.SearchStrategy[Event]:
    """Generate a valid Event instance."""
    return st.builds(
        _build_event,
        event_id=st.text(min_size=1, max_size=10, alphabet="abcdef0123456789"),
        summary=_safe_text_st,
        start=_tz_aware_dt_st,
        duration_hours=st.integers(min_value=1, max_value=24),
    )


def _build_event(event_id: str, summary: str, start: datetime, duration_hours: int) -> Event:
    return Event(
        event_id=event_id,
        summary=summary,
        start=start,
        end=start + timedelta(hours=duration_hours),
        all_day=False,
    )


def st_metadata() -> st.SearchStrategy[CalendarMetadata]:
    """Generate a valid CalendarMetadata instance."""
    return st.builds(
        _build_metadata,
        calendar_id=st.text(min_size=1, max_size=20, alphabet="abcdef0123456789-"),
        calendar_name=_safe_text_st,
        start=_tz_aware_dt_st,
        range_days=st.integers(min_value=1, max_value=180),
        exporter_version=st.just("0.3.0"),
    )


def _build_metadata(
    calendar_id: str,
    calendar_name: str,
    start: datetime,
    range_days: int,
    exporter_version: str,
) -> CalendarMetadata:
    return CalendarMetadata(
        calendar_id=calendar_id,
        calendar_name=calendar_name,
        export_timestamp=datetime.now(timezone.utc).isoformat(),
        exporter_version=exporter_version,
        date_range=DateRange(start=start, end=start + timedelta(days=range_days)),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_frontmatter(text: str) -> dict:
    """Extract and parse the YAML front-matter block from markdown text."""
    lines = text.split("\n")
    assert lines[0] == "---", "Markdown must start with ---"
    end_idx = lines.index("---", 1)
    yaml_block = "\n".join(lines[1:end_idx])
    return yaml.safe_load(yaml_block)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty05MarkdownFrontmatter:
    """Property 5: Markdown front-matter parses to the original metadata."""

    @given(
        metadata=st_metadata(),
        events=st.lists(st_event(), min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_frontmatter_has_required_fields(
        self, metadata: CalendarMetadata, events: list[Event]
    ) -> None:
        """Front-matter contains all required fields.

        **Validates: Requirements 4.1**
        """
        renderer = CalendarMarkdownRenderer()
        output = renderer.render(events, metadata)
        fm = _extract_frontmatter(output)

        assert "calendar_id" in fm
        assert "calendar_name" in fm
        assert "export_timestamp" in fm
        assert "exporter_version" in fm
        assert "date_range" in fm
        assert "event_count" in fm

    @given(
        metadata=st_metadata(),
        events=st.lists(st_event(), min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_frontmatter_values_match_metadata(
        self, metadata: CalendarMetadata, events: list[Event]
    ) -> None:
        """Front-matter values equal M's values.

        **Validates: Requirements 4.1**
        """
        renderer = CalendarMarkdownRenderer()
        output = renderer.render(events, metadata)
        fm = _extract_frontmatter(output)

        assert fm["calendar_id"] == metadata.calendar_id
        assert fm["calendar_name"] == metadata.calendar_name
        assert fm["exporter_version"] == metadata.exporter_version
        # event_count is set by the renderer to len(events)
        assert fm["event_count"] == len(events)

    @given(
        metadata=st_metadata(),
        events=st.lists(st_event(), min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_frontmatter_date_range_matches(
        self, metadata: CalendarMetadata, events: list[Event]
    ) -> None:
        """date_range start/end match M's values as YYYY-MM-DD strings.

        **Validates: Requirements 4.1**
        """
        renderer = CalendarMarkdownRenderer()
        output = renderer.render(events, metadata)
        fm = _extract_frontmatter(output)

        expected_start = metadata.date_range.start.strftime("%Y-%m-%d")
        expected_end = metadata.date_range.end.strftime("%Y-%m-%d")

        assert fm["date_range"]["start"] == expected_start
        assert fm["date_range"]["end"] == expected_end
