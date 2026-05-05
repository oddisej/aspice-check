"""MCP server for ASPICE evaluation and Confluence AI tools.

Implements a stdio JSON-RPC 2.0 transport server exposing five tools:
evaluate_sdp, validate_kb, list_standards, export_page, describe_image.

Handlers call only top-level ``confluence_ai`` and ``aspice_eval`` APIs.

Requirements: 18.1, 18.7, 19.1, 19.2, 19.3, 19.5
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

import jsonschema

import aspice_eval
import confluence_ai

from aspice_check.mcp_tools import (
    ALL_TOOL_SCHEMAS,
    DESCRIBE_IMAGE_SCHEMA,
    EVALUATE_SDP_SCHEMA,
    EXPORT_PAGE_SCHEMA,
    LIST_STANDARDS_SCHEMA,
    VALIDATE_KB_SCHEMA,
)

logger = logging.getLogger(__name__)


class AspiceMCPServer:
    """Model Context Protocol server exposing evaluation and export tools.

    Communicates via stdio transport using JSON-RPC 2.0 messages.
    """

    def __init__(self) -> None:
        self._tool_handlers: dict[str, Any] = {
            "evaluate_sdp": self._handle_evaluate_sdp,
            "validate_kb": self._handle_validate_kb,
            "list_standards": self._handle_list_standards,
            "export_page": self._handle_export_page,
            "describe_image": self._handle_describe_image,
        }
        self._tool_schemas: dict[str, dict] = {
            schema["name"]: schema for schema in ALL_TOOL_SCHEMAS
        }

    def run(self) -> None:
        """Start the MCP server on stdio transport.

        Reads JSON-RPC requests from stdin line-by-line and writes
        JSON-RPC responses to stdout.
        """
        logger.info(
            "Starting aspice-mcp server (stdio transport) with tools: %s",
            ", ".join(sorted(self._tool_handlers.keys())),
        )

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError as exc:
                response = _make_error_response(
                    None, -32700, f"Parse error: {exc}"
                )
                self._write_response(response)
                continue

            response = self._handle_request(request)
            self._write_response(response)

    def _write_response(self, response: dict) -> None:
        """Write a JSON-RPC response to stdout."""
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

    def _handle_request(self, request: dict) -> dict:
        """Route a JSON-RPC request to the appropriate handler."""
        request_id = request.get("id")
        method = request.get("method")

        if method == "tools/list":
            return self._list_tools(request_id)
        elif method == "tools/call":
            return self._call_tool(request)
        elif method == "initialize":
            return self._handle_initialize(request_id)
        else:
            return _make_error_response(
                request_id, -32601, f"Method not found: {method}"
            )

    def _handle_initialize(self, request_id: Any) -> dict:
        """Handle the MCP initialize handshake."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "aspice-mcp",
                    "version": "0.1.0",
                },
            },
        }

    def _list_tools(self, request_id: Any) -> dict:
        """Return the list of available tools with their schemas."""
        tools = []
        for schema in ALL_TOOL_SCHEMAS:
            tools.append({
                "name": schema["name"],
                "description": schema["description"],
                "inputSchema": schema["inputSchema"],
            })
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": tools},
        }

    def _call_tool(self, request: dict) -> dict:
        """Dispatch a tools/call request to the appropriate handler."""
        request_id = request.get("id")
        params = request.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name not in self._tool_handlers:
            return _make_error_response(
                request_id,
                -32602,
                f"Unknown tool: {tool_name}",
                data={
                    "tool": tool_name,
                    "parameter": "name",
                    "actual_value": tool_name,
                    "valid_values": sorted(self._tool_handlers.keys()),
                    "suggestion": "Use one of the listed tool names",
                },
            )

        # Validate parameters against the tool's JSON Schema
        schema = self._tool_schemas[tool_name]
        validation_error = self._validate_params(tool_name, arguments, schema)
        if validation_error is not None:
            return _make_error_response(
                request_id,
                -32602,
                "Invalid params",
                data=validation_error,
            )

        # Dispatch to handler
        try:
            handler = self._tool_handlers[tool_name]
            result = handler(arguments)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
            }
        except Exception as exc:
            return _make_error_response(
                request_id,
                -32603,
                f"Tool execution error: {exc}",
            )

    def _validate_params(
        self, tool_name: str, params: dict, schema: dict
    ) -> dict | None:
        """Validate tool parameters against the declared JSON Schema.

        Returns an error data dict on failure, or None if valid.
        """
        input_schema = schema["inputSchema"]

        try:
            jsonschema.validate(instance=params, schema=input_schema)
        except jsonschema.ValidationError as exc:
            # Extract the failing parameter path
            parameter = ".".join(str(p) for p in exc.absolute_path) if exc.absolute_path else exc.validator
            actual_value = exc.instance

            # Determine valid values from schema context
            valid_values: list[str] | None = None
            suggestion = ""

            if exc.validator == "enum":
                valid_values = exc.schema.get("enum", [])
                suggestion = f"Use one of: {', '.join(str(v) for v in valid_values)}"
            elif exc.validator == "required":
                # exc.message contains the missing field name
                parameter = exc.message.split("'")[1] if "'" in exc.message else "unknown"
                actual_value = None
                suggestion = f"Provide the required parameter '{parameter}'"
            elif exc.validator == "type":
                expected_type = exc.schema.get("type", "unknown")
                suggestion = f"Expected type '{expected_type}'"
                valid_values = [expected_type] if isinstance(expected_type, str) else expected_type
            elif exc.validator == "minimum":
                suggestion = f"Value must be >= {exc.schema.get('minimum')}"
            elif exc.validator == "maximum":
                suggestion = f"Value must be <= {exc.schema.get('maximum')}"
            else:
                suggestion = exc.message

            error_data: dict[str, Any] = {
                "tool": tool_name,
                "parameter": parameter,
                "actual_value": actual_value,
            }
            if valid_values is not None:
                error_data["valid_values"] = valid_values
            error_data["suggestion"] = suggestion

            return error_data

        return None

    # ------------------------------------------------------------------
    # Tool handlers
    # ------------------------------------------------------------------

    def _handle_evaluate_sdp(self, params: dict) -> dict:
        """Handle evaluate_sdp tool call."""
        model_config = aspice_eval.ModelConfig(
            provider=params["provider"],
            model_name=params["model"],
        )
        result = aspice_eval.evaluate_sdp(
            sdp_path=params.get("sdp_path", ""),
            model_config=model_config,
            target_level=params.get("target_level", 3),
            process_groups=params.get("process_groups"),
            standard=params.get("standard", "aspice"),
        )
        return {
            "ratings_count": len(result.ratings),
            "evaluation_timestamp": result.evaluation_timestamp,
            "token_usage": result.token_usage,
        }

    def _handle_validate_kb(self, params: dict) -> dict:
        """Handle validate_kb tool call."""
        result = aspice_eval.validate_kb(
            kb_path=params["kb_path"],
            standard=params.get("standard", "aspice"),
        )
        return {
            "is_valid": result.is_valid,
            "schema_errors": result.schema_errors,
            "completeness_gaps": result.completeness_gaps,
            "warnings": result.warnings,
        }

    def _handle_list_standards(self, params: dict) -> dict:
        """Handle list_standards tool call."""
        kb_path = params.get("kb_path")
        if kb_path:
            kb = aspice_eval.KnowledgeBase(kb_path)
        else:
            kb = aspice_eval.KnowledgeBase("knowledge_base")
        # Return available standards info
        return {"standards": ["aspice"]}

    def _handle_export_page(self, params: dict) -> dict:
        """Handle export_page tool call."""
        ai_config = None
        if params.get("ai_provider"):
            ai_config = confluence_ai.ImageDescriberConfig(
                provider=params["ai_provider"],
                model=params.get("ai_model", ""),
            )
        result = confluence_ai.export_page(
            page_url=params["page_url"],
            output_dir=params["output_dir"],
            email=params["email"],
            api_token=params["api_token"],
            ai_config=ai_config,
            output_format=params.get("output_format", "markdown"),
        )
        return {
            "markdown_path": result.markdown_path,
            "images_downloaded": result.images_downloaded,
            "descriptions_generated": result.descriptions_generated,
        }

    def _handle_describe_image(self, params: dict) -> dict:
        """Handle describe_image tool call."""
        config = confluence_ai.ImageDescriberConfig(
            provider=params["provider"],
            model=params["model"],
        )
        describer = confluence_ai.create_describer(config)
        context = confluence_ai.ImageContext(
            is_gliffy=params.get("is_gliffy", False),
            page_title=params.get("page_title", ""),
        )
        description = describer.describe(params["image_path"], context)
        return {"description": description}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_error_response(
    request_id: Any,
    code: int,
    message: str,
    data: dict | None = None,
) -> dict:
    """Construct a JSON-RPC error response."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the aspice-mcp CLI command.

    Parses args and starts the MCP server on stdio transport.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    server = AspiceMCPServer()
    server.run()
