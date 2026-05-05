"""Unit tests for CalendarClient page-driven calendar discovery.

Verifies that list_calendars_from_page correctly extracts calendar macro IDs
from a page's storage body, resolves them via list_subcalendars, and returns
a sorted calendar tree.

Requirements: 1.1, 1.4, 1.5, 1.6, 1.9, 1.10
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from confluence_ai.calendar_client import CalendarClient
from confluence_ai.exceptions import InvalidURLError
from confluence_ai.models import Calendar, PageData, SubCalendar


@pytest.fixture
def client():
    """Create a CalendarClient with mocked Confluence and ConfluenceClient."""
    with patch("confluence_ai.calendar_client.Confluence") as mock_confluence, \
         patch("confluence_ai.calendar_client.ConfluenceClient") as mock_conf_client:
        mock_instance = MagicMock()
        mock_instance._session = MagicMock()
        mock_confluence.return_value = mock_instance
        c = CalendarClient(
            base_url="https://acme.atlassian.net/wiki",
            email="user@acme.com",
            api_token="token123",
        )
    return c


VALID_PAGE_URL = (
    "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456789/My-Page"
)


class TestListCalendarsFromPage:
    """Tests for list_calendars_from_page discovery flow."""

    def test_page_with_no_macros_returns_empty_list(self, client):
        """A page with no calendar macros returns an empty list."""
        page_data = PageData(
            page_id="123456789",
            title="Empty Page",
            storage_format="<p>No calendars here</p>",
            version=1,
            space_key="ENG",
        )
        client._confluence_client.get_page.return_value = page_data

        result = client.list_calendars_from_page(VALID_PAGE_URL)

        assert result == []

    def test_page_with_single_macro_returns_calendar(self, client):
        """A page with one calendar macro returns the resolved calendar."""
        storage = (
            '<ac:structured-macro ac:name="calendar">'
            '<ac:parameter ac:name="id">parent-1</ac:parameter>'
            '</ac:structured-macro>'
        )
        page_data = PageData(
            page_id="123456789",
            title="Calendar Page",
            storage_format=storage,
            version=1,
            space_key="ENG",
        )
        client._confluence_client.get_page.return_value = page_data

        expected_calendar = Calendar(
            calendar_id="parent-1",
            name="Team Calendar",
            type="custom",
            space_key="ENG",
            sub_calendars=[
                SubCalendar(
                    calendar_id="child-1",
                    name="Leaves",
                    type="leaves",
                    parent_id="parent-1",
                ),
            ],
        )
        client.list_subcalendars = MagicMock(return_value=expected_calendar)

        result = client.list_calendars_from_page(VALID_PAGE_URL)

        assert len(result) == 1
        assert result[0].calendar_id == "parent-1"
        assert result[0].name == "Team Calendar"
        assert len(result[0].sub_calendars) == 1
        assert result[0].sub_calendars[0].calendar_id == "child-1"
        client.list_subcalendars.assert_called_once_with("parent-1", "ENG")

    def test_page_with_comma_separated_ids_in_single_macro(self, client):
        """A macro with comma-separated IDs resolves each ID separately."""
        storage = (
            '<ac:structured-macro ac:name="calendar">'
            '<ac:parameter ac:name="id">abc-123,def-456</ac:parameter>'
            '</ac:structured-macro>'
        )
        page_data = PageData(
            page_id="123456789",
            title="Multi-ID Page",
            storage_format=storage,
            version=1,
            space_key="ENG",
        )
        client._confluence_client.get_page.return_value = page_data

        cal_abc = Calendar(
            calendar_id="abc-123",
            name="Alpha Calendar",
            type="custom",
            space_key="ENG",
            sub_calendars=[],
        )
        cal_def = Calendar(
            calendar_id="def-456",
            name="Beta Calendar",
            type="custom",
            space_key="ENG",
            sub_calendars=[],
        )
        client.list_subcalendars = MagicMock(
            side_effect=[cal_abc, cal_def]
        )

        result = client.list_calendars_from_page(VALID_PAGE_URL)

        assert len(result) == 2
        # Should be sorted case-insensitively: Alpha before Beta
        assert result[0].name == "Alpha Calendar"
        assert result[1].name == "Beta Calendar"
        assert client.list_subcalendars.call_count == 2

    def test_page_with_multiple_calendar_macros(self, client):
        """Multiple calendar macros on a page each get resolved."""
        storage = (
            '<ac:structured-macro ac:name="calendar">'
            '<ac:parameter ac:name="id">cal-z</ac:parameter>'
            '</ac:structured-macro>'
            '<p>Some content</p>'
            '<ac:structured-macro ac:name="calendar">'
            '<ac:parameter ac:name="id">cal-a</ac:parameter>'
            '</ac:structured-macro>'
        )
        page_data = PageData(
            page_id="123456789",
            title="Multi-Macro Page",
            storage_format=storage,
            version=1,
            space_key="ENG",
        )
        client._confluence_client.get_page.return_value = page_data

        cal_z = Calendar(
            calendar_id="cal-z",
            name="Zebra Calendar",
            type="custom",
            space_key="ENG",
            sub_calendars=[],
        )
        cal_a = Calendar(
            calendar_id="cal-a",
            name="Apple Calendar",
            type="custom",
            space_key="ENG",
            sub_calendars=[],
        )
        client.list_subcalendars = MagicMock(
            side_effect=[cal_z, cal_a]
        )

        result = client.list_calendars_from_page(VALID_PAGE_URL)

        assert len(result) == 2
        # Sorted case-insensitively: Apple before Zebra
        assert result[0].name == "Apple Calendar"
        assert result[1].name == "Zebra Calendar"

    def test_invalid_page_url_raises_invalid_url_error(self, client):
        """An invalid page URL raises InvalidURLError."""
        with pytest.raises(InvalidURLError):
            client.list_calendars_from_page("https://not-a-valid-url.com/foo")

    def test_sorted_calendar_tree_with_subcalendars(self, client):
        """Calendars and their sub-calendars are sorted case-insensitively."""
        storage = (
            '<ac:structured-macro ac:name="calendar">'
            '<ac:parameter ac:name="id">parent-1</ac:parameter>'
            '</ac:structured-macro>'
        )
        page_data = PageData(
            page_id="123456789",
            title="Sorted Page",
            storage_format=storage,
            version=1,
            space_key="ENG",
        )
        client._confluence_client.get_page.return_value = page_data

        calendar = Calendar(
            calendar_id="parent-1",
            name="Team Calendar",
            type="custom",
            space_key="ENG",
            sub_calendars=[
                SubCalendar(
                    calendar_id="child-z",
                    name="zebra",
                    type="custom",
                    parent_id="parent-1",
                ),
                SubCalendar(
                    calendar_id="child-a",
                    name="Alpha",
                    type="leaves",
                    parent_id="parent-1",
                ),
                SubCalendar(
                    calendar_id="child-m",
                    name="middle",
                    type="travel",
                    parent_id="parent-1",
                ),
            ],
        )
        client.list_subcalendars = MagicMock(return_value=calendar)

        result = client.list_calendars_from_page(VALID_PAGE_URL)

        assert len(result) == 1
        subs = result[0].sub_calendars
        assert len(subs) == 3
        # Sorted case-insensitively: Alpha, middle, zebra
        assert subs[0].name == "Alpha"
        assert subs[1].name == "middle"
        assert subs[2].name == "zebra"

    def test_duplicate_ids_across_macros_are_deduplicated(self, client):
        """Duplicate calendar IDs across macros are resolved only once."""
        storage = (
            '<ac:structured-macro ac:name="calendar">'
            '<ac:parameter ac:name="id">parent-1</ac:parameter>'
            '</ac:structured-macro>'
            '<ac:structured-macro ac:name="calendar">'
            '<ac:parameter ac:name="id">parent-1</ac:parameter>'
            '</ac:structured-macro>'
        )
        page_data = PageData(
            page_id="123456789",
            title="Dupe Page",
            storage_format=storage,
            version=1,
            space_key="ENG",
        )
        client._confluence_client.get_page.return_value = page_data

        calendar = Calendar(
            calendar_id="parent-1",
            name="Team Calendar",
            type="custom",
            space_key="ENG",
            sub_calendars=[],
        )
        client.list_subcalendars = MagicMock(return_value=calendar)

        result = client.list_calendars_from_page(VALID_PAGE_URL)

        assert len(result) == 1
        client.list_subcalendars.assert_called_once_with("parent-1", "ENG")
