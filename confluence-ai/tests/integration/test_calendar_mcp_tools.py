"""Integration tests for the MCP calendar tools (list_calendars, export_calendar).

Instantiates ``AspiceMCPServer`` directly and exercises the JSON-RPC 2.0
dispatch path for both calendar tools, verifying schema exposure, successful
tool calls with mocked backends, and parameter validation error handling.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**
"""

from __future__ import annotations

import json

import pytest

from aspice_check.mcp_server import AspiceMCPServer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _jsonrpc_request(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    """Build a JSON-RPC 2.0 request dict."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCalendarMCPToolsListing:
    """Verify both calendar tools appear in tools/list with correct schemas."""

    def test_tools_list_contains_calendar_tools(self):
        """Both list_calendars and export_calendar appear in tools/list."""
        server = AspiceMCPServer()
        response = server._handle_request(_jsonrpc_request("tools/list"))

        assert "result" in response
        tools = response["result"]["tools"]
        tool_names = [t["name"] for t in tools]

        assert "list_calendars" in tool_names
        assert "export_calendar" in tool_names

    def test_list_calendars_schema_has_required_params(self):
        """list_calendars schema declares base_url and page_url as required."""
        server = AspiceMCPServer()
        response = server._handle_request(_jsonrpc_request("tools/list"))

        tools = response["result"]["tools"]
        schema = next(t for t in tools if t["name"] == "list_calendars")

        assert "inputSchema" in schema
        input_schema = schema["inputSchema"]
        assert "base_url" in input_schema["properties"]
        assert "page_url" in input_schema["properties"]
        assert "base_url" in input_schema["required"]
        assert "page_url" in input_schema["required"]

    def test_export_calendar_schema_has_required_params(self):
        """export_calendar schema declares base_url, calendar_id, output_dir as required."""
        server = AspiceMCPServer()
        response = server._handle_request(_jsonrpc_request("tools/list"))

        tools = response["result"]["tools"]
        schema = next(t for t in tools if t["name"] == "export_calendar")

        assert "inputSchema" in schema
        input_schema = schema["inputSchema"]
        assert "base_url" in input_schema["properties"]
        assert "calendar_id" in input_schema["properties"]
        assert "output_dir" in input_schema["properties"]
        assert "base_url" in input_schema["required"]
        assert "calendar_id" in input_schema["required"]
        assert "output_dir" in input_schema["required"]


class TestListCalendarsTool:
    """Verify the list_calendars tool call dispatches correctly."""

    def test_list_calendars_returns_calendars_in_mcp_envelope(self, mocker):
        """list_calendars wraps the result in the MCP content envelope."""
        from confluence_ai.models import Calendar, SubCalendar

        mock_calendars = [
            Calendar(
                calendar_id="cal-001",
                name="Team Leave",
                type="custom",
                space_key="ENG",
                description="Out of office",
                sub_calendars=[
                    SubCalendar(
                        calendar_id="cal-001-leaves",
                        name="Leaves",
                        type="leaves",
                        color="#ff0000",
                        description="",
                    ),
                ],
            ),
        ]

        mocker.patch(
            "confluence_ai.calendar_client.CalendarClient.__init__",
            return_value=None,
        )
        mocker.patch(
            "confluence_ai.calendar_client.CalendarClient.list_calendars_from_page",
            return_value=mock_calendars,
        )

        server = AspiceMCPServer()
        response = server._handle_request(
            _jsonrpc_request(
                "tools/call",
                {
                    "name": "list_calendars",
                    "arguments": {
                        "base_url": "https://acme.atlassian.net/wiki",
                        "page_url": "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456/Calendar",
                        "email": "user@example.com",
                        "api_token": "token-123",
                    },
                },
            )
        )

        assert "result" in response, f"Expected result, got: {response}"
        content = response["result"]["content"]
        assert len(content) == 1
        assert content[0]["type"] == "text"

        payload = json.loads(content[0]["text"])
        assert "calendars" in payload
        assert len(payload["calendars"]) == 1
        assert payload["calendars"][0]["calendar_id"] == "cal-001"
        assert payload["calendars"][0]["name"] == "Team Leave"
        assert len(payload["calendars"][0]["sub_calendars"]) == 1


class TestExportCalendarTool:
    """Verify the export_calendar tool call dispatches correctly."""

    def test_export_calendar_returns_result_in_mcp_envelope(self, tmp_path, mocker):
        """export_calendar wraps output_path, event_count, warnings in MCP envelope."""
        from confluence_ai.models import CalendarExportResult

        output_dir = str(tmp_path / "cal_output")
        fake_output_path = str(tmp_path / "cal_output" / "Team_Leave.json")

        mock_result = CalendarExportResult(
            output_path=fake_output_path,
            event_count=5,
            warnings=["Some warning"],
        )

        mocker.patch(
            "confluence_ai.export_calendar",
            return_value=mock_result,
        )

        server = AspiceMCPServer()
        response = server._handle_request(
            _jsonrpc_request(
                "tools/call",
                {
                    "name": "export_calendar",
                    "arguments": {
                        "base_url": "https://acme.atlassian.net/wiki",
                        "calendar_id": "cal-001",
                        "output_dir": output_dir,
                        "output_format": "json",
                        "email": "user@example.com",
                        "api_token": "token-123",
                    },
                },
            )
        )

        assert "result" in response, f"Expected result, got: {response}"
        content = response["result"]["content"]
        assert len(content) == 1
        assert content[0]["type"] == "text"

        payload = json.loads(content[0]["text"])
        assert payload["output_path"] == fake_output_path
        assert payload["event_count"] == 5
        assert payload["warnings"] == ["Some warning"]


class TestCalendarToolValidation:
    """Verify parameter validation returns -32602 Invalid params."""

    def test_missing_required_param_returns_invalid_params_error(self):
        """Missing base_url on list_calendars returns -32602 error."""
        server = AspiceMCPServer()
        response = server._handle_request(
            _jsonrpc_request(
                "tools/call",
                {
                    "name": "list_calendars",
                    "arguments": {
                        # Missing base_url — required
                        "page_url": "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456/Calendar",
                    },
                },
            )
        )

        assert "error" in response
        assert response["error"]["code"] == -32602
        assert response["error"]["message"] == "Invalid params"

    def test_missing_calendar_id_returns_invalid_params_error(self):
        """Missing calendar_id on export_calendar returns -32602 error."""
        server = AspiceMCPServer()
        response = server._handle_request(
            _jsonrpc_request(
                "tools/call",
                {
                    "name": "export_calendar",
                    "arguments": {
                        "base_url": "https://acme.atlassian.net/wiki",
                        # Missing calendar_id — required
                        "output_dir": "/tmp/out",
                    },
                },
            )
        )

        assert "error" in response
        assert response["error"]["code"] == -32602
        assert response["error"]["message"] == "Invalid params"

    def test_missing_page_url_returns_invalid_params_error(self):
        """Missing page_url on list_calendars returns -32602 error."""
        server = AspiceMCPServer()
        response = server._handle_request(
            _jsonrpc_request(
                "tools/call",
                {
                    "name": "list_calendars",
                    "arguments": {
                        "base_url": "https://acme.atlassian.net/wiki",
                        # Missing page_url — required
                    },
                },
            )
        )

        assert "error" in response
        assert response["error"]["code"] == -32602
        assert response["error"]["message"] == "Invalid params"
