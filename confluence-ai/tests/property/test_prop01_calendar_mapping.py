"""Feature: confluence-calendar-export, Property 1: Calendar response mapping preserves IDs, names, and sub-calendar structure."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.calendar_client import _map_subcalendars_payload


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_id_st = st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "P")))
_name_st = st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "Z")))
_type_st = st.sampled_from(["custom", "leaves", "travel", "rota", "events"])


def st_child_subcalendar_entry(parent_id: st.SearchStrategy[str] = _id_st) -> st.SearchStrategy[dict]:
    """Generate a child entry in the subcalendars.json payload shape.

    Shape: {"subCalendar": {"id": "...", "name": "...", "type": "...", "color": "...", "description": "...", "parentId": "..."}}
    """
    return st.fixed_dictionaries({
        "subCalendar": st.fixed_dictionaries({
            "id": _id_st,
            "name": _name_st,
            "type": _type_st,
            "color": st.text(min_size=0, max_size=7),
            "description": st.text(min_size=0, max_size=50),
            "parentId": parent_id,
        }),
    })


def st_subcalendars_payload_entry() -> st.SearchStrategy[dict]:
    """Generate a single entry in the subcalendars.json payload array.

    Shape: {"subCalendar": {"id": "...", "name": "...", ...}, "childSubCalendars": [...]}
    """
    return _id_st.flatmap(lambda pid: st.fixed_dictionaries({
        "subCalendar": st.fixed_dictionaries({
            "id": st.just(pid),
            "name": _name_st,
            "type": _type_st,
            "spaceKey": st.text(min_size=1, max_size=10, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
            "description": st.text(min_size=0, max_size=50),
        }),
        "childSubCalendars": st.lists(st_child_subcalendar_entry(st.just(pid)), min_size=0, max_size=5),
    }))


def st_subcalendars_payload() -> st.SearchStrategy[list[dict]]:
    """Generate a full subcalendars.json payload array (list of entries)."""
    return st.lists(st_subcalendars_payload_entry(), min_size=1, max_size=3)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProperty01CalendarMapping:
    """Property 1: Calendar response mapping preserves IDs, names, and sub-calendar structure."""

    @given(payload=st_subcalendars_payload())
    @settings(max_examples=100)
    def test_calendar_id_preserved(self, payload: list[dict]) -> None:
        """calendar_id equals the input subCalendar.id for each entry.

        **Validates: Requirements 1.1, 1.2**
        """
        result = _map_subcalendars_payload(payload)
        for i, cal in enumerate(result):
            assert cal.calendar_id == payload[i]["subCalendar"]["id"]

    @given(payload=st_subcalendars_payload())
    @settings(max_examples=100)
    def test_calendar_name_preserved(self, payload: list[dict]) -> None:
        """name equals the input subCalendar.name for each entry.

        **Validates: Requirements 1.1, 1.2**
        """
        result = _map_subcalendars_payload(payload)
        for i, cal in enumerate(result):
            assert cal.name == payload[i]["subCalendar"]["name"]

    @given(payload=st_subcalendars_payload())
    @settings(max_examples=100)
    def test_calendar_type_preserved(self, payload: list[dict]) -> None:
        """type equals the input subCalendar.type for each entry.

        **Validates: Requirements 1.1, 1.2**
        """
        result = _map_subcalendars_payload(payload)
        for i, cal in enumerate(result):
            assert cal.type == payload[i]["subCalendar"]["type"]

    @given(payload=st_subcalendars_payload())
    @settings(max_examples=100)
    def test_sub_calendars_length_matches(self, payload: list[dict]) -> None:
        """sub_calendars list has the same length as input childSubCalendars.

        **Validates: Requirements 1.1, 1.2**
        """
        result = _map_subcalendars_payload(payload)
        for i, cal in enumerate(result):
            assert len(cal.sub_calendars) == len(payload[i]["childSubCalendars"])

    @given(payload=st_subcalendars_payload())
    @settings(max_examples=100)
    def test_sub_calendars_ids_and_names_preserved(self, payload: list[dict]) -> None:
        """sub_calendar IDs and names match input childSubCalendars in order.

        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        result = _map_subcalendars_payload(payload)
        for i, cal in enumerate(result):
            for j, sc in enumerate(cal.sub_calendars):
                child_raw = payload[i]["childSubCalendars"][j]["subCalendar"]
                assert sc.calendar_id == child_raw["id"]
                assert sc.name == child_raw["name"]
                assert sc.type == child_raw["type"]
                assert sc.parent_id == child_raw["parentId"]
