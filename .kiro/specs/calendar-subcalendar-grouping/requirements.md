# Requirements Document

## Introduction

This feature enhances the Confluence Calendar export to present events from all subcalendars as a single unified calendar view in the output. Currently, when a parent calendar ID is exported, the system correctly auto-resolves to child subcalendars and aggregates events, but the output retains per-subcalendar identity and the calendar name resolution falls back to the raw `calendar_id` when events come from multiple subcalendars. This feature ensures the output uses the parent calendar's descriptive name as the unified title and presents all events as belonging to one logical calendar.

The existing `export_calendar()` API and `get_events()` method remain unchanged. A new `export_calendar_grouped()` convenience function is added that produces the unified view. The MCP `export_calendar` tool gains unified output behavior automatically when a parent calendar ID is provided.

## Glossary

- **Calendar_Exporter**: The orchestration module (`calendar_export.py`) that coordinates retrieval, rendering, and file output for calendar exports.
- **Calendar_Client**: The module (`calendar_client.py`) responsible for communicating with the Confluence Calendar REST API to retrieve calendar metadata and events.
- **Calendar_Renderer**: A component (`calendar_renderer.py`) that transforms internal event models into a specific output format (JSON or Markdown).
- **Parent_Calendar**: A top-level calendar referenced by a page macro. Contains no events directly; holds child Sub_Calendars that contain events.
- **Sub_Calendar**: A child calendar within a parent Team Calendar that manages a specific event type (e.g., Leave, Travel, Custom Events).
- **Unified_Calendar_View**: An output representation where events from all subcalendars are merged under a single parent calendar name, without per-subcalendar separation in the document structure.
- **CalendarMetadata**: The metadata block included in export output (JSON top-level object and Markdown YAML front-matter) containing calendar_id, calendar_name, export_timestamp, exporter_version, date_range, and event_count.

## Requirements

### Requirement 1: Parent Calendar Name Resolution

**User Story:** As a developer, I want the grouped export output to use the parent calendar's descriptive name as the title, so that the output is clearly identified by the calendar's human-readable name rather than a raw GUID.

#### Acceptance Criteria

1. WHEN a Parent_Calendar ID is provided to the grouped export function, THE Calendar_Exporter SHALL resolve the parent calendar's descriptive name via the `list_subcalendars` endpoint and use it as the `calendar_name` in CalendarMetadata.
2. WHEN events are retrieved from multiple Sub_Calendars under a single Parent_Calendar, THE Calendar_Exporter SHALL use the Parent_Calendar's descriptive name as the unified `calendar_name` in the output.
3. IF the parent calendar name cannot be resolved (endpoint failure or empty response), THEN THE Calendar_Exporter SHALL fall back to using the first event's `sub_calendar_name`, then to the raw `calendar_id`.
4. WHEN a single Sub_Calendar ID is provided (not a parent), THE Calendar_Exporter SHALL use that Sub_Calendar's name from the event data as the `calendar_name`.

### Requirement 2: Unified JSON Output

**User Story:** As a developer, I want the JSON export to present all events from subcalendars in a single flat list under one metadata block with the parent calendar name, so that consumers see a unified calendar view.

#### Acceptance Criteria

1. WHEN a Parent_Calendar is exported to JSON format via the grouped export, THE Calendar_Renderer SHALL produce a single JSON document with one `metadata` object using the Parent_Calendar's descriptive name as `calendar_name`.
2. THE Calendar_Renderer SHALL include all events from all child Sub_Calendars in a single `events` array, sorted chronologically by start time.
3. THE Calendar_Renderer SHALL retain `sub_calendar_id` and `sub_calendar_name` fields on each event object to preserve provenance information.
4. THE CalendarMetadata `event_count` field SHALL equal the total number of events across all Sub_Calendars.

### Requirement 3: Unified Markdown Output

**User Story:** As a developer, I want the Markdown export to present all events from subcalendars grouped by date under a single heading with the parent calendar name, so that the output reads as one cohesive calendar.

#### Acceptance Criteria

1. WHEN a Parent_Calendar is exported to Markdown format via the grouped export, THE Calendar_Renderer SHALL produce a single Markdown document with the Parent_Calendar's descriptive name as the H1 heading.
2. THE Calendar_Renderer SHALL merge events from all child Sub_Calendars into date-grouped sections (H2 headings), sorted chronologically.
3. THE Calendar_Renderer SHALL include the Sub_Calendar name as a sub-bullet on each event entry to indicate provenance (e.g., `- Calendar: {sub_calendar_name}`).
4. THE CalendarMetadata in the YAML front-matter SHALL use the Parent_Calendar's descriptive name as `calendar_name` and the total event count across all Sub_Calendars as `event_count`.

### Requirement 4: Output Filename Uses Parent Calendar Name

**User Story:** As a developer, I want the output filename to use the parent calendar's descriptive name when exporting a parent calendar, so that the file is easily identifiable on disk.

#### Acceptance Criteria

1. WHEN a Parent_Calendar is exported via the grouped export, THE Calendar_Exporter SHALL use the resolved Parent_Calendar descriptive name (sanitized) as the output filename stem.
2. THE Calendar_Exporter SHALL sanitize the Parent_Calendar name using the existing filename sanitization rules (spaces to underscores, strip non-alphanumeric characters except underscore and hyphen).
3. IF the sanitized name is empty, THEN THE Calendar_Exporter SHALL fall back to the literal string "calendar" as the filename stem.

### Requirement 5: New Grouped Export API Function

**User Story:** As a library consumer, I want a new `export_calendar_grouped()` function that produces unified output, while the existing `export_calendar()` function remains unchanged, so that I can choose between the current behavior and the new grouped behavior.

#### Acceptance Criteria

1. THE confluence_ai package SHALL expose a new `export_calendar_grouped()` convenience function in `__init__.py`.
2. THE `export_calendar_grouped()` function SHALL accept the same parameters as `export_calendar()`: base_url, calendar_id, output_dir, email, api_token, output_format, and date_range.
3. WHEN called with a Parent_Calendar ID, THE `export_calendar_grouped()` function SHALL resolve the parent name, fetch events from all child Sub_Calendars, and produce a single unified output file.
4. WHEN called with a child Sub_Calendar ID, THE `export_calendar_grouped()` function SHALL behave identically to `export_calendar()` (single subcalendar export with that subcalendar's name).
5. THE existing `export_calendar()` function SHALL remain unchanged in behavior and signature.
6. THE `export_calendar_grouped()` function SHALL return a CalendarExportResult containing the output file path, event count, and any warnings.

### Requirement 6: MCP Tool Unified Output

**User Story:** As an AI assistant user, I want the `export_calendar` MCP tool to produce unified output when given a parent calendar ID, so that the exported file presents a single calendar view by default.

#### Acceptance Criteria

1. WHEN the `export_calendar` MCP tool is called with a Parent_Calendar ID, THE MCP_Server SHALL produce a unified output file with the Parent_Calendar's descriptive name and all events merged.
2. THE `export_calendar` MCP tool response SHALL include the total `event_count` across all Sub_Calendars.
3. THE `export_calendar` MCP tool SHALL require no additional parameters to produce unified output — the behavior is automatic when a Parent_Calendar ID is provided.
4. THE MCP_Server SHALL use the `export_calendar_grouped()` library function internally to produce the unified output.

