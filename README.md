# ICS Importer

A Python tool for importing and organizing calendar events from ICS feeds (Vereinsplaner, Google Calendar, etc.) into Apple Calendar-compatible formats with team-based filtering and RSVP support.

## Features

- **Multiple Import Modes**:
  - Generate individual RSVP invitations for each event
  - Aggregate events by source into standalone ICS files
  - Create team-specific calendars with intelligent event routing

- **Date Filtering**: Import events within a specific date range
- **Keyword Filtering**: Exclude events based on summary keywords
- **Team Detection**: Automatically route events to appropriate team calendars based on event names
- **Normalization**: Fixes capitalization issues (e.g., GETSGOstart → GetsGoStart)

## Installation

1. Clone or download this repository
2. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Command Structure

```bash
python -m ics_importer.cli [OPTIONS] <URLS...>
```

### Command-Line Options

#### Required Arguments
- `urls`: One or more ICS calendar URLs to import

#### Required Options (for invite mode)
- `--attendee-email EMAIL`: Email address of the attendee who will receive invitations

#### Optional Options
- `--attendee-name NAME`: Display name of the attendee (defaults to email)
- `--organizer-email EMAIL`: Email address for the organizer (defaults to attendee email)
- `--output-dir DIR`: Output directory (default: `invites`)
- `--start DATE`: Start date filter (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
- `--end DATE`: End date filter (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
- `--exclude-keyword KEYWORD`: Exclude events containing this keyword (can be used multiple times)
- `--quiet`: Suppress informational output

#### Mode Selection (mutually exclusive)
- `--aggregate`: Create one ICS file per source calendar
- `--team-calendars`: Generate team-specific calendars (see Team Calendars section)
- (default): Generate individual RSVP invitation files

## Usage Modes

### 1. Individual RSVP Invitations (Default)

Generate separate `.ics` files for each event that can be opened in Apple Calendar to accept/decline individually.

```bash
python -m ics_importer.cli \
  --attendee-email you@example.com \
  --attendee-name "Your Name" \
  --organizer-email organizer@example.com \
  --output-dir invites_dec_2025 \
  --start 2025-12-01 \
  --end 2025-12-31 \
  https://api.vereinsplaner.at/v1/public/ical/your-calendar.ics \
  https://calendar.google.com/calendar/ical/your-calendar/public/basic.ics
```

**Output**: Individual `.ics` files in the output directory, each containing a single event with RSVP request.

### 2. Aggregate Mode

Combine all events from each source into separate ICS files (one per source).

```bash
python -m ics_importer.cli \
  --aggregate \
  --output-dir calendars_dec_2025 \
  --start 2025-12-01 \
  --end 2025-12-31 \
  https://api.vereinsplaner.at/v1/public/ical/your-calendar.ics \
  https://calendar.google.com/calendar/ical/your-calendar/public/basic.ics
```

**Output**: 
- `vereinsplaner.ics`: All events from Vereinsplaner
- `google.ics`: All events from Google Calendar

### 3. Team Calendars Mode

Generate separate ICS files for each team, with intelligent event routing based on event names.

```bash
python -m ics_importer.cli \
  --team-calendars \
  --output-dir team_calendars \
  --start 2025-12-01 \
  --end 2026-07-01 \
  https://api.vereinsplaner.at/v1/public/ical/your-calendar.ics \
  https://calendar.google.com/calendar/ical/your-calendar/public/basic.ics
```

**Output**: Separate `.ics` files for each team:
- `U9.ics`
- `U10.ics`
- `U11.ics`
- `U12.1.ics`
- `U12.2.ics`
- `wU12.ics`
- `mU14.ics`
- `wU14.ics`
- `Schultraining.ics`
- `GetsGoStart.ics`

## Team Calendar Routing Rules

The tool automatically routes events to team calendars based on numbers and keywords found in event summaries:

### Number-Based Detection
- Events containing **9** → `U9.ics`
- Events containing **10** → `U10.ics`
- Events containing **11** → `U11.ics`
- Events containing **12** (without .1 or .2) → `U12.1.ics` and `U12.2.ics`
- Events containing **12.1** → `U12.1.ics`
- Events containing **12.2** → `U12.2.ics`

### Keyword-Based Detection
- **Schultraining** → `Schultraining.ics`
- **GetsGoStart** (case-insensitive) → `GetsGoStart.ics`
- **mU14** or **m14** → `mU14.ics`
- **wU14** or **w14** → `wU14.ics`
- **wU12** or **w12** → `wU12.ics`
- **xU14** → `mU14.ics` and `wU14.ics`

### Special Routing Rules
- **9/10** or **9-10** → Both `U9.ics` and `U10.ics`
- **11/12** → `U11.ics`, `U12.1.ics`, and `wU12.ics`
- **wU12/14** → Both `wU12.ics` and `wU14.ics`
- **mU14 from Google Calendar** → Also added to `U12.1.ics`

### Exclusion Rules
- `U12.1.ics` excludes events explicitly marked as "U12.2"
- `U12.2.ics` excludes events explicitly marked as "U12.1"

## Examples

### Example 1: Import December 2025 Events as Invitations

```bash
python -m ics_importer.cli \
  --attendee-email getsgo@example.com \
  --attendee-name "GetsGo" \
  --output-dir invites_dec_2025 \
  --start 2025-12-01 \
  --end 2025-12-31 \
  https://api.vereinsplaner.at/v1/public/ical/your-calendar.ics
```

### Example 2: Generate Team Calendars for Full Season

```bash
python -m ics_importer.cli \
  --team-calendars \
  --output-dir team_calendars_2025_2026 \
  --start 2025-12-01 \
  --end 2026-07-01 \
  https://api.vereinsplaner.at/v1/public/ical/your-calendar.ics \
  https://calendar.google.com/calendar/ical/your-calendar/public/basic.ics
```

### Example 3: Aggregate Mode with Custom Exclusions

```bash
python -m ics_importer.cli \
  --aggregate \
  --output-dir filtered_calendars \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --exclude-keyword "U9" \
  --exclude-keyword "U10" \
  --exclude-keyword "Schultraining" \
  https://api.vereinsplaner.at/v1/public/ical/your-calendar.ics
```

## Default Exclusions

When using invite mode or aggregate mode, the following keywords are excluded by default:
- `U9`
- `U10`
- `Schultraining`

To override this, use `--exclude-keyword` with your own keywords, or provide an empty list by not using the flag (team calendars mode doesn't apply default exclusions).

## Output Files

All generated `.ics` files are compatible with:
- Apple Calendar
- Google Calendar
- Microsoft Outlook
- Other standard calendar applications

Simply double-click any `.ics` file to import it into your calendar application.

## Testing

Run the test suite:

```bash
pytest
```

## Requirements

- Python 3.8+
- See `requirements.txt` for dependencies

## License

[Add your license information here]

