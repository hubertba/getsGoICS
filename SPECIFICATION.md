# ICS Importer Specification

## Overview

ICS Importer is a Python-based tool for processing iCalendar (ICS) feeds from multiple sources, filtering events, and generating output in various formats suitable for calendar applications.

## Architecture

### Core Components

1. **Event Parser** (`parse_events`): Parses ICS text into structured Event objects
2. **Event Filter** (`filter_events`): Filters events by date range and keywords
3. **Team Router** (`_teams_for_event`): Determines which team calendars an event belongs to
4. **Calendar Generator**: Creates ICS files in different formats:
   - Individual invitations (`generate_invites`)
   - Aggregated calendars (`export_calendars`)
   - Team calendars (`export_team_calendars`)

### Data Model

#### Event Dataclass

```python
@dataclass
class Event:
    uid: str                    # Unique identifier
    summary: str                # Event title
    description: str            # Event description
    location: str               # Event location
    url: str                    # Related URL
    start: datetime             # Start time (timezone-aware)
    end: datetime               # End time (timezone-aware)
    status: str = ""            # Event status (CONFIRMED, etc.)
    transparency: str = ""      # TRANSPARENT/OPAQUE
    created: datetime | None    # Creation timestamp
    last_modified: datetime | None  # Last modification timestamp
    dtstamp: datetime | None    # DTSTAMP value
```

## Processing Flow

### 1. Input Phase

- Fetches ICS content from provided URLs using HTTP GET
- Parses ICS text using `icalendar` library
- Extracts VEVENT components and converts to Event objects
- Handles timezone information (converts to UTC if needed)
- Preserves metadata (status, transparency, created, modified)

### 2. Filtering Phase

- **Date Filtering**: Events must have `start` date within `[start, end]` range
- **Keyword Filtering**: Events whose summary contains excluded keywords are removed
- Default exclusions (invite/aggregate modes): `["U9", "U10", "Schultraining"]`

### 3. Routing Phase (Team Calendars Only)

- Analyzes event summary for team indicators
- Applies routing rules (see Team Routing Rules section)
- Tracks source URL to apply source-specific rules (e.g., Google Calendar mU14 → U12.1)

### 4. Output Phase

- **Invite Mode**: Creates individual `.ics` files with `METHOD:REQUEST` and RSVP attendee
- **Aggregate Mode**: Creates one `.ics` file per source with `METHOD:PUBLISH`
- **Team Mode**: Creates one `.ics` file per team with `METHOD:PUBLISH`

## Team Routing Algorithm

### Detection Method

The tool uses a two-phase detection system:

1. **Keyword Pattern Matching**: Regex patterns for specific team keywords
2. **Number Extraction**: Extracts numeric values (9, 10, 11, 12, 12.1, 12.2, 14) from summaries

### Routing Rules (Priority Order)

1. **Special Keywords** (highest priority):
   - `schultraining` → Schultraining
   - `getsgo start` (case-insensitive) → GetsGoStart
   - `xU14` → mU14, wU14

2. **Gender/Type Prefixes**:
   - `mU14` or `m14` → mU14
   - `wU14` or `w14` → wU14
   - `wU12` or `w12` → wU12
   - `wU12/14` → wU12, wU14

3. **Number Detection**:
   - Contains `9` → U9
   - Contains `10` → U10
   - Contains `11` → U11
   - Contains `12.1` → U12.1
   - Contains `12.2` → U12.2
   - Contains `12` (without .1/.2) → U12.1, U12.2

4. **Combination Rules**:
   - `9/10` or `9-10` → U9, U10
   - `11/12` → U11, U12.1, wU12
   - `wU12/14` → wU12, wU14

5. **Source-Specific Rules**:
   - mU14 events from Google Calendar → Also added to U12.1

### Exclusion Rules

- U12.1 calendar excludes events explicitly containing "U12.2"
- U12.2 calendar excludes events explicitly containing "U12.1"
- Other teams don't exclude each other (events can appear in multiple calendars)

## Output Formats

### Invitation Format (METHOD:REQUEST)

```ics
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//icsImporter//Invite Generator//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:<event-uid>
SUMMARY:<event-summary>
DTSTART:<start-time>
DTEND:<end-time>
DTSTAMP:<current-time>
SEQUENCE:0
ATTENDEE;CN="<attendee-name>";PARTSTAT=NEEDS-ACTION;ROLE=REQ-PARTICIPANT;RSVP=TRUE:MAILTO:<attendee-email>
ORGANIZER;CN=<organizer-email>:MAILTO:<organizer-email>
...
END:VEVENT
END:VCALENDAR
```

### Calendar Format (METHOD:PUBLISH)

```ics
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//icsImporter//Calendar Export//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
NAME:<calendar-name>
X-WR-CALNAME:<calendar-name>
BEGIN:VEVENT
UID:<event-uid>
SUMMARY:<event-summary>
DTSTART:<start-time>
DTEND:<end-time>
...
END:VEVENT
END:VCALENDAR
```

## Normalization Rules

### Summary Normalization

- `GETSGOstart` (any case variation) → `GetsGoStart`
- Applied when writing events to output calendars
- Case-insensitive matching with regex: `getsgo\s*start`

## Date Handling

### Timezone Support

- All datetime objects are timezone-aware
- Input dates without timezone are assumed UTC
- Date-only values (all-day events) are converted to datetime at 00:00 UTC
- Boundary dates:
  - Start boundary: Uses `time.min` (00:00:00)
  - End boundary: Uses `time.max` (23:59:59)

### Date Filtering Logic

```python
if start_dt and event.start < start_dt:
    continue  # Event too early
if end_dt and event.start > end_dt:
    continue  # Event too late
```

## Error Handling

- HTTP errors from URL fetching raise exceptions
- Invalid ICS format: Parsing errors are propagated
- Missing required fields: Events without DTSTART are skipped
- Invalid date formats: CLI argument parsing raises `ArgumentTypeError`

## Performance Considerations

- Events are loaded into memory (suitable for calendars with <10,000 events)
- Team routing is O(n*m) where n=events, m=teams
- File I/O is sequential (one file per event/team)

## Testing Strategy

### Unit Tests

- Event parsing from sample ICS
- Date filtering logic
- Keyword filtering logic
- Team routing for various patterns
- Calendar generation (invite, aggregate, team modes)

### Test Coverage

- All core functions have unit tests
- Edge cases: empty calendars, missing fields, timezone handling
- Integration tests for CLI argument parsing

## Dependencies

- `icalendar`: ICS parsing and generation
- `requests`: HTTP fetching
- `pytest`: Testing framework

## Limitations

1. **Memory**: All events loaded into memory (not suitable for very large calendars)
2. **Timezone**: Complex timezone rules may not be fully preserved
3. **Recurrence**: Recurring events (RRULE) are not expanded
4. **Attachments**: Event attachments are not preserved
5. **Alarms**: Event alarms/reminders are not preserved

## Future Enhancements

Potential improvements:
- Recurrence rule expansion
- Incremental updates (track last sync)
- Calendar subscription support
- Web UI for configuration
- Event deduplication across sources
- Custom team routing rules via configuration file

