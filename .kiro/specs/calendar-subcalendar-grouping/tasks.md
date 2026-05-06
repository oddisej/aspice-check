# Implementation Plan: Calendar Subcalendar Grouping

## Overview

Convert the feature design into a series of prompts for a code-generation LLM that will implement each step with incremental progress. Make sure that each prompt builds on the previous prompts, and ends with wiring things together. There should be no hanging or orphaned code that isn't integrated into a previous step. Focus ONLY on tasks that involve writing, modifying, or testing code.

Implementation language: **Python 3.10+** (matches the existing `confluence-ai` and `aspice-check` packages). All code uses `from __future__ import annotations`, `@dataclass` models, and `str | None` union syntax.

This feature adds a new `export_calendar_grouped()` convenience function that produces a unified calendar view when exporting a parent calendar. The existing `export_calendar()` function remains unchanged. The MCP `export_calendar` tool switches to using the grouped export internally.

**Files being modified:**

- `confluence-ai/src/confluence_ai/calendar_export.py` — add `_resolve_calendar_name()` helper and `export_calendar_grouped()` function
- `confluence-ai/src/confluence_ai/calendar_renderer.py` — add `show_subcalendar` constructor parameter to `CalendarMarkdownRenderer`
- `confluence-ai/src/confluence_ai/__init__.py` — export `export_calendar_grouped`
- `aspice-check/src/aspice_check/mcp_server.py` — update `_handle_export_calendar` to use `export_calendar_grouped`

**Files unchanged:** `calendar_client.py`, `models.py`, `exceptions.py`, `mcp_tools.py`

Conventions:

- Tasks marked with `*` are optional (per workflow); core implementation tasks are never marked optional.
- Property-based tests use `hypothesis`; each property test file carries a module docstring of the form `"""Feature: calendar-subcalendar-grouping, Property N: <title>."""`.
- Property tests live under `confluence-ai/tests/property/` using the `test_propNN_*.py` naming convention (starting at prop13 for this feature).
- Unit tests live under `confluence-ai/tests/unit/`.
- Integration tests live under `confluence-ai/tests/integration/`.
- No live Confluence calls — all HTTP is mocked with `pytest-mock` / fixture objects.

## Tasks

- [x] 1. Extend `CalendarMarkdownRenderer` with `show_subcalendar` parameter
  - [x] 1.1 Add `show_subcalendar: bool = False` constructor parameter to `CalendarMarkdownRenderer` in `confluence-ai/src/confluence_ai/calendar_renderer.py`
    - Add `__init__(self, show_subcalendar: bool = False) -> None` method that stores `self._show_subcalendar = show_subcalendar`
    - In the `render` method, after rendering each event's main bullet line (and before location/organizer/description sub-bullets), if `self._show_subcalendar is True` and `event.sub_calendar_name` is non-empty, insert a sub-bullet: `  - Calendar: {event.sub_calendar_name}`
    - The default `show_subcalendar=False` preserves existing behavior — no sub-calendar bullet is emitted
    - _Requirements: 3.3_
  - [x] 1.2 Write unit tests for `show_subcalendar` rendering behavior
    - Add tests to `confluence-ai/tests/unit/test_calendar_export_grouped.py`
    - Test that `CalendarMarkdownRenderer(show_subcalendar=True)` includes `Calendar: <name>` sub-bullets for each event
    - Test that `CalendarMarkdownRenderer(show_subcalendar=False)` does NOT include `Calendar:` sub-bullets (backward compat)
    - Test that events with empty `sub_calendar_name` do not get a `Calendar:` sub-bullet even when `show_subcalendar=True`
    - _Requirements: 3.3_

