# Implementation Plan: Confluence Calendar Export

## Overview

Convert the feature design into a series of prompts for a code-generation LLM that will implement each step with incremental progress. Make sure that each prompt builds on the previous prompts, and ends with wiring things together. There should be no hanging or orphaned code that isn't integrated into a previous step. Focus ONLY on tasks that involve writing, modifying, or testing code.

Implementation language: **Python 3.10+** (matches the existing `confluence-ai` and `aspice-check` packages). All code uses `from __future__ import annotations`, `@dataclass` models, and `str | None` union syntax.

The feature ships in two packages:

- `confluence-ai/src/confluence_ai/` — calendar library code (models, client, renderers, orchestration) plus tests under `confluence-ai/tests/{unit,property,integration}/`.
- `aspice-check/src/aspice_check/` — MCP schema declarations and MCP server handlers.

Tasks are ordered for incremental validation: skeleton (models + exceptions) → client → renderers → orchestration → public API → MCP surface → property-based tests → integration. Each top-level task is a single self-contained commit.

Conventions:

- Tests marked with `*` are optional (per workflow); core implementation tasks are never marked optional.
- Property-based tests use `hypothesis`; each property test file carries a module docstring of the form `"""Feature: confluence-calendar-export, Property N: <title>."""`.
- Property tests live under `confluence-ai/tests/property/` using the `test_propNN_*.py` naming convention.
- Unit tests live under `confluence-ai/tests/unit/` using the `test_<module>.py` convention.
- Integration tests live under `confluence-ai/tests/integration/`.
- No live Confluence calls — all HTTP is mocked with `pytest-mock` / fixture `Response` objects.

## Tasks

- [x] 1. Add calendar data models and exception classes
  - [x] 1.1 Extend `confluence-ai/src/confluence_ai/models.py` with calendar dataclasses
    - Add a new "Calendar Models" section at the bottom of the file
    - Add `DateRange`, `SubCalendar`, `Calendar`, `Event`, `CalendarMetadata`, `CalendarExportResult` dataclasses matching the field definitions in design § Data Models
    - Use `from __future__ import annotations` (already present) and `datetime` from stdlib
    - Keep defaults aligned with the design (e.g., `Event.all_day: bool = False`, empty-string defaults for optional text fields, `list[...] = field(default_factory=list)` for sub_calendars / warnings)
    - _Requirements: 2.3, 5.3, 8.2_
  - [x] 1.2 Extend `confluence-ai/src/confluence_ai/exceptions.py` with calendar exceptions
    - Add `CalendarNotFoundError(ExporterError)` with `calendar_id`, `status_code`, and `message` constructor parameters and the HTTP-403-aware default message defined in design § Error Handling
    - Add `CalendarAPIError(ExporterError)` with `endpoint`, `status_code`, and `message` constructor parameters
    - Both subclass `ExporterError` so existing `except ExporterError:` blocks cover them
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [x] 1.3 Write unit tests for the new exception classes
    - Assert `CalendarNotFoundError` exposes `calendar_id` and `status_code` attributes
    - Assert the HTTP 403 message branch names access-denied and quotes the calendar id
    - Assert `CalendarAPIError` exposes `endpoint` and `status_code` attributes
    - Assert both subclass `ExporterError`
    - Place the file at `confluence-ai/tests/unit/test_calendar_exceptions.py`
    - _Requirements: 7.3, 7.4_

- [x] 2. Implement `CalendarClient` REST wrapper with unit tests for error mapping
  - [x] 2.1 Create `confluence-ai/src/confluence_ai/calendar_client.py` skeleton
    - Add module docstring referencing requirements 1.1–1.4, 2.1–2.6, 7.1–7.4
    - Define `class CalendarClient` with `__init__(self, base_url: str, email: str, api_token: str)`
    - In `__init__`, construct an internal `atlassian.Confluence` object (matching `ConfluenceClient`) purely to reuse its authenticated `requests.Session`; catch `requests.exceptions.ConnectionError` and raise `ConfluenceConnectionError`
    - Expose `self._session` and `self._base_url` for use by the two endpoint methods
    - _Requirements: 1.4, 7.1_
  - [x] 2.2 Implement `CalendarClient.list_calendars(space_key)` and `_map_calendar`
    - Perform `GET {base_url}/rest/calendar-services/1.0/calendar?spaceKey={space_key}` via the shared session
    - Call `_handle_http_error` on non-2xx responses (401 → `AuthenticationError`, 403/404 → `CalendarNotFoundError`, else `CalendarAPIError`)
    - Implement `_map_calendar(raw: dict) -> Calendar`: maps `subCalendarId` → `calendar_id`, preserves `name`/`type`/`spaceKey`/`description`, recursively maps nested `subCalendars` to `SubCalendar` instances in order
    - Return `list[Calendar]`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 7.1, 7.2_
  - [x] 2.3 Implement `CalendarClient.get_events(calendar_id, date_range)` and `_map_event`
    - Perform `GET {base_url}/rest/calendar-services/1.0/calendar/events.json?subCalendarId={calendar_id}&start={iso}&end={iso}` using `date_range.start.isoformat()` / `date_range.end.isoformat()`
    - Call `_handle_http_error` on non-2xx responses, passing `calendar_id` so 404 maps to `CalendarNotFoundError`
    - Implement `_map_event(raw: dict) -> Event`: maps `id` → `event_id`, `title` → `summary`, `allDay` → `all_day`, `organizer.email` or `organizer.displayName` → `organizer`, `subCalendarId`/`subCalendarName` → `sub_calendar_id`/`sub_calendar_name`; parse `start`/`end` as tz-aware `datetime` (normalise naive timestamps to UTC); default missing string fields to `""` and missing booleans to `False`
    - Return a flat `list[Event]` from the response `events` array (recurring events are already expanded server-side)
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6, 7.2_
  - [x] 2.4 Implement `_handle_http_error(exc, *, calendar_id=None, endpoint=None)`
    - Mirror the shape of `ConfluenceClient._handle_http_error`
    - Map 401 → `AuthenticationError(base_url=self._base_url, status_code=401)`
    - Map 403/404 → `CalendarNotFoundError(calendar_id=calendar_id or "", status_code=status)`
    - All other non-2xx → `CalendarAPIError(endpoint=endpoint or "", status_code=status)`
    - Translate `RequestsConnectionError` to `ConfluenceConnectionError`
    - _Requirements: 1.3, 1.4, 2.5, 7.1, 7.2_
  - [x] 2.5 Write unit tests for `CalendarClient` error mapping
    - Use `pytest-mock` to stub the session's `get` method to return `Response` objects with 401 / 403 / 404 / 500 status codes
    - Assert 401 raises `AuthenticationError`, 403 and 404 raise `CalendarNotFoundError` with the right `calendar_id`, 500 raises `CalendarAPIError` with the right `endpoint`
    - Place the file at `confluence-ai/tests/unit/test_calendar_client_errors.py`
    - _Requirements: 1.3, 1.4, 2.5, 7.1, 7.2_
  - [x] 2.6 Write unit tests for `CalendarClient` query-string and sub-calendar passthrough
    - Capture the URL passed to the stubbed session `get`; assert `spaceKey`, `subCalendarId`, `start`, `end` query params match inputs exactly
    - Include a test that a sub-calendar ID is accepted as `calendar_id` (same parameter name)
    - Place the file at `confluence-ai/tests/unit/test_calendar_client_passthrough.py`
    - _Requirements: 2.1, 2.2_

- [x] 3. Checkpoint - Ensure all client tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement JSON and Markdown calendar renderers
  - [x] 4.1 Create `confluence-ai/src/confluence_ai/calendar_renderer.py` with `CalendarJSONRenderer`
    - Implement `render(events: list[Event], metadata: CalendarMetadata) -> str`
    - Emit `{ "metadata": {...}, "events": [...] }` with `indent=2`, `ensure_ascii=False` (matching the existing `JSONRenderer`)
    - Serialise `datetime` fields via `isoformat()`, ensuring `tzinfo` is always set (normalise naive → UTC before serialising)
    - Serialise `DateRange` as `{ "start": ISO8601, "end": ISO8601 }`
    - Set `metadata.event_count = len(events)` before serialising (invariant 4)
    - Include all `Event` fields: `event_id`, `summary`, `start`, `end`, `all_day`, `description`, `location`, `organizer`, `sub_calendar_id`, `sub_calendar_name`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [x] 4.2 Add `CalendarMarkdownRenderer` to the same module
    - Implement `render(events: list[Event], metadata: CalendarMetadata) -> str`
    - Emit YAML front-matter block (`---\n...\n---\n`) containing `calendar_id`, `calendar_name`, `export_timestamp`, `exporter_version`, `date_range.start`/`date_range.end` (as `YYYY-MM-DD`), `event_count`
    - Emit an H1 heading: `# {calendar_name}`
    - Group events by `local_date(event.start)`; sort groups ascending by date; within a group sort ascending by `start` then `summary`
    - All-day event line: `- **{summary}**  —  All day`
    - Timed event line: `- **{summary}**  —  {HH:MM} – {HH:MM} {TZNAME}` using an en-dash (U+2013)
    - Emit optional sub-bullets only when non-empty: `Location:`, `Organizer:`, `Description:` (first line; wrap multi-line descriptions in a blockquote)
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  - [x] 4.3 Write unit tests for the JSON renderer
    - Assert the output round-trips through `json.loads` to a dict with `metadata` and `events` keys
    - Assert `metadata.event_count` in the parsed output equals `len(events)`
    - Assert `datetime` fields parse back via `datetime.fromisoformat` to the same UTC instant
    - Place the file at `confluence-ai/tests/unit/test_calendar_renderer_json.py`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [x] 4.4 Write unit tests for the Markdown renderer
    - Assert the output starts with a `---\n` line and contains a closing `---\n`
    - Assert the YAML block parses with `yaml.safe_load` to a dict with the required keys
    - Assert an H1 `# {calendar_name}` line is present
    - Assert all-day events render `"All day"` and no `HH:MM` substring; timed events render two `HH:MM` substrings and no `"All day"`
    - Place the file at `confluence-ai/tests/unit/test_calendar_renderer_markdown.py`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 5. Implement `export_calendar` orchestration
  - [x] 5.1 Create `confluence-ai/src/confluence_ai/calendar_export.py`
    - Define `export_calendar(*, base_url, calendar_id, output_dir, email, api_token, output_format="json", date_range=None) -> CalendarExportResult`
    - Step 1: credential validation — raise `AuthenticationError(base_url, message="email required")` / `"api_token required"` on empty values
    - Step 2: resolve default `DateRange` when `None`: `datetime.now(UTC) - 30 days` → `datetime.now(UTC) + 90 days`
    - Step 3: construct `CalendarClient`
    - Step 4: resolve `calendar_name` — after fetching events, use the first event's `sub_calendar_name` if present, else fall back to `calendar_id`
    - Step 5: call `client.get_events(calendar_id, date_range)`
    - Step 6: select renderer based on `output_format` (`"json"` → `CalendarJSONRenderer`, `"markdown"` → `CalendarMarkdownRenderer`); raise `ValueError` listing valid formats on unknown values
    - Step 7: build `CalendarMetadata` with `export_timestamp = datetime.now(UTC).isoformat()`, `exporter_version = confluence_ai.__version__`, and `event_count = len(events)`
    - Step 8: `os.makedirs(output_dir, exist_ok=True)`; compute filename via `_sanitize_calendar_name(calendar_name) + "." + ("json"|"md")`; write file with `encoding="utf-8"`
    - Step 9: return `CalendarExportResult(output_path=..., event_count=len(events), warnings=[])`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [x] 5.2 Add `_sanitize_calendar_name(name: str) -> str` helper to the same module
    - Replace spaces with `_`; strip any character not in `[A-Za-z0-9_\-]` via `re.sub`
    - Fall back to the literal `"calendar"` when the result would be empty
    - _Requirements: 5.5_
  - [x] 5.3 Write unit tests for `export_calendar` defaults and orchestration
    - Mock `CalendarClient` via `pytest-mock`; assert that `date_range=None` resolves to now-30d → now+90d within a small tolerance
    - Assert that `export_calendar` returns a `CalendarExportResult` with `os.path.exists(result.output_path)`, `event_count == len(events)`, `warnings` is a list
    - Assert that `output_format="markdown"` writes a `.md` file and `output_format="json"` writes a `.json` file
    - Assert that empty `email` / `api_token` raise `AuthenticationError`
    - Place the file at `confluence-ai/tests/unit/test_calendar_export_defaults.py`
    - _Requirements: 2.4, 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 6. Expose new API in `confluence_ai/__init__.py`
  - [x] 6.1 Extend `confluence-ai/src/confluence_ai/__init__.py` with the new public surface
    - Import and re-export `export_calendar` from `confluence_ai.calendar_export`
    - Import and re-export `Calendar`, `SubCalendar`, `Event`, `DateRange`, `CalendarMetadata`, `CalendarExportResult` from `confluence_ai.models`
    - Import and re-export `CalendarNotFoundError`, `CalendarAPIError` from `confluence_ai.exceptions`
    - Append every new name to `__all__`; do not remove or rename any existing entry
    - _Requirements: 8.1, 8.2, 8.3_
  - [x] 6.2 Write smoke tests for the public API surface
    - Assert `from confluence_ai import export_calendar, Calendar, Event, DateRange, CalendarMetadata, CalendarExportResult, CalendarNotFoundError, CalendarAPIError` succeeds
    - Assert each name is present in `confluence_ai.__all__`
    - Assert no existing public name was removed (spot-check `export_page`, `publish_page`, `ExportResult`, `PageMetadata`)
    - Place the file at `confluence-ai/tests/unit/test_public_api.py`
    - _Requirements: 8.1, 8.2, 8.3_

- [x] 7. Wire calendar tools into the aspice-check MCP server
  - [x] 7.1 Add `EXPORT_CALENDAR_SCHEMA` and `LIST_CALENDARS_SCHEMA` to `aspice-check/src/aspice_check/mcp_tools.py`
    - Follow the same dict shape as `EXPORT_PAGE_SCHEMA` (top-level `name`, `description`, `inputSchema`)
    - `EXPORT_CALENDAR_SCHEMA` parameters: `base_url` (str, required), `calendar_id` (str, required), `output_dir` (str, required), `output_format` (enum `["json","markdown"]`, default `"json"`), `start_date` (str, ISO 8601, optional), `end_date` (str, ISO 8601, optional), `email` (str, optional), `api_token` (str, optional)
    - `LIST_CALENDARS_SCHEMA` parameters: `base_url` (str, required), `space_key` (str, required), `email` (str, optional), `api_token` (str, optional)
    - Append both schemas to `ALL_TOOL_SCHEMAS`
    - _Requirements: 6.1, 6.2, 6.6_
  - [x] 7.2 Register handlers in `aspice-check/src/aspice_check/mcp_server.py`
    - Extend `self._tool_handlers` in `AspiceMCPServer.__init__` with `"list_calendars": self._handle_list_calendars` and `"export_calendar": self._handle_export_calendar`
    - Update the module import list at the top of the file to include `EXPORT_CALENDAR_SCHEMA` and `LIST_CALENDARS_SCHEMA` from `aspice_check.mcp_tools`
    - _Requirements: 6.1, 6.6_
  - [x] 7.3 Implement `_handle_list_calendars(self, params: dict) -> dict`
    - Construct `confluence_ai.calendar_client.CalendarClient(base_url=..., email=params.get("email") or os.environ.get("CONFLUENCE_EMAIL",""), api_token=params.get("api_token") or os.environ.get("CONFLUENCE_API_TOKEN",""))`
    - Call `client.list_calendars(params["space_key"])`
    - Return `{"calendars": [asdict(c) for c in calendars]}` (import `asdict` from `dataclasses` at module top)
    - _Requirements: 6.3, 6.4, 6.6_
  - [x] 7.4 Implement `_handle_export_calendar(self, params: dict) -> dict`
    - Parse optional `start_date`/`end_date` into a `DateRange` via `datetime.fromisoformat`; leave `date_range=None` when either is missing
    - Call `confluence_ai.export_calendar(...)` with base_url, calendar_id, output_dir, output_format (default `"json"`), date_range, email/api_token fallbacks via env vars
    - Return `{"output_path": result.output_path, "event_count": result.event_count, "warnings": result.warnings}`
    - Rely on the existing dispatcher's `_make_error_response` to translate exceptions into JSON-RPC error `-32603`
    - _Requirements: 6.1, 6.3, 6.4, 6.5_

