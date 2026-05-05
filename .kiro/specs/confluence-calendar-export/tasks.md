# Implementation Plan: Confluence Calendar Export — Page-Driven Discovery Rewrite

## Overview

Convert the feature design into a series of prompts for a code-generation LLM that will implement each step with incremental progress. Make sure that each prompt builds on the previous prompts, and ends with wiring things together. There should be no hanging or orphaned code that isn't integrated into a previous step. Focus ONLY on tasks that involve writing, modifying, or testing code.

Implementation language: **Python 3.10+** (matches the existing `confluence-ai` and `aspice-check` packages). All code uses `from __future__ import annotations`, `@dataclass` models, and `str | None` union syntax.

This is a **delta update** to the existing implementation (Tasks 1–11 from the original spec are complete and committed). The changes replace the broken `?spaceKey=` calendar discovery with page-driven discovery via `subcalendars.json`, add mandatory headers, add `userTimeZoneId=UTC`, and implement parent → children auto-resolution in `get_events`.

**Files being modified (not created from scratch):**

- `confluence-ai/src/confluence_ai/calendar_client.py` — major rewrite
- `confluence-ai/src/confluence_ai/calendar_export.py` — minor update
- `confluence-ai/src/confluence_ai/models.py` — add `parent_id` field
- `aspice-check/src/aspice_check/mcp_tools.py` — update `LIST_CALENDARS_SCHEMA`
- `aspice-check/src/aspice_check/mcp_server.py` — update `_handle_list_calendars`

**Files unchanged:** `calendar_renderer.py`, `exceptions.py`, `__init__.py`

Conventions:

- Tests marked with `*` are optional (per workflow); core implementation tasks are never marked optional.
- Property-based tests use `hypothesis`; each property test file carries a module docstring of the form `"""Feature: confluence-calendar-export, Property N: <title>."""`.
- Property tests live under `confluence-ai/tests/property/` using the `test_propNN_*.py` naming convention.
- Unit tests live under `confluence-ai/tests/unit/` using the `test_<module>.py` convention.
- Integration tests live under `confluence-ai/tests/integration/`.
- No live Confluence calls — all HTTP is mocked with `pytest-mock` / fixture `Response` objects.

## Tasks

- [x] 1. Update data model — add `parent_id` to `SubCalendar`
  - [x] 1.1 Add `parent_id: str = ""` field to the `SubCalendar` dataclass in `confluence-ai/src/confluence_ai/models.py`
    - Add the field after `description` with default `""` so existing code that constructs `SubCalendar` without `parent_id` continues to work
    - This field maps to the `parentId` value from the `subcalendars.json` response's `childSubCalendars[].subCalendar.parentId`
    - _Requirements: 1.3, 2.2_

- [x] 2. Rewrite `CalendarClient` for page-driven discovery and mandatory headers
  - [x] 2.1 Add `_CALENDAR_HEADERS` class variable and update `__init__` to use `ConfluenceClient` + `URLParser`
    - Add `_CALENDAR_HEADERS: ClassVar[dict[str, str]] = {"Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest"}` as a class-level constant
    - Change `__init__` to construct an internal `ConfluenceClient` (from `confluence_ai.client`) for page fetching, and store a `URLParser` instance for URL parsing
    - Keep the `atlassian.Confluence` session construction for the authenticated `requests.Session` (used for calendar REST calls)
    - Store `self._confluence_client` and keep `self._session` and `self._base_url`
    - _Requirements: 1.8, 2.8_
  - [x] 2.2 Implement `_extract_parent_ids_from_body(storage_body: str) -> list[str]` helper
    - Use regex to find all `<ac:structured-macro ac:name="calendar">` elements and extract the `<ac:parameter ac:name="id">` value from each
    - Split comma-separated IDs, strip whitespace, deduplicate while preserving order, skip empty segments
    - Return an empty list if no calendar macros are found
    - _Requirements: 1.1, 1.4_
  - [x] 2.3 Implement `_map_subcalendars_payload(payload: list[dict]) -> list[Calendar]` helper
    - Map the `{payload: [{subCalendar: {...}, childSubCalendars: [{subCalendar: {...}}]}]}` response shape
    - For each entry: create a `Calendar` from `entry["subCalendar"]` fields (`id` → `calendar_id`, `name`, `type`, `spaceKey` → `space_key`, `description`)
    - For each child in `entry["childSubCalendars"]`: create a `SubCalendar` with `parent_id` set from `childSubCalendar["subCalendar"]["parentId"]`
    - Populate `Calendar.sub_calendars` with the child list
    - _Requirements: 1.2, 1.3_
  - [x] 2.4 Implement `_is_parent_response(data: dict) -> bool` helper
    - Return `True` iff `data.get("success") is True` and `"events" not in data`
    - This detects the parent-calendar response pattern from `events.json`
    - _Requirements: 2.2, 2.3_
  - [x] 2.5 Implement `_sort_calendars_case_insensitive(cals: list[Calendar]) -> list[Calendar]` helper
    - Sort the top-level list by `cal.name.casefold()`
    - Within each calendar, sort `cal.sub_calendars` by `sc.name.casefold()`
    - Return the sorted list (may sort in-place)
    - _Requirements: 1.9, 1.10_
  - [x] 2.6 Implement `list_calendars_from_page(self, page_url: str) -> list[Calendar]`
    - Step 1: `URLParser.parse(page_url)` → extract `page_id` (raise `InvalidURLError` on bad URL)
    - Step 2: `self._confluence_client.get_page(page_id)` → get `PageData` with `storage_format` and `space_key`
    - Step 3: `_extract_parent_ids_from_body(page_data.storage_format)` → list of parent IDs
    - Step 4: For each parent ID, call `self.list_subcalendars(parent_id, page_data.space_key)`
    - Step 5: Collect all `Calendar` results, apply `_sort_calendars_case_insensitive`, return
    - Return empty list if no calendar macros found (Requirement 1.6)
    - Raise `PageNotFoundError` if page fetch fails, `AuthenticationError` on 401
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.9, 1.10_
  - [x] 2.7 Implement `list_subcalendars(self, parent_id: str, space_key: str) -> Calendar`
    - Perform `GET {base_url}/rest/calendar-services/1.0/calendar/subcalendars.json?include={parent_id}&calendarContext=spaceCalendars&viewingSpaceKey={space_key}`
    - Include `_CALENDAR_HEADERS` on the request
    - Parse response JSON; call `_map_subcalendars_payload(data.get("payload", []))` and return the first Calendar (or raise `CalendarNotFoundError` if payload is empty)
    - Call `_handle_http_error` on non-2xx responses
    - _Requirements: 1.2, 1.3, 1.8_
  - [x] 2.8 Update `get_events` to use mandatory headers, `userTimeZoneId=UTC`, and parent → children auto-resolution
    - Add `_CALENDAR_HEADERS` to the GET request for `events.json`
    - Add `userTimeZoneId=UTC` query parameter to the URL
    - After receiving the response: if `_is_parent_response(data)` is True, call `list_subcalendars(calendar_id, space_key)` to discover children, then recursively call `get_events` on each child, aggregate results, and deduplicate by `event_id` (first occurrence wins)
    - The `space_key` for the subcalendars call is obtained from the parent's subcalendars.json response (`subCalendar.spaceKey`)
    - If response has an `events` key (even empty list), return mapped events directly — no fallback
    - _Requirements: 2.1, 2.2, 2.3, 2.8, 2.9_
  - [x] 2.9 Update `_handle_http_error` to detect `BAD_START_DATETIME` in 500 responses
    - If status is 500 and response body contains `BAD_START_DATETIME`, raise `CalendarAPIError` with hint message: "date range must use full ISO 8601 timestamps (YYYY-MM-DDTHH:MM:SSZ), not date-only"
    - Keep existing 401/403/404/other mappings unchanged
    - _Requirements: 2.8, 7.2_
  - [x] 2.10 Remove the old `list_calendars(space_key)` method
    - Delete the `list_calendars` method that used the broken `?spaceKey=` endpoint
    - The old `_map_calendar` static method can be removed or refactored into `_map_subcalendars_payload`
    - _Requirements: 1.1_

- [x] 3. Checkpoint — Ensure CalendarClient rewrite compiles and existing unit tests are updated
  - Ensure all tests pass, ask the user if questions arise.
  - Update any existing unit tests in `confluence-ai/tests/unit/test_calendar_client_errors.py` and `test_calendar_client_passthrough.py` that reference the old `list_calendars(space_key)` method or old URL patterns

- [x] 4. Update `calendar_export.py` for parent → children calendar name resolution
  - [x] 4.1 Update `export_calendar` to handle parent calendar name resolution
    - The `get_events` call now handles parent → children auto-resolution transparently (returns aggregated events)
    - Update calendar name resolution: if events come from multiple sub-calendars (different `sub_calendar_name` values), use the parent calendar's name from `list_subcalendars` metadata; otherwise use the first event's `sub_calendar_name` as before; fall back to `calendar_id`
    - No signature change — the function still accepts `calendar_id` (which may be a parent or child ID)
    - _Requirements: 5.6, 2.2_

- [x] 5. Update MCP tools schema and handler for page-driven discovery
  - [x] 5.1 Update `LIST_CALENDARS_SCHEMA` in `aspice-check/src/aspice_check/mcp_tools.py`
    - Replace `space_key` (required) with `page_url` (required, type string, description: "Full Confluence page URL containing calendar macros")
    - Keep `base_url`, `email`, `api_token` parameters unchanged
    - Update the schema description to: "List available calendars in a Confluence space by reading calendar macros from a page"
    - _Requirements: 6.6, 6.7_
  - [x] 5.2 Update `_handle_list_calendars` in `aspice-check/src/aspice_check/mcp_server.py`
    - Change from `client.list_calendars(params["space_key"])` to `client.list_calendars_from_page(params["page_url"])`
    - Keep the rest of the handler logic unchanged (CalendarClient construction, `asdict` serialization)
    - _Requirements: 6.6, 6.7_

- [x] 6. Checkpoint — Ensure MCP schema and handler changes work end-to-end
  - Ensure all tests pass, ask the user if questions arise.
  - Update the existing integration test in `confluence-ai/tests/integration/test_calendar_mcp_tools.py` to use `page_url` instead of `space_key` in the `list_calendars` tool call

- [x] 7. Update existing unit tests for the rewritten CalendarClient
  - [x] 7.1 Update `confluence-ai/tests/unit/test_calendar_client_errors.py`
    - Update test setup to account for the new `__init__` that uses `ConfluenceClient` internally
    - Keep error mapping assertions (401 → AuthenticationError, 403/404 → CalendarNotFoundError, 500 → CalendarAPIError)
    - Add a test for the `BAD_START_DATETIME` hint on 500 responses
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [x] 7.2 Update `confluence-ai/tests/unit/test_calendar_client_passthrough.py`
    - Replace tests for the old `list_calendars(space_key)` URL with tests for `list_subcalendars` URL construction
    - Assert `subcalendars.json` URL includes `include={parent_id}`, `calendarContext=spaceCalendars`, `viewingSpaceKey={space_key}`
    - Assert `events.json` URL includes `userTimeZoneId=UTC` parameter
    - Assert `_CALENDAR_HEADERS` are sent on every request
    - _Requirements: 1.8, 2.8, 2.9_
  - [x] 7.3 Add `confluence-ai/tests/unit/test_calendar_client_discovery.py` for page-driven discovery
    - Mock `ConfluenceClient.get_page` to return a `PageData` with a storage body containing calendar macros
    - Mock `list_subcalendars` to return Calendar objects
    - Assert `list_calendars_from_page` returns the expected sorted calendar tree
    - Test edge cases: page with no macros (returns empty list), page with comma-separated IDs, invalid page URL
    - _Requirements: 1.1, 1.4, 1.5, 1.6, 1.9, 1.10_

- [x] 8. Checkpoint — Ensure all unit tests pass with the rewritten client
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Add property-based tests for new/updated properties
  - [x] 9.1 Write property test for `_map_subcalendars_payload` (Property 1)
    - **Property 1: `_map_subcalendars_payload` preserves fields and sorts both levels case-insensitively**
    - **Validates: Requirements 1.3, 1.9, 1.10**
    - Generate random `subcalendars.json` payloads with N parents × M_i children using a `st_subcalendars_payload()` strategy
    - Apply `_map_subcalendars_payload` then `_sort_calendars_case_insensitive`; assert field preservation, correct `parent_id` on children, and both levels sorted by `name.casefold()`
    - Place the file at `confluence-ai/tests/property/test_prop01_subcalendars_mapping.py`
  - [x] 9.2 Write property test for `_extract_parent_ids_from_body` (Property 2)
    - **Property 2: Macro extraction returns all comma-separated IDs from every calendar macro**
    - **Validates: Requirements 1.1, 1.4**
    - Generate synthetic XHTML bodies with N calendar macros containing random comma-separated IDs
    - Assert the returned list equals the in-order, deduplicated concatenation of all IDs
    - Place the file at `confluence-ai/tests/property/test_prop02_macro_extraction.py`
  - [x] 9.3 Update property test for event mapping (Property 3)
    - **Property 3: Event response mapping is field-complete and timezone-aware**
    - **Validates: Requirements 2.4**
    - Update `confluence-ai/tests/property/test_prop03_event_mapping.py` (was `test_prop02_event_mapping.py`) to reference the current `_map_event` method
    - Ensure the test still validates: all string fields are `str` (not None), `start`/`end` are tz-aware, `end >= start`, `all_day` is bool
    - Rename file if needed to match new numbering
  - [x] 9.4 Write property test for `get_events` passthrough (Property 4)
    - **Property 4: `get_events` passes through the plugin's event list for a child calendar**
    - **Validates: Requirements 2.1**
    - Mock `events.json` to return `{"events": D}` for a child calendar; assert `get_events` returns exactly `len(D)` events in the same order with no filtering
    - Place the file at `confluence-ai/tests/property/test_prop04_get_events_passthrough.py`
  - [x] 9.5 Keep/update property test for JSON round-trip (Property 5)
    - **Property 5: JSON render + parse round-trips events and metadata**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
    - Existing `test_prop04_json_roundtrip.py` — rename to `test_prop05_json_roundtrip.py` if needed; no logic changes required (renderers are unchanged)
  - [x] 9.6 Keep/update property test for Markdown front-matter (Property 6)
    - **Property 6: Markdown front-matter parses to the original metadata**
    - **Validates: Requirements 4.1**
    - Existing `test_prop05_markdown_frontmatter.py` — rename to `test_prop06_markdown_frontmatter.py` if needed; no logic changes required
  - [x] 9.7 Keep/update property test for Markdown ordering (Property 7)
    - **Property 7: Markdown events render grouped and chronologically ordered**
    - **Validates: Requirements 4.2, 4.3**
    - Existing `test_prop06_markdown_ordering.py` — rename to `test_prop07_markdown_ordering.py` if needed; no logic changes required
  - [x] 9.8 Keep/update property test for all-day dichotomy (Property 8)
    - **Property 8: All-day vs timed event rendering dichotomy**
    - **Validates: Requirements 4.4**
    - Existing `test_prop07_allday_dichotomy.py` — rename to `test_prop08_allday_dichotomy.py` if needed; no logic changes required
  - [x] 9.9 Keep/update property test for filename sanitization (Property 9)
    - **Property 9: Calendar filename sanitization produces filesystem-safe names**
    - **Validates: Requirements 5.5**
    - Existing `test_prop08_filename_sanitization.py` — rename to `test_prop09_filename_sanitization.py` if needed; no logic changes required
  - [x] 9.10 Keep/update property test for export result invariants (Property 10)
    - **Property 10: `export_calendar` result invariants**
    - **Validates: Requirements 5.3**
    - Existing `test_prop09_export_result.py` — rename to `test_prop10_export_result.py` if needed; update mocks if CalendarClient constructor changed
  - [x] 9.11 Write property test for parent → children fallback (Property 11)
    - **Property 11: Parent → children fallback triggers on the no-events response and aggregates deduped child events**
    - **Validates: Requirements 2.2, 2.3, 5.6**
    - Generate a parent ID P with K children, each holding event lists (possibly overlapping by `event_id`)
    - Mock initial `get_events(P)` to return `{"success": true}` (no `events` key); mock `list_subcalendars` to return children; mock child `get_events` calls
    - Assert returned events equal the union of all children's events, deduplicated by `event_id` (first occurrence wins)
    - Also test the non-trigger case: `{"events": []}` should NOT trigger fallback
    - Place the file at `confluence-ai/tests/property/test_prop11_parent_fallback.py`
  - [x] 9.12 Write property test for mandatory headers and parameters (Property 12)
    - **Property 12: Every calendar REST request carries the required headers and parameters**
    - **Validates: Requirements 1.8, 2.8, 2.9**
    - Mock the session to record all request headers and URLs
    - Invoke `list_calendars_from_page`, `list_subcalendars`, and `get_events`
    - Assert every request has `X-Requested-With: XMLHttpRequest` and `Accept: application/json, text/javascript, */*; q=0.01`
    - Assert `events.json` requests include `userTimeZoneId=UTC` in the query string
    - Place the file at `confluence-ai/tests/property/test_prop12_request_invariants.py`

