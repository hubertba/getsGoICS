import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from ics_importer.inviter import (
    Event,
    create_invitation,
    export_calendars,
    export_team_calendars,
    fetch_ics,
    filter_events,
    generate_invites,
    import_invites,
    parse_events,
)


def unfold_ics(text: str) -> str:
    text = text.replace("\r\n ", "")
    text = text.replace("\n ", "")
    return text.replace("\r\n", "\n")


def test_fetch_ics(monkeypatch):
    captured = {}

    class DummyResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            captured["raised"] = True

    def fake_get(url, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        return DummyResponse("body")

    monkeypatch.setattr("ics_importer.inviter.requests.get", fake_get)

    result = fetch_ics("https://example.com/calendar.ics")

    assert result == "body"
    assert captured["url"] == "https://example.com/calendar.ics"
    assert captured["timeout"] == 10
    assert captured["raised"]


def sample_ics():
    return textwrap.dedent(
        """\
        BEGIN:VCALENDAR
        VERSION:2.0
        PRODID:-//Example Corp.//Calendar 1.0//EN
        BEGIN:VEVENT
        UID:123
        DTSTART:20241201T140000Z
        DTEND:20241201T150000Z
        SUMMARY:Sample Event
        DESCRIPTION:Event description
        LOCATION:Virtual
        URL:https://example.com/events/123
        STATUS:CONFIRMED
        TRANSP:OPAQUE
        CREATED:20231201T120000Z
        LAST-MODIFIED:20231202T130000Z
        END:VEVENT
        BEGIN:VEVENT
        UID:124
        DTSTART:20241202T100000Z
        DTEND:20241202T120000Z
        SUMMARY:Second Event
        END:VEVENT
        END:VCALENDAR
        """
    )


def google_sample_ics():
    return textwrap.dedent(
        """\
        BEGIN:VCALENDAR
        VERSION:2.0
        PRODID:-//Google Inc//Google Calendar 70.9054//EN
        BEGIN:VEVENT
        UID:google-2025
        DTSTART:20250301T100000Z
        DTEND:20250301T120000Z
        SUMMARY:Google Event 2025
        END:VEVENT
        BEGIN:VEVENT
        UID:google-2026
        DTSTART:20260301T100000Z
        DTEND:20260301T120000Z
        SUMMARY:Google Event 2026
        END:VEVENT
        END:VCALENDAR
        """
    )


def test_parse_events_returns_dataclasses():
    events = parse_events(sample_ics())

    assert len(events) == 2

    first, second = events
    assert isinstance(first, Event)
    assert first.uid == "123"
    assert first.summary == "Sample Event"
    assert first.description == "Event description"
    assert first.location == "Virtual"
    assert first.url == "https://example.com/events/123"
    assert first.start == datetime(2024, 12, 1, 14, 0, tzinfo=timezone.utc)
    assert first.end == datetime(2024, 12, 1, 15, 0, tzinfo=timezone.utc)
    assert first.status == "CONFIRMED"
    assert first.transparency == "OPAQUE"
    assert first.created == datetime(2023, 12, 1, 12, 0, tzinfo=timezone.utc)
    assert first.last_modified == datetime(2023, 12, 2, 13, 0, tzinfo=timezone.utc)

    assert second.uid == "124"
    assert second.summary == "Second Event"
    assert second.description == ""
    assert second.location == ""
    assert second.url == ""
    assert second.start == datetime(2024, 12, 2, 10, 0, tzinfo=timezone.utc)
    assert second.end == datetime(2024, 12, 2, 12, 0, tzinfo=timezone.utc)
    assert second.status == ""
    assert second.transparency == ""
    assert second.created is None
    assert second.last_modified is None


def test_filter_events_by_date_range():
    events = [
        Event(
            uid="early",
            summary="Early Event",
            description="",
            location="",
            url="",
            start=datetime(2024, 11, 30, 9, 0, tzinfo=timezone.utc),
            end=datetime(2024, 11, 30, 10, 0, tzinfo=timezone.utc),
        ),
        Event(
            uid="within",
            summary="Within Range",
            description="",
            location="",
            url="",
            start=datetime(2024, 12, 5, 9, 0, tzinfo=timezone.utc),
            end=datetime(2024, 12, 5, 10, 0, tzinfo=timezone.utc),
        ),
        Event(
            uid="late",
            summary="Late Event",
            description="",
            location="",
            url="",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        ),
    ]

    filtered = filter_events(
        events,
        start=datetime(2024, 12, 1, tzinfo=timezone.utc),
        end=datetime(2024, 12, 31, tzinfo=timezone.utc),
    )

    assert [event.uid for event in filtered] == ["within"]


def test_filter_events_excludes_keywords():
    events = [
        Event(
            uid="keep",
            summary="Regular training",
            description="",
            location="",
            url="",
            start=datetime(2025, 1, 5, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 5, 10, 0, tzinfo=timezone.utc),
        ),
        Event(
            uid="drop9",
            summary="BBV U9 Turnier",
            description="",
            location="",
            url="",
            start=datetime(2025, 1, 6, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 6, 10, 0, tzinfo=timezone.utc),
        ),
        Event(
            uid="drop10",
            summary="Testspiel u10 Squad",
            description="",
            location="",
            url="",
            start=datetime(2025, 1, 7, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 7, 10, 0, tzinfo=timezone.utc),
        ),
    ]

    filtered = filter_events(events, exclude_keywords=["U9", "u10"])

    assert [event.uid for event in filtered] == ["keep"]


def test_filter_events_excludes_additional_keywords():
    events = [
        Event(
            uid="keep",
            summary="Regular training",
            description="",
            location="",
            url="",
            start=datetime(2025, 1, 5, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 5, 10, 0, tzinfo=timezone.utc),
        ),
        Event(
            uid="drop",
            summary="Schultraining Spezial",
            description="",
            location="",
            url="",
            start=datetime(2025, 1, 6, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 6, 10, 0, tzinfo=timezone.utc),
        ),
    ]

    filtered = filter_events(events, exclude_keywords=["Schultraining"])

    assert [event.uid for event in filtered] == ["keep"]


def test_export_calendars_writes_files(monkeypatch, tmp_path: Path):
    urls = [
        "https://api.vereinsplaner.at/v1/public/ical/example.ics",
        "https://calendar.google.com/calendar/ical/getsgostadtschlaining%40gmail.com/public/basic.ics",
    ]

    responses = {
        urls[0]: sample_ics(),
        urls[1]: google_sample_ics(),
    }

    def fake_fetch(url, timeout=10):
        return responses[url]

    monkeypatch.setattr("ics_importer.inviter.fetch_ics", fake_fetch)

    written = export_calendars(
        urls=urls,
        output_dir=tmp_path,
        start=datetime(2024, 12, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 1, tzinfo=timezone.utc),
        exclude_keywords=["U10"],
    )

    assert set(written.keys()) == set(urls)
    google_file = written[urls[1]]
    assert google_file.name == "google.ics"
    content = google_file.read_text()
    assert "Google Event 2025" in content
    assert "Google Event 2026" not in content


def test_export_team_calendars_creates_team_files(monkeypatch, tmp_path: Path):
    url = "https://api.vereinsplaner.at/v1/public/ical/teams.ics"
    ics = textwrap.dedent(
        """\
        BEGIN:VCALENDAR
        VERSION:2.0
        PRODID:-//Example Corp.//Calendar 1.0//EN
        BEGIN:VEVENT
        UID:u9-1
        DTSTART:20251205T100000Z
        DTEND:20251205T110000Z
        SUMMARY:Training U9
        END:VEVENT
        BEGIN:VEVENT
        UID:u11-1
        DTSTART:20251205T120000Z
        DTEND:20251205T130000Z
        SUMMARY:Training U11 Elite
        END:VEVENT
        BEGIN:VEVENT
        UID:mu14-1
        DTSTART:20251206T120000Z
        DTEND:20251206T140000Z
        SUMMARY:Scrimmage mU14
        END:VEVENT
        BEGIN:VEVENT
        UID:u12-1
        DTSTART:20251208T150000Z
        DTEND:20251208T160000Z
        SUMMARY:Training U12
        END:VEVENT
        BEGIN:VEVENT
        UID:u12_1-1
        DTSTART:20251209T150000Z
        DTEND:20251209T160000Z
        SUMMARY:Training U12.1
        END:VEVENT
        BEGIN:VEVENT
        UID:u12_2-1
        DTSTART:20251210T150000Z
        DTEND:20251210T160000Z
        SUMMARY:Training U12.2
        END:VEVENT
        BEGIN:VEVENT
        UID:xu14-1
        DTSTART:20251207T090000Z
        DTEND:20251207T100000Z
        SUMMARY:Turnier xU14 Auswahl
        END:VEVENT
        BEGIN:VEVENT
        UID:wu12-1
        DTSTART:20251207T110000Z
        DTEND:20251207T120000Z
        SUMMARY:Training wU12
        END:VEVENT
        BEGIN:VEVENT
        UID:wu12_14-1
        DTSTART:20251207T130000Z
        DTEND:20251207T140000Z
        SUMMARY:Training wU12/14
        END:VEVENT
        BEGIN:VEVENT
        UID:u11_12-1
        DTSTART:20251207T150000Z
        DTEND:20251207T160000Z
        SUMMARY:Training U11/12
        END:VEVENT
        BEGIN:VEVENT
        UID:u9_10-1
        DTSTART:20251208T080000Z
        DTEND:20251208T090000Z
        SUMMARY:Freundschaftsspiel 9/10/11
        END:VEVENT
        BEGIN:VEVENT
        UID:schul-1
        DTSTART:20251211T080000Z
        DTEND:20251211T090000Z
        SUMMARY:Schultraining Basics
        END:VEVENT
        BEGIN:VEVENT
        UID:start-1
        DTSTART:20251212T080000Z
        DTEND:20251212T090000Z
        SUMMARY:GetsGoStart Intro
        END:VEVENT
        END:VCALENDAR
        """
    )

    monkeypatch.setattr("ics_importer.inviter.fetch_ics", lambda url, timeout=10: ics)

    written = export_team_calendars(
        urls=[url],
        output_dir=tmp_path,
        start=datetime(2025, 12, 1, tzinfo=timezone.utc),
        end=datetime(2025, 12, 31, tzinfo=timezone.utc),
    )

    assert set(written.keys()) == {
        "U9",
        "U10",
        "U11",
        "mU14",
        "wU14",
        "wU12",
        "U12.1",
        "U12.2",
        "Schultraining",
        "GetsGoStart",
    }
    assert written["U9"].name == "U9.ics"
    assert "Training U9" in written["U9"].read_text()
    assert "Freundschaftsspiel 9/10/11" in written["U9"].read_text()
    assert "Freundschaftsspiel 9/10/11" in written["U10"].read_text()
    assert "Freundschaftsspiel 9/10/11" in written["U11"].read_text()
    assert "Training U11 Elite" in written["U11"].read_text()
    assert "Scrimmage mU14" in written["mU14"].read_text()
    assert "Turnier xU14 Auswahl" in written["wU14"].read_text()
    assert "Training wU12/14" in written["wU14"].read_text()
    assert "Training wU12" in written["wU12"].read_text()
    assert "Training wU12/14" in written["wU12"].read_text()
    assert "Training U11/12" in written["wU12"].read_text()
    assert "Training U12" in written["U12.1"].read_text()
    assert "Training U12" in written["U12.2"].read_text()
    assert "Training U12.1" in written["U12.1"].read_text()
    assert "Training U12.2" in written["U12.2"].read_text()
    assert "Schultraining Basics" in written["Schultraining"].read_text()
    assert "GetsGoStart Intro" in written["GetsGoStart"].read_text()


def test_create_invitation_contains_required_fields():
    event = Event(
        uid="123",
        summary="Sample Event",
        description="Event description",
        location="Virtual",
        url="https://example.com/events/123",
        start=datetime(2024, 12, 1, 14, 0, tzinfo=timezone.utc),
        end=datetime(2024, 12, 1, 15, 0, tzinfo=timezone.utc),
        status="CONFIRMED",
        transparency="OPAQUE",
        created=datetime(2023, 12, 1, 12, 0, tzinfo=timezone.utc),
        last_modified=datetime(2023, 12, 2, 13, 0, tzinfo=timezone.utc),
    )

    invite = create_invitation(
        event,
        attendee_email="user@example.com",
        organizer_email="organizer@example.com",
        attendee_name="User Example",
    )

    invite = unfold_ics(invite)

    assert "METHOD:REQUEST" in invite
    assert "BEGIN:VEVENT" in invite
    assert "UID:123" in invite
    assert "SUMMARY:Sample Event" in invite
    assert "DTSTART:20241201T140000Z" in invite
    assert (
        'ATTENDEE;CN="User Example";PARTSTAT=NEEDS-ACTION;ROLE=REQ-PARTICIPANT;RSVP=TRUE:MAILTO:user@example.com'
        in invite
    )
    assert "ORGANIZER;CN=organizer@example.com:MAILTO:organizer@example.com" in invite
    assert "STATUS:CONFIRMED" in invite
    assert "TRANSP:OPAQUE" in invite
    assert "CREATED:20231201T120000Z" in invite
    assert "LAST-MODIFIED:20231202T130000Z" in invite


def test_generate_invites_writes_files(tmp_path: Path):
    events = parse_events(sample_ics())

    written = generate_invites(
        events,
        attendee_email="user@example.com",
        output_dir=tmp_path,
        attendee_name="User Example",
    )

    assert len(written) == 2
    for path in written:
        assert path.exists()
        assert path.suffix == ".ics"
        content = unfold_ics(path.read_text())
        assert "METHOD:REQUEST" in content
        assert 'ATTENDEE;CN="User Example"' in content


def test_import_invites_combines_sources_and_filters(monkeypatch, tmp_path: Path):
    urls = [
        "https://source.example/vereinsplaner.ics",
        "https://source.example/google.ics",
    ]

    responses = {
        urls[0]: sample_ics(),
        urls[1]: google_sample_ics(),
    }

    calls = []

    def fake_fetch(url, timeout=10):
        calls.append((url, timeout))
        return responses[url]

    monkeypatch.setattr("ics_importer.inviter.fetch_ics", fake_fetch)

    written = import_invites(
        urls=urls,
        attendee_email="user@example.com",
        attendee_name="User Example",
        organizer_email="organizer@example.com",
        output_dir=tmp_path,
        start=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        exclude_keywords=["U9", "U10"],
    )

    assert calls == [(urls[0], 10), (urls[1], 10)]
    assert len(written) == 1
    assert written[0].name == "google-2025.ics"
    content = unfold_ics(written[0].read_text())
    assert "SUMMARY:Google Event 2025" in content