# Requirements Document

## Introduction

This feature extends the confluence-ai library and the existing aspice-check MCP server to support exporting calendar event data from Confluence Cloud Team Calendars. The Confluence Calendar plugin exposes an unofficial REST API (`/rest/calendar-services/1.0/`). This feature adds a calendar client, event models, export orchestration (to JSON and Markdown formats), and MCP tools for calendar discovery and export. Matching the existing confluence-ai approach (which has no CLI today), calendar export is exposed only through the library API and MCP tools — no new CLI command is added.

**Important discovery:** The documented `/rest/calendar-services/1.0/calendar?spaceKey=...` endpoint returns HTTP 500 on Atlassian Cloud. Calendar discovery instead works by reading calendar macro IDs from a Confluence page's storage format body and resolving them via the `subcalendars.json` endpoint. Events live exclusively in child sub-calendars, not parent calendars.

## Glossary

- **Calendar_Client**: The module responsible for communicating with the Confluence Calendar REST API to retrieve calendar metadata and events.
- **Calendar_Exporter**: The orchestration module that coordinates retrieval, filtering, and rendering of calendar events into output files.
- **Event**: A single calendar entry with a summary, start time, end time, optional description, location, and organizer.
- **Sub_Calendar**: A child calendar within a parent Team Calendar that manages a specific event type (e.g., Leave, Travel, Custom Events). Events live in child sub-calendars, not parent calendars.
- **Parent_Calendar**: A top-level calendar referenced by a page macro. Contains no events directly; instead holds child Sub_Calendars that contain events.
- **Calendar_Macro**: An `<ac:structured-macro ac:name="calendar">` element in a Confluence page's storage format body. Its `id` parameter contains comma-separated parent calendar IDs.
- **Calendar_Renderer**: A component that transforms internal event models into a specific output format (JSON or Markdown).
- **Date_Range**: A time window defined by a start date and end date used to filter which events are retrieved.
- **MCP_Server**: The existing aspice-check Model Context Protocol server (AspiceMCPServer) that exposes confluence-ai and aspice-eval functionality as tools for AI assistants.

## Requirements

### Requirement 1: Calendar Discovery via Page

**User Story:** As a developer, I want to discover available calendars from a Confluence page URL, so that I can identify which calendar to export by reading the calendar macros embedded in the page.

#### Acceptance Criteria

1. WHEN a valid Confluence page URL is provided, THE Calendar_Client SHALL fetch the page's storage format body and extract parent calendar IDs from Calendar_Macro elements.
2. WHEN parent calendar IDs are extracted from the page, THE Calendar_Client SHALL call the `subcalendars.json` endpoint to resolve each parent ID into its full metadata including descriptive name, type, and child Sub_Calendar entries.
3. THE Calendar_Client SHALL return a tree structure containing each Parent_Calendar with its name, type, and ID, along with nested child Sub_Calendars each having a descriptive name, type, and ID.
4. WHEN a Calendar_Macro contains comma-separated IDs in its `id` parameter, THE Calendar_Client SHALL treat each comma-separated value as a separate parent calendar ID to resolve.
5. IF the page URL is invalid or the page does not exist, THEN THE Calendar_Client SHALL raise a PageNotFoundError with a descriptive message.
6. IF the page contains no Calendar_Macro elements, THEN THE Calendar_Client SHALL return an empty list with a warning indicating no calendars were found on the page.
7. IF authentication credentials are invalid, THEN THE Calendar_Client SHALL raise an AuthenticationError.
8. THE Calendar_Client SHALL include the `X-Requested-With: XMLHttpRequest` header on all requests to the calendar REST API endpoints.
9. THE Calendar_Client SHALL return the top-level Parent_Calendar entries sorted alphabetically by descriptive calendar name using case-insensitive ordering.
10. WITHIN each Parent_Calendar, THE Calendar_Client SHALL return the child Sub_Calendar entries sorted alphabetically by descriptive calendar name using case-insensitive ordering.

### Requirement 2: Event Retrieval

**User Story:** As a developer, I want to retrieve calendar events within a date range, so that I can export a specific time window of events.

#### Acceptance Criteria

1. WHEN a child Sub_Calendar ID and Date_Range are provided, THE Calendar_Client SHALL return all events that overlap with the specified Date_Range from that Sub_Calendar.
2. WHEN a Parent_Calendar ID is provided instead of a child Sub_Calendar ID, THE Calendar_Client SHALL auto-resolve the parent to its child Sub_Calendars via the `subcalendars.json` endpoint and fetch events from all children.
3. WHEN the calendar REST API returns a response with `{"success": true}` and no `events` key, THE Calendar_Client SHALL treat this as a parent calendar indicator and resolve to child Sub_Calendars.
4. THE Calendar_Client SHALL return Event objects containing: summary, start time (with timezone), end time (with timezone), description, location, organizer, and unique event ID.
5. WHEN no Date_Range is provided, THE Calendar_Client SHALL default to retrieving events from 30 days in the past to 90 days in the future.
6. IF the calendar ID does not exist or the user lacks access, THEN THE Calendar_Client SHALL raise a CalendarNotFoundError with the calendar ID in the message.
7. WHEN a calendar contains recurring events, THE Calendar_Client SHALL expand recurrences within the Date_Range into individual Event instances.
8. THE Calendar_Client SHALL include the `X-Requested-With: XMLHttpRequest` header and `Accept: application/json, text/javascript, */*; q=0.01` header on all event retrieval requests.
9. THE Calendar_Client SHALL include the `userTimeZoneId=UTC` parameter on all event retrieval requests.

### Requirement 3: JSON Export

**User Story:** As a developer, I want to export calendar events to JSON format, so that I can programmatically consume the data.

#### Acceptance Criteria

1. WHEN events are exported with format "json", THE Calendar_Renderer SHALL produce a JSON file containing an array of event objects.
2. THE Calendar_Renderer SHALL include metadata in the JSON output: calendar name, export timestamp, exporter version, and date range.
3. THE Calendar_Renderer SHALL serialize datetime values as ISO 8601 strings with timezone offset.
4. THE Calendar_Renderer SHALL include all Event fields: event_id, summary, start, end, description, location, organizer, and all_day flag.

### Requirement 4: Markdown Export

**User Story:** As a developer, I want to export calendar events to Markdown format, so that I can include them in documentation or reports.

#### Acceptance Criteria

1. WHEN events are exported with format "markdown", THE Calendar_Renderer SHALL produce a Markdown file with a YAML front-matter block containing export metadata.
2. THE Calendar_Renderer SHALL render events as a chronologically sorted list grouped by date.
3. THE Calendar_Renderer SHALL include event summary, time range, location, and description for each event entry.
4. WHEN an Event is an all-day event, THE Calendar_Renderer SHALL display "All day" instead of a specific time range.

### Requirement 5: Export Orchestration

**User Story:** As a developer, I want a single function that coordinates calendar retrieval and rendering, so that I can export calendars with one call.

#### Acceptance Criteria

1. THE Calendar_Exporter SHALL accept a calendar ID (GUID), output directory, output format, optional Date_Range, and authentication credentials.
2. THE Calendar_Exporter SHALL validate credentials before making API calls and raise AuthenticationError if email or API token is empty.
3. WHEN export completes successfully, THE Calendar_Exporter SHALL return a CalendarExportResult containing the output file path, event count, and any warnings.
4. THE Calendar_Exporter SHALL create the output directory if it does not exist.
5. THE Calendar_Exporter SHALL sanitize the calendar name for use as the output filename, replacing spaces with underscores and removing special characters.
6. WHEN a Parent_Calendar ID is provided, THE Calendar_Exporter SHALL auto-resolve to child Sub_Calendars and aggregate events from all children into a single export.

### Requirement 6: MCP Server Tools

**User Story:** As an AI assistant user, I want MCP tools for calendar discovery and export added to the existing aspice-check MCP server, so that AI assistants can retrieve and export calendar data alongside existing tools.

#### Acceptance Criteria

1. THE existing AspiceMCPServer in `aspice-check/src/aspice_check/mcp_server.py` SHALL expose an `export_calendar` tool with parameters: calendar_id, base_url, output_dir, output_format, start_date, end_date, email, and api_token.
2. THE `export_calendar` tool schema SHALL be defined in `aspice-check/src/aspice_check/mcp_tools.py` following the same pattern as existing tool schemas (e.g., EXPORT_PAGE_SCHEMA).
3. THE MCP_Server SHALL validate required parameters (calendar_id, base_url, output_dir) and return an error if missing.
4. WHEN export succeeds, THE MCP_Server SHALL return the output file path, event count, and any warnings in the response.
5. IF export fails, THEN THE MCP_Server SHALL return a structured error message describing the failure.
6. THE MCP_Server SHALL expose a `list_calendars` tool with parameters: page_url, base_url, email, and api_token, that discovers calendars from a Confluence page URL.
7. WHEN `list_calendars` succeeds, THE MCP_Server SHALL return the full calendar tree: parent calendars with their child Sub_Calendars, each including name, type, and ID, with parent calendars sorted alphabetically (case-insensitive) by name and each parent's child Sub_Calendars sorted alphabetically (case-insensitive) by name.
8. WHEN a Parent_Calendar ID is provided to `export_calendar`, THE MCP_Server SHALL auto-resolve to child Sub_Calendars and export events from all children.

### Requirement 7: Calendar-Specific Exceptions

**User Story:** As a developer, I want specific exception types for calendar errors, so that I can handle calendar failures distinctly from page export failures.

#### Acceptance Criteria

1. THE Calendar_Client SHALL raise CalendarNotFoundError (subclass of ExporterError) when a calendar ID is not found or inaccessible.
2. THE Calendar_Client SHALL raise CalendarAPIError (subclass of ExporterError) when the calendar REST API returns an unexpected error.
3. THE CalendarNotFoundError SHALL include the calendar_id and optional HTTP status code in its attributes.
4. THE CalendarAPIError SHALL include the endpoint path and HTTP status code in its attributes.

### Requirement 8: Public API Surface

**User Story:** As a library consumer, I want calendar export functionality exposed in the package's public API, so that I can use it programmatically.

#### Acceptance Criteria

1. THE confluence_ai package SHALL expose an `export_calendar()` convenience function in `__init__.py`.
2. THE confluence_ai package SHALL expose CalendarExportResult, CalendarNotFoundError, and CalendarAPIError in `__init__.py`.
3. THE `export_calendar()` function SHALL accept the same parameters as the Calendar_Exporter orchestration function and return a CalendarExportResult.