- [x] 10. Update integration test for MCP calendar tools
  - [x] 10.1 Update `confluence-ai/tests/integration/test_calendar_mcp_tools.py`
    - Change the `list_calendars` tool call to pass `page_url` instead of `space_key`
    - Update the mock from `CalendarClient.list_calendars` to `CalendarClient.list_calendars_from_page`
    - Assert the `tools/list` response shows the updated `LIST_CALENDARS_SCHEMA` with `page_url` as required
    - Keep the `export_calendar` tool call tests unchanged (schema is the same)
    - Assert missing `page_url` returns `-32602` validation error
    - _Requirements: 6.6, 6.7, 6.8_

- [-] 11. Final checkpoint — Ensure the whole feature is green
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP, but every correctness property in design § Correctness Properties is captured as its own optional sub-task so it can be picked up individually.
- Each top-level task is intended to be a single git commit using the workspace convention `feat(confluence-calendar-export): Task N — <short title>`.
- Checkpoints (tasks 3, 6, 8, 11) do not introduce new code; they are pauses to run the suite and surface questions before moving on.
- Property tests follow the repository's `test_propNN_*.py` naming convention and reuse the `ci` (100 examples) / `dev` (50 examples) Hypothesis profiles registered in `confluence-ai/tests/conftest.py`.
- The renderers (`CalendarJSONRenderer`, `CalendarMarkdownRenderer`) are **unchanged** — no tasks needed.
- The exceptions (`CalendarNotFoundError`, `CalendarAPIError`) are **unchanged** — no tasks needed.
- The public API surface (`__init__.py`) is **unchanged** — no tasks needed.
- After all tasks are complete, the feature uses page-driven discovery via `list_calendars_from_page(page_url)` and the MCP `list_calendars` tool accepts `page_url` instead of `space_key`.
