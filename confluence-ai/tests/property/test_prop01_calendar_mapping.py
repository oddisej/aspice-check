"""Feature: confluence-calendar-export, Property 1: Calendar response mapping preserves IDs, names, and sub-calendar structure."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.calendar_client import CalendarClient


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_id_st = st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "P")))
_name_st = st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "Z")))
_type_st = st.sampled_from(["custom", "leaves", "travel", "rota", "events"])


def st_sub_calendar_dict() -> st.SearchStrategy[dict]:
    """Generate a raw sub-calendar dict as returned by the plugin."""
    return st.fixed_dictionaries({
        "subCalendarId": _id_st,
        "name": _name_st,
        "type": _type_st,
        "color": st.text(min_size=0, max_size=7),
        "description": st.text(min_size=0, max_size=50),
    })


def st_calendar_dict() -> st.SearchStrategy[dict]:
    """Generate a raw parent calendar dict as returned by the plugin."""
    return st.fixed_dictionaries({
        "subCalendarId": _id_st,
        "name": _name_st,
        "type": _type_st,
        "spaceKey": st.text(min_size=1, max_size=10, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        "description": st.text(min_size=0, max_size=50),
        "subCalendars": st.lists(st_sub_calendar_dict(), min_size=0, max_size=5),
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty01CalendarMapping:
    """Property 1: Calendar response mapping preserves IDs, names, and sub-calendar structure."""

    @given(raw=st_calendar_dict())
    @settings(max_examples=100)
    def test_calendar_id_preserved(self, raw: dict) -> None:
        """calendar_id equals the input subCalendarId.

        **Validates: Requirements 1.1, 1.2**
        """
        result = CalendarClient._map_calendar(raw)
        assert result.calendar_id == raw["subCalendarId"]

    @given(raw=st_calendar_dict())
    @settings(max_examples=100)
    def test_calendar_name_preserved(self, raw: dict) -> None:
        """name equals the input name.

        **Validates: Requirements 1.1, 1.2**
        """
        result = CalendarClient._map_calendar(raw)
        assert result.name == raw["name"]

    @given(raw=st_calendar_dict())
    @settings(max_examples=100)
    def test_calendar_type_preserved(self, raw: dict) -> None:
        """type equals the input type.

        **Validates: Requirements 1.1, 1.2**
        """
        result = CalendarClient._map_calendar(raw)
        assert result.type == raw["type"]

    @given(raw=st_calendar_dict())
    @settings(max_examples=100)
    def test_sub_calendars_length_matches(self, raw: dict) -> None:
        """sub_calendars list has the same length as input subCalendars.

        **Validates: Requirements 1.1, 1.2**
        """
        result = CalendarClient._map_calendar(raw)
        assert len(result.sub_calendars) == len(raw["subCalendars"])

    @given(raw=st_calendar_dict())
    @settings(max_examples=100)
    def test_sub_calendars_order_and_ids_preserved(self, raw: dict) -> None:
        """sub_calendar IDs match input subCalendars in order.

        **Validates: Requirements 1.1, 1.2**
        """
        result = CalendarClient._map_calendar(raw)
        for i, sc in enumerate(result.sub_calendars):
            assert sc.calendar_id == raw["subCalendars"][i]["subCalendarId"]
            assert sc.name == raw["subCalendars"][i]["name"]
            assert sc.type == raw["subCalendars"][i]["type"]
