from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
import re
from pathlib import Path
from typing import Dict, List, Sequence, Set
from urllib.parse import urlparse
import uuid

import requests
from icalendar import Calendar, Event as ICalEvent, vCalAddress, vText


@dataclass
class Event:
    uid: str
    summary: str
    description: str
    location: str
    url: str
    start: datetime
    end: datetime
    status: str = ""
    transparency: str = ""
    created: datetime | None = None
    last_modified: datetime | None = None
    dtstamp: datetime | None = None


def fetch_ics(url: str, timeout: int = 10) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_events(ics_text: str) -> List[Event]:
    calendar = Calendar.from_ical(ics_text)

    events: List[Event] = []
    for component in calendar.walk():
        if component.name != "VEVENT":
            continue

        dtstart = component.get("DTSTART")
        if not dtstart:
            continue

        start = _ensure_datetime(dtstart.dt)
        dtend = component.get("DTEND")
        end = _ensure_datetime(dtend.dt) if dtend else start

        raw_uid = component.get("UID")
        uid = str(raw_uid) if raw_uid else _generate_uid()

        events.append(
            Event(
                uid=uid,
                summary=_text(component.get("SUMMARY")),
                description=_text(component.get("DESCRIPTION")),
                location=_text(component.get("LOCATION")),
                url=_text(component.get("URL")),
                start=start,
                end=end,
                status=_text(component.get("STATUS")),
                transparency=_text(component.get("TRANSP")),
                created=_maybe_datetime(component.get("CREATED")),
                last_modified=_maybe_datetime(component.get("LAST-MODIFIED")),
                dtstamp=_maybe_datetime(component.get("DTSTAMP")),
            )
        )

    return events