- [x] 2. Implement `_resolve_calendar_name()` helper and `export_calendar_grouped()` function
  - [x] 2.1 Add `_resolve_calendar_name(client, calendar_id, events)` helper to `confluence-ai/src/confluence_ai/calendar_export.py`
    - Signature: `def _resolve_calendar_name(client: CalendarClient, calendar_id: str, events: list[Event]) -> str`
    - Try `client.list_subcalendars(calendar_id, space_key="")` — if it returns a `Calendar` with a non-empty `name`, return that name
    - Catch `CalendarNotFoundError` and `CalendarAPIError` silently (these indicate a child ID was passed)
    - Fall back: if events exist and all share one `sub_calendar_name`, return that name
    - Final fall back: return `calendar_id` as-is
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - [x] 2.2 Add `export_calendar_grouped()` function to `confluence-ai/src/confluence_ai/calendar_export.py`
    - Signature matches `export_calendar()`: keyword-only args `base_url`, `calendar_id`, `output_dir`, `email`, `api_token`, `output_format="json"`, `date_range=None`
    - Returns `CalendarExportResult`
    - Step 1: Validate credentials (raise `AuthenticationError` on empty email/token) — same as `export_calendar`
    - Step 2: Resolve default date range if None: `now - 30d` → `now + 90d` (UTC) — same as `export_calendar`
    - Step 3: Construct `CalendarClient(base_url, email, api_token)`
    - Step 4: Fetch events via `client.get_events(calendar_id, date_range)` — parent→children auto-resolution happens transparently
    - Step 5: Resolve calendar name via `_resolve_calendar_name(client, calendar_id, events)`
    - Step 6: Determine `show_subcalendar`: `True` if events have more than one unique `sub_calendar_name`, else `False`
    - Step 7: Select renderer — `CalendarJSONRenderer()` for JSON, `CalendarMarkdownRenderer(show_subcalendar=show_subcalendar)` for Markdown
    - Step 8: Build `CalendarMetadata` with resolved `calendar_name` and `event_count=len(events)`
    - Step 9: Render, sanitize filename via `_sanitize_calendar_name(calendar_name)`, write to `output_dir`
    - Step 10: Return `CalendarExportResult(output_path, event_count, warnings=[])`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 3.2, 4.1, 4.2, 4.3_

- [x] 3. Export `export_calendar_grouped` from the public API
  - [x] 3.1 Add `export_calendar_grouped` to `confluence-ai/src/confluence_ai/__init__.py`
    - Add import: `from confluence_ai.calendar_export import export_calendar_grouped`
    - Add `"export_calendar_grouped"` to the `__all__` list in the "Convenience functions" section
    - _Requirements: 5.1_

- [x] 4. Checkpoint — Ensure grouped export compiles and existing tests still pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Update MCP handler to use `export_calendar_grouped`
  - [x] 5.1 Update `_handle_export_calendar` in `aspice-check/src/aspice_check/mcp_server.py`
    - Change the import from `confluence_ai.export_calendar` to `confluence_ai.export_calendar_grouped`
    - Replace `confluence_ai.export_calendar(...)` call with `confluence_ai.export_calendar_grouped(...)`
    - Keep all other handler logic unchanged (DateRange construction, response dict shape)
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 6. Checkpoint — Ensure MCP handler change compiles and existing tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Write unit tests for `export_calendar_grouped` and `_resolve_calendar_name`
  - [x] 7.1 Create `confluence-ai/tests/unit/test_calendar_export_grouped.py`
    - Test `_resolve_calendar_name` with parent ID: mock `list_subcalendars` to return `Calendar(name="Team Calendar")` → assert returns `"Team Calendar"`
    - Test `_resolve_calendar_name` with child ID: mock `list_subcalendars` to raise `CalendarNotFoundError` → assert falls back to event's `sub_calendar_name`
    - Test `_resolve_calendar_name` fallback chain: no events → returns raw `calendar_id`
    - Test `export_calendar_grouped` with parent ID: mock client, assert output file uses resolved parent name, metadata has correct `calendar_name`
    - Test `export_calendar_grouped` with child ID: mock client to raise `CalendarNotFoundError` on `list_subcalendars`, assert behavior matches `export_calendar`
    - Test `show_subcalendar=True` is used when events have multiple `sub_calendar_name` values (Markdown output contains `Calendar:` sub-bullets)
    - Test `show_subcalendar=False` is used when events have single `sub_calendar_name` (no `Calendar:` sub-bullets)
    - Test existing `export_calendar()` is unchanged (non-regression): call it and verify it does NOT call `list_subcalendars` for name resolution
    - Test MCP handler calls `export_calendar_grouped` (not `export_calendar`) — mock and assert
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.3, 5.4, 5.5, 5.6, 6.4_