- [x] 8. Checkpoint - Ensure implementation is wired end to end
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Add property-based tests for the calendar feature
  - [x] 9.1 Property 1 — Calendar response mapping preserves IDs, names, and sub-calendar structure
    - **Property 1: Calendar response mapping preserves IDs, names, and sub-calendar structure**
    - **Validates: Requirements 1.1, 1.2**
    - Generate random plugin calendar JSON arrays (N parents × M_i sub-calendars) via `hypothesis` strategies
    - Apply `CalendarClient._map_calendar` and assert every `calendar_id`/`name`/`type` equals the input and sub-calendar lists match in length and order
    - Place the file at `confluence-ai/tests/property/test_prop01_calendar_mapping.py`
  - [x] 9.2 Property 2 — Event response mapping is field-complete, timezone-aware, and one-per-occurrence
    - **Property 2: Event response mapping is field-complete, timezone-aware, and one-per-occurrence**
    - **Validates: Requirements 2.3, 2.6**
    - Generate K raw event dicts (including duplicates for recurrence occurrences) via a `st_plugin_event_dict()` strategy
    - Stub `CalendarClient.get_events` HTTP call to return those K events; assert K `Event` instances come back, each with non-None fields, tz-aware `start`/`end`, `end >= start`, and boolean `all_day`
    - Place the file at `confluence-ai/tests/property/test_prop02_event_mapping.py`
  - [x] 9.3 Property 3 — Date-range filtering returns only overlapping events
    - **Property 3: Date-range filtering returns only overlapping events**
    - **Validates: Requirements 2.1**
    - Generate a universe U of events and a `DateRange` R where `R.end > R.start`
    - Stub the plugin response with U; assert the returned events are exactly those satisfying `e.end > R.start AND e.start < R.end`
    - Place the file at `confluence-ai/tests/property/test_prop03_daterange_overlap.py`
  - [x] 9.4 Property 4 — JSON render + parse round-trips events and metadata
    - **Property 4: JSON render + parse round-trips events and metadata**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
    - Generate `CalendarMetadata` M and `list[Event]` E; render via `CalendarJSONRenderer`
    - Parse with `json.loads`; assert `metadata` contains every field of M (dates compared by UTC instant); assert `events` has length `len(E)` and each element matches E by field (datetimes parsed via `datetime.fromisoformat`)
    - Place the file at `confluence-ai/tests/property/test_prop04_json_roundtrip.py`
  - [x] 9.5 Property 5 — Markdown front-matter parses to the original metadata
    - **Property 5: Markdown front-matter parses to the original metadata**
    - **Validates: Requirements 4.1**
    - Generate M and E, render via `CalendarMarkdownRenderer`
    - Extract the `---\n...\n---\n` block, parse with `yaml.safe_load`; assert every required field (`calendar_id`, `calendar_name`, `export_timestamp`, `exporter_version`, `date_range.start`, `date_range.end`, `event_count`) equals M's values (dates compared as `YYYY-MM-DD`, `event_count` as int)
    - Place the file at `confluence-ai/tests/property/test_prop05_markdown_frontmatter.py`
  - [x] 9.6 Property 6 — Markdown events render grouped and chronologically ordered
    - **Property 6: Markdown events render grouped and chronologically ordered**
    - **Validates: Requirements 4.2, 4.3**
    - Generate `list[Event]` E in any input order; render markdown
    - Parse `## YYYY-MM-DD` headers and their bullets; assert one header per distinct local date of `E[*].start`, headers strictly ascending, bullets within a group ascending by `start`, and every `e.summary` appears at least once in the output
    - Place the file at `confluence-ai/tests/property/test_prop06_markdown_ordering.py`
  - [x] 9.7 Property 7 — All-day vs timed event rendering dichotomy
    - **Property 7: All-day vs timed event rendering dichotomy**
    - **Validates: Requirements 4.4**
    - Generate individual `Event` instances with `all_day ∈ {True, False}`; render each and locate its bullet line in the output
    - Assert: `all_day == True` → line contains `"All day"` and no `HH:MM` substring; `all_day == False` → line contains two `HH:MM` substrings separated by an en-dash and no `"All day"`
    - Place the file at `confluence-ai/tests/property/test_prop07_allday_dichotomy.py`
  - [x] 9.8 Property 8 — Calendar filename sanitization produces filesystem-safe names
    - **Property 8: Calendar filename sanitization produces filesystem-safe names**
    - **Validates: Requirements 5.5**
    - Generate arbitrary `str` inputs (including Unicode, control chars, whitespace); call `_sanitize_calendar_name`
    - Assert `re.fullmatch(r"[A-Za-z0-9_\-]+", r)` matches OR `r == "calendar"`; assert no whitespace characters in `r`; assert every allowed character in input is preserved and spaces become `_` at the same relative position
    - Place the file at `confluence-ai/tests/property/test_prop08_filename_sanitization.py`
  - [x] 9.9 Property 9 — `export_calendar` result invariants
    - **Property 9: `export_calendar` result invariants**
    - **Validates: Requirements 5.3, 6.6**
    - Generate a random list of events E; patch `CalendarClient` (via `pytest-mock`) to return E; call `export_calendar(...)` against a `tmp_path` output directory for both formats
    - Assert `os.path.exists(result.output_path)`, `result.event_count == len(E)`, `result.warnings` is a `list`, and the file parses successfully (`json.loads` for JSON; contains a `---\n...\n---\n` YAML block for Markdown)
    - Place the file at `confluence-ai/tests/property/test_prop09_export_result.py`

