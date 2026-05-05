"""Property 19: MCP Invalid Parameter Error Response.

**Validates: Requirements 18.7**

For any MCP tool call with missing required parameters or parameters that
violate the declared JSON Schema, the MCP server shall return a structured
error response containing actionable details about which parameters are
invalid.
"""

from __future__ import annotations

import json

from hypothesis import given, settings, strategies as st

from aspice_check.mcp_server import AspiceMCPServer
from aspice_check.mcp_tools import ALL_TOOL_SCHEMAS


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for valid tool names (from the declared schemas)
_TOOL_NAMES = [schema["name"] for schema in ALL_TOOL_SCHEMAS]
tool_name_st = st.sampled_from(_TOOL_NAMES)

# Strategy for invalid provider values (not in the enum)
invalid_provider_st = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_",
    min_size=1,
    max_size=20,
).filter(lambda s: s not in {"bedrock", "openai", "anthropic"})

# Strategy for invalid target_level values (outside 1-5 range)
invalid_target_level_st = st.one_of(
    st.integers(max_value=0),
    st.integers(min_value=6),
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(tool_name=tool_name_st)
def test_prop19_missing_required_params_returns_error(tool_name: str) -> None:
    """Calling a tool with empty params when required fields exist returns -32602.

    **Validates: Requirements 18.7**
    """
    server = AspiceMCPServer()

    # Find the schema for this tool
    schema = next(s for s in ALL_TOOL_SCHEMAS if s["name"] == tool_name)
    required_fields = schema["inputSchema"].get("required", [])

    if not required_fields:
        # list_standards has no required fields — skip
        return

    # Call with empty arguments (missing all required params)
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": {}},
    }

    response = server._handle_request(request)

    # Must be an error response
    assert "error" in response, f"Expected error response for {tool_name} with empty params"
    error = response["error"]
    assert error["code"] == -32602
    assert "data" in error

    data = error["data"]
    assert data["tool"] == tool_name
    assert "parameter" in data
    assert "suggestion" in data


@settings(max_examples=50)
@given(invalid_provider=invalid_provider_st)
def test_prop19_invalid_enum_value_returns_error(invalid_provider: str) -> None:
    """Calling evaluate_sdp with an invalid provider enum returns -32602 with valid_values.

    **Validates: Requirements 18.7**
    """
    server = AspiceMCPServer()

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "evaluate_sdp",
            "arguments": {
                "provider": invalid_provider,
                "model": "some-model",
            },
        },
    }

    response = server._handle_request(request)

    assert "error" in response
    error = response["error"]
    assert error["code"] == -32602
    assert "data" in error

    data = error["data"]
    assert data["tool"] == "evaluate_sdp"
    assert data["parameter"] == "provider"
    assert data["actual_value"] == invalid_provider
    assert "valid_values" in data
    assert set(data["valid_values"]) == {"bedrock", "openai", "anthropic"}
    assert "suggestion" in data


@settings(max_examples=50)
@given(invalid_level=invalid_target_level_st)
def test_prop19_invalid_integer_range_returns_error(invalid_level: int) -> None:
    """Calling evaluate_sdp with target_level outside 1-5 returns -32602.

    **Validates: Requirements 18.7**
    """
    server = AspiceMCPServer()

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "evaluate_sdp",
            "arguments": {
                "provider": "bedrock",
                "model": "some-model",
                "target_level": invalid_level,
            },
        },
    }

    response = server._handle_request(request)

    assert "error" in response
    error = response["error"]
    assert error["code"] == -32602
    assert "data" in error

    data = error["data"]
    assert data["tool"] == "evaluate_sdp"
    assert data["actual_value"] == invalid_level
    assert "suggestion" in data


@settings(max_examples=50)
@given(
    unknown_tool=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz_",
        min_size=1,
        max_size=20,
    ).filter(lambda s: s not in _TOOL_NAMES)
)
def test_prop19_unknown_tool_returns_error(unknown_tool: str) -> None:
    """Calling an unknown tool returns -32602 with valid tool names listed.

    **Validates: Requirements 18.7**
    """
    server = AspiceMCPServer()

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": unknown_tool, "arguments": {}},
    }

    response = server._handle_request(request)

    assert "error" in response
    error = response["error"]
    assert error["code"] == -32602
    assert "data" in error

    data = error["data"]
    assert data["tool"] == unknown_tool
    assert "valid_values" in data
    assert set(data["valid_values"]) == set(_TOOL_NAMES)
    assert "suggestion" in data