def create_invitation(
    event: Event,
    attendee_email: str,
    organizer_email: str | None = None,
    attendee_name: str | None = None,
) -> str:
    organizer_email = organizer_email or attendee_email
    attendee_name = attendee_name or attendee_email

    calendar = Calendar()
    calendar.add("prodid", "-//icsImporter//Invite Generator//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "REQUEST")

    component = ICalEvent()
    component.add("uid", event.uid)
    if event.summary:
        component.add("summary", event.summary)
    if event.description:
        component.add("description", event.description)
    if event.location:
        component.add("location", event.location)
    if event.url:
        component.add("url", event.url)
    if event.status:
        component.add("status", event.status)
    if event.transparency:
        component.add("transp", event.transparency)
    if event.created:
        component.add("created", event.created)
    if event.last_modified:
        component.add("last-modified", event.last_modified)
    component.add("dtstamp", datetime.now(timezone.utc))
    component.add("dtstart", event.start)
    component.add("dtend", event.end)
    component.add("sequence", 0)

    organizer = vCalAddress(f"MAILTO:{organizer_email}")
    organizer.params["cn"] = vText(organizer_email)
    component.add("organizer", organizer)

    attendee = vCalAddress(f"MAILTO:{attendee_email}")
    attendee.params["cn"] = vText(attendee_name)
    attendee.params["role"] = vText("REQ-PARTICIPANT")
    attendee.params["partstat"] = vText("NEEDS-ACTION")
    attendee.params["rsvp"] = vText("TRUE")
    component.add("attendee", attendee)

    calendar.add_component(component)

    return calendar.to_ical().decode("utf-8")


def generate_invites(
    events: Sequence[Event],
    attendee_email: str,
    output_dir: Path | str,
    organizer_email: str | None = None,
    attendee_name: str | None = None,
) -> List[Path]:
    attendee_name = attendee_name or attendee_email
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    written_paths: List[Path] = []
    used_names: set[str] = set()

    for event in events:
        invite_content = create_invitation(
            event,
            attendee_email=attendee_email,
            organizer_email=organizer_email,
            attendee_name=attendee_name,
        )
        filename = _build_filename(event.uid, used_names)
        target = output_path / filename
        target.write_text(invite_content, encoding="utf-8")
        written_paths.append(target)

    return written_paths


def filter_events(
    events: Sequence[Event],
    start: datetime | date | None = None,
    end: datetime | date | None = None,
    exclude_keywords: Sequence[str] | None = None,
) -> List[Event]:
    start_dt = _normalize_boundary(start, is_start=True)
    end_dt = _normalize_boundary(end, is_start=False)
    exclude_lower = [keyword.lower() for keyword in exclude_keywords or []]

    filtered: List[Event] = []
    for event in events:
        summary_lower = event.summary.lower() if event.summary else ""
        if exclude_lower and any(keyword in summary_lower for keyword in exclude_lower):
            continue
        if start_dt and event.start < start_dt:
            continue
        if end_dt and event.start > end_dt:
            continue
        filtered.append(event)

    return filtered


def import_invites(
    urls: Sequence[str],
    attendee_email: str,
    output_dir: Path | str,
    *,
    start: datetime | date | None = None,
    end: datetime | date | None = None,
    organizer_email: str | None = None,
    attendee_name: str | None = None,
    exclude_keywords: Sequence[str] | None = None,
) -> List[Path]:
    events_by_url = _load_events(urls)
    all_events = [
        event for events in events_by_url.values() for event in events
    ]

    filtered = filter_events(
        all_events,
        start=start,
        end=end,
        exclude_keywords=exclude_keywords,
    )

    return generate_invites(
        filtered,
        attendee_email=attendee_email,
        output_dir=output_dir,
        organizer_email=organizer_email,
        attendee_name=attendee_name,
    )


def export_calendars(
    urls: Sequence[str],
    output_dir: Path | str,
    *,
    start: datetime | date | None = None,
    end: datetime | date | None = None,
    exclude_keywords: Sequence[str] | None = None,
) -> Dict[str, Path]:
    events_by_url = _load_events(urls)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    written: Dict[str, Path] = {}
    used_names: set[str] = set()

    for url, events in events_by_url.items():
        filtered = filter_events(
            events,
            start=start,
            end=end,
            exclude_keywords=exclude_keywords,
        )

        if not filtered:
            continue

        calendar = Calendar()
        calendar.add("prodid", "-//icsImporter//Calendar Export//EN")
        calendar.add("version", "2.0")
        calendar.add("calscale", "GREGORIAN")
        calendar.add("method", "PUBLISH")

        name = _calendar_name_from_url(url)
        calendar.add("name", name)
        calendar.add("x-wr-calname", name)

        for event in filtered:
            component = ICalEvent()
            component.add("uid", event.uid)
            if event.summary:
                component.add("summary", event.summary)
            if event.description:
                component.add("description", event.description)
            if event.location:
                component.add("location", event.location)
            if event.url:
                component.add("url", event.url)
            component.add("dtstart", event.start)
            component.add("dtend", event.end)
            if event.status:
                component.add("status", event.status)
            if event.transparency:
                component.add("transp", event.transparency)
            if event.created:
                component.add("created", event.created)
            if event.last_modified:
                component.add("last-modified", event.last_modified)
            component.add(
                "dtstamp",
                event.dtstamp or event.last_modified or event.created or datetime.now(timezone.utc),
            )

            calendar.add_component(component)

        filename = _calendar_filename_from_url(url, used_names)
        path = output_path / filename
        path.write_bytes(calendar.to_ical())
        written[url] = path

    return written


def export_team_calendars(
    urls: Sequence[str],
    output_dir: Path | str,
    *,
    start: datetime | date | None = None,
    end: datetime | date | None = None,
    exclude_keywords: Sequence[str] | None = None,
) -> Dict[str, Path]:
    events_by_url = _load_events(urls)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    base_events = [
        event for events in events_by_url.values() for event in events
    ]

    filtered_events = filter_events(
        base_events,
        start=start,
        end=end,
        exclude_keywords=None,
    )

    teams = ["U9", "U10", "U11", "U12.1", "U12.2", "wU12", "mU14", "wU14", "Schultraining", "GetsGoStart"]
    team_calendars: Dict[str, Calendar] = {team: _new_team_calendar(team) for team in teams}

    exclude_keywords = exclude_keywords or []

    exclusion_map = {
        "U9": exclude_keywords,
        "U10": exclude_keywords,
        "U11": exclude_keywords,
        "U12.1": exclude_keywords + ["U12.2"],
        "U12.2": exclude_keywords + ["U12.1"],
        "wU12": exclude_keywords,
        "mU14": exclude_keywords,
        "wU14": exclude_keywords,
        "Schultraining": [],
        "GetsGoStart": [],
    }

    # Track source URL for each event by UID
    event_uid_to_url: Dict[str, str] = {}
    for url, events in events_by_url.items():
        for event in events:
            event_uid_to_url[event.uid] = url
    
    for event in filtered_events:
        assigned = False
        event_teams = set(_teams_for_event(event))
        source_url = event_uid_to_url.get(event.uid, "")
        is_google = "google" in source_url.lower()
        
        # Special case: mU14 from Google Calendar should also go to U12.1
        if is_google and "mU14" in event_teams:
            event_teams.add("U12.1")
        
        for team in teams:
            if team in event_teams:
                if exclusion_map[team] and any(
                    keyword.lower() in (event.summary or "").lower()
                    for keyword in exclusion_map[team]
                ):
                    continue
                _append_event(team_calendars[team], event)
                assigned = True
        if not assigned:
            continue

    written: Dict[str, Path] = {}
    for team, calendar in team_calendars.items():
        if not any(component.name == "VEVENT" for component in calendar.walk()):
            continue
        filename = f"{team}.ics"
        path = output_path / filename
        path.write_bytes(calendar.to_ical())
        written[team] = path

    return written


def _append_event(calendar: Calendar, event: Event) -> None:
    component = ICalEvent()
    component.add("uid", event.uid)
    if event.summary:
        # Normalize GETSGOstart variations to GetsGoStart
        summary = re.sub(r"getsgo\s*start", "GetsGoStart", event.summary, flags=re.IGNORECASE)
        component.add("summary", summary)
    if event.description:
        component.add("description", event.description)
    if event.location:
        component.add("location", event.location)
    if event.url:
        component.add("url", event.url)
    component.add("dtstart", event.start)
    component.add("dtend", event.end)
    if event.status:
        component.add("status", event.status)
    if event.transparency:
        component.add("transp", event.transparency)
    if event.created:
        component.add("created", event.created)
    if event.last_modified:
        component.add("last-modified", event.last_modified)
    component.add(
        "dtstamp",
        event.dtstamp or event.last_modified or event.created or datetime.now(timezone.utc),
    )
    calendar.add_component(component)


def _ensure_datetime(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    # Interpret date-only values as all-day events in UTC.
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _build_filename(uid: str, used_names: set[str]) -> str:
    safe_uid = "".join(char for char in uid if char.isalnum() or char in ("-", "_"))
    if not safe_uid:
        safe_uid = "event"

    candidate = f"{safe_uid}.ics"
    counter = 1
    while candidate in used_names:
        counter += 1
        candidate = f"{safe_uid}_{counter}.ics"

    used_names.add(candidate)
    return candidate


def _text(value) -> str:
    if not value:
        return ""
    return str(value)


def _generate_uid() -> str:
    return f"generated-{uuid.uuid4()}"


def _normalize_boundary(value, *, is_start: bool) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, date):
        default_time = time.min if is_start else time.max
        return datetime.combine(value, default_time, tzinfo=timezone.utc)
    raise TypeError("Boundary must be a date or datetime")


def _maybe_datetime(value) -> datetime | None:
    if not value:
        return None
    dt = value.dt if hasattr(value, "dt") else value
    return _ensure_datetime(dt)


def _teams_for_event(event: Event) -> List[str]:
    summary = (event.summary or "").lower()
    if not summary:
        return []

    teams: Set[str] = set()

    if "schultraining" in summary:
        teams.add("Schultraining")

    if "getsgo" in summary and "start" in summary:
        teams.add("GetsGoStart")

    if re.search(r"\bx\s*(?:u)?14\b", summary):
        teams.update({"mU14", "wU14"})

    if re.search(r"\bm\s*(?:u)?14\b", summary):
        teams.add("mU14")

    if re.search(r"\bw\s*(?:u)?14\b", summary):
        teams.add("wU14")

    if re.search(r"\bw\s*(?:u)?12\s*[/\-]\s*14\b", summary):
        teams.update({"wU12", "wU14"})
    elif re.search(r"\bw\s*(?:u)?12\b", summary):
        teams.add("wU12")

    numbers: Set[str] = set()
    for match in re.finditer(r"\d+(?:\.\d+)?", summary):
        value = match.group(0)
        if value in {"9", "10", "11", "12", "12.1", "12.2"}:
            numbers.add(value)

    if "9" in numbers:
        teams.add("U9")
    if "10" in numbers:
        teams.add("U10")
    if "11" in numbers:
        teams.add("U11")
    if "12.1" in numbers:
        teams.add("U12.1")
    if "12.2" in numbers:
        teams.add("U12.2")
    if "12" in numbers and "12.1" not in numbers and "12.2" not in numbers:
        teams.update({"U12.1", "U12.2"})
    
    # U11/12 events should also go to wU12
    if "11" in numbers and "12" in numbers:
        teams.add("wU12")

    return sorted(teams)


def _event_matches_team(event: Event, team: str) -> bool:
    teams = _teams_for_event(event)
    return team in teams


def _new_team_calendar(team: str) -> Calendar:
    calendar = Calendar()
    calendar.add("prodid", "-//icsImporter//Team Calendar Export//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    name = f"Team {team}"
    calendar.add("name", name)
    calendar.add("x-wr-calname", name)
    return calendar


def _load_events(urls: Sequence[str]) -> Dict[str, List[Event]]:
    events_by_url: Dict[str, List[Event]] = {}
    for url in urls:
        ics_text = fetch_ics(url)
        events_by_url[url] = parse_events(ics_text)
    return events_by_url


def _calendar_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if "google" in hostname:
        return "Google Calendar"
    if "vereinsplaner" in hostname:
        return "Vereinsplaner"
    stem = Path(parsed.path).stem or "Calendar"
    return stem


def _calendar_filename_from_url(url: str, used: set[str]) -> str:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if "google" in hostname:
        base = "google"
    elif "vereinsplaner" in hostname:
        base = "vereinsplaner"
    else:
        base = Path(parsed.path).stem or "calendar"

    base = "".join(char for char in base if char.isalnum() or char in ("-", "_"))
    if not base:
        base = "calendar"

    candidate = f"{base}.ics"
    counter = 1
    while candidate in used:
        counter += 1
        candidate = f"{base}_{counter}.ics"

    used.add(candidate)
    return candidate