- [x] 10. Add an integration test for the two MCP calendar tools
  - [x] 10.1 Write `confluence-ai/tests/integration/test_calendar_mcp_tools.py`
    - Instantiate `aspice_check.mcp_server.AspiceMCPServer()` directly
    - Send a `tools/list` JSON-RPC request via `_handle_request`; assert both `list_calendars` and `export_calendar` appear in the returned tools array with their input schemas
    - Patch `confluence_ai.calendar_client.CalendarClient.list_calendars` and `confluence_ai.export_calendar` with `pytest-mock` so no real HTTP is attempted
    - Send a `tools/call` request for `list_calendars`; assert the result wraps `{"calendars": [...]}` in the MCP content envelope
    - Send a `tools/call` request for `export_calendar` (writing to `tmp_path`); assert the result includes `output_path`, `event_count`, and `warnings`
    - Send a `tools/call` with a missing required parameter; assert the response carries the `-32602` `Invalid params` error path from the existing dispatcher
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 11. Final checkpoint - Ensure the whole feature is green
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP, but every correctness property in design § Correctness Properties is captured as its own optional sub-task here so it can be picked up individually.
- Each top-level task is intended to be a single git commit using the workspace convention `feat(confluence-calendar-export): Task N — <short title>`.
- Checkpoints (tasks 3, 8, 11) do not introduce new code; they are pauses to run the suite and surface questions before moving on.
- Property tests follow the repository's `test_propNN_*.py` naming convention and reuse the `ci` (100 examples) / `dev` (50 examples) Hypothesis profiles registered in `confluence-ai/tests/conftest.py`.
- No CLI command is added in this feature, matching the existing `confluence-ai` surface (library + MCP only).
- After all tasks are complete, the feature is exercised exclusively via `confluence_ai.export_calendar(...)` and the two new MCP tools (`list_calendars`, `export_calendar`) in `AspiceMCPServer`.