- [x] 8. Checkpoint — Ensure unit tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Write property-based tests for correctness properties
  - [x] 9.1 Write property test for grouped name resolution (Property 1)
    - **Property 13: Grouped export resolves parent calendar name for unified output**
    - **Validates: Requirements 1.1, 1.2, 4.1**
    - Generate random parent calendar names (non-empty strings) and calendar IDs
    - Mock `list_subcalendars` to return a `Calendar` with the generated name
    - Mock `get_events` to return a list of events from multiple subcalendars
    - Call `export_calendar_grouped` and parse the output file
    - Assert: JSON metadata `calendar_name` equals the parent name; output filename stem equals `_sanitize_calendar_name(parent_name)`
    - Place at `confluence-ai/tests/property/test_prop13_grouped_name_resolution.py`
  - [x] 9.2 Write property test for grouped event ordering (Property 2)
    - **Property 14: Grouped export events are sorted chronologically by start time**
    - **Validates: Requirements 2.2**
    - Generate random lists of events with arbitrary start times from multiple subcalendars
    - Mock `get_events` to return the shuffled list; mock `list_subcalendars` to return a parent name
    - Call `export_calendar_grouped` with `output_format="json"`, parse the JSON output
    - Assert: for all consecutive pairs in the `events` array, `events[i].start <= events[i+1].start`
    - Place at `confluence-ai/tests/property/test_prop14_grouped_event_ordering.py`
  - [x] 9.3 Write property test for subcalendar provenance (Property 3)
    - **Property 15: Markdown subcalendar provenance sub-bullet appears when events come from multiple subcalendars**
    - **Validates: Requirements 3.3**
    - Generate events with at least 2 distinct `sub_calendar_name` values
    - Render with `CalendarMarkdownRenderer(show_subcalendar=True)`
    - Assert: for every event with a non-empty `sub_calendar_name`, the rendered output contains the substring `Calendar: {event.sub_calendar_name}`
    - Also test the negative: when all events share one `sub_calendar_name`, `CalendarMarkdownRenderer(show_subcalendar=False)` does NOT include `Calendar:` lines
    - Place at `confluence-ai/tests/property/test_prop15_subcalendar_provenance.py`
  - [x] 9.4 Write property test for grouped result invariants (Property 4)
    - **Property 16: Grouped export result invariants match export_calendar invariants**
    - **Validates: Requirements 5.3, 5.6**
    - Generate random event lists and calendar names
    - Mock `CalendarClient.get_events` and `list_subcalendars`
    - Call `export_calendar_grouped` with both `"json"` and `"markdown"` formats
    - Assert: (a) `os.path.exists(result.output_path)` is True, (b) `result.event_count == len(events)`, (c) `result.warnings` is a list, (d) the file is non-empty and parseable (JSON loads without error / Markdown starts with `---`)
    - Place at `confluence-ai/tests/property/test_prop16_grouped_result_invariants.py`

- [x] 10. Update integration test for MCP export_calendar tool
  - [x] 10.1 Update `confluence-ai/tests/integration/test_calendar_mcp_tools.py`
    - Add/update test case for `export_calendar` tool to verify it calls `export_calendar_grouped` internally
    - Mock `confluence_ai.export_calendar_grouped` (not `export_calendar`) in the MCP handler test
    - Assert the response includes `output_path`, `event_count`, and `warnings` fields
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP.
- Each top-level task is intended to be a single git commit using the workspace convention `feat(calendar-subcalendar-grouping): Task N — <short title>`.
- Checkpoints (tasks 4, 6, 8, 11) do not introduce new code; they are pauses to run the suite and surface questions before moving on.
- Property tests follow the repository's `test_propNN_*.py` naming convention and reuse the `ci` (100 examples) / `dev` (50 examples) Hypothesis profiles registered in `confluence-ai/tests/conftest.py`.
- The existing `export_calendar()` function is **unchanged** — no modifications to its logic or signature.
- The `CalendarJSONRenderer` is **unchanged** — it already includes `sub_calendar_id` and `sub_calendar_name` on each event.
- The `CalendarClient` is **unchanged** — `get_events` already handles parent→children auto-resolution.
- No new data models or exceptions are needed.
