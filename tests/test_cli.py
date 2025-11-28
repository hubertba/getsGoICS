import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ics_importer import cli


def test_main_invokes_import_with_filters(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_import_invites(
        urls,
        attendee_email,
        output_dir,
        start,
        end,
        organizer_email,
        attendee_name,
        exclude_keywords,
    ):
        captured.update(
            {
                "urls": urls,
                "attendee_email": attendee_email,
                "output_dir": output_dir,
                "start": start,
                "end": end,
                "organizer_email": organizer_email,
                "attendee_name": attendee_name,
                "exclude_keywords": exclude_keywords,
            }
        )
        return [Path(output_dir) / "dummy.ics"]

    monkeypatch.setattr(cli, "import_invites", fake_import_invites)

    args = [
        "--attendee-email",
        "user@example.com",
        "--attendee-name",
        "User Example",
        "--organizer-email",
        "organizer@example.com",
        "--output-dir",
        str(tmp_path),
        "--start",
        "2025-01-01",
        "--end",
        "2025-12-31",
        "https://example.com/a.ics",
        "https://example.com/b.ics",
    ]

    exit_code = cli.main(args)

    assert exit_code == 0
    assert captured["urls"] == ["https://example.com/a.ics", "https://example.com/b.ics"]
    assert captured["attendee_email"] == "user@example.com"
    assert captured["attendee_name"] == "User Example"
    assert captured["organizer_email"] == "organizer@example.com"
    assert captured["output_dir"] == Path(tmp_path)
    assert captured["start"] == date(2025, 1, 1)
    assert captured["end"] == date(2025, 12, 31)
    assert captured["exclude_keywords"] == ["U9", "U10", "Schultraining"]


def test_main_allows_missing_dates(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_import_invites(
        urls,
        attendee_email,
        output_dir,
        start,
        end,
        organizer_email,
        attendee_name,
        exclude_keywords,
    ):
        captured.update({"start": start, "end": end, "exclude_keywords": exclude_keywords})
        return []

    monkeypatch.setattr(cli, "import_invites", fake_import_invites)

    args = [
        "--attendee-email",
        "user@example.com",
        "--output-dir",
        str(tmp_path),
        "https://example.com/a.ics",
    ]

    exit_code = cli.main(args)

    assert exit_code == 0
    assert captured["start"] is None
    assert captured["end"] is None
    assert captured["exclude_keywords"] == ["U9", "U10", "Schultraining"]


def test_main_aggregate_mode(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_export_calendars(
        urls,
        output_dir,
        start,
        end,
        exclude_keywords,
    ):
        captured.update(
            {
                "urls": urls,
                "output_dir": output_dir,
                "start": start,
                "end": end,
                "exclude_keywords": exclude_keywords,
            }
        )
        return {urls[0]: Path(output_dir) / "vereinsplaner.ics"}

    monkeypatch.setattr(cli, "export_calendars", fake_export_calendars)

    def fail_import_invites(*args, **kwargs):
        raise AssertionError("import_invites should not be called in aggregate mode")

    monkeypatch.setattr(cli, "import_invites", fail_import_invites)

    args = [
        "--aggregate",
        "--attendee-email",
        "user@example.com",
        "--output-dir",
        str(tmp_path),
        "--start",
        "2025-01-01",
        "https://example.com/a.ics",
    ]

    exit_code = cli.main(args)

    assert exit_code == 0
    assert captured["urls"] == ["https://example.com/a.ics"]
    assert captured["output_dir"] == Path(tmp_path)
    assert captured["start"] == date(2025, 1, 1)
    assert captured["end"] is None
    assert captured["exclude_keywords"] == ["U9", "U10", "Schultraining"]


def test_main_team_calendars(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_export_team_calendars(
        urls,
        output_dir,
        start,
        end,
        exclude_keywords,
    ):
        captured.update(
            {
                "urls": urls,
                "output_dir": output_dir,
                "start": start,
                "end": end,
                "exclude_keywords": exclude_keywords,
            }
        )
        return {"U9": Path(output_dir) / "U9.ics"}

    def fail_import_invites(*args, **kwargs):
        raise AssertionError("import_invites should not be called in team mode")

    def fail_export_calendars(*args, **kwargs):
        raise AssertionError("export_calendars should not be called in team mode")

    monkeypatch.setattr(cli, "export_team_calendars", fake_export_team_calendars)
    monkeypatch.setattr(cli, "import_invites", fail_import_invites)
    monkeypatch.setattr(cli, "export_calendars", fail_export_calendars)

    args = [
        "--team-calendars",
        "--attendee-email",
        "user@example.com",
        "--output-dir",
        str(tmp_path),
        "--start",
        "2025-12-01",
        "--end",
        "2025-12-31",
        "https://example.com/a.ics",
    ]

    exit_code = cli.main(args)

    assert exit_code == 0
    assert captured["urls"] == ["https://example.com/a.ics"]
    assert captured["output_dir"] == Path(tmp_path)
    assert captured["start"] == date(2025, 12, 1)
    assert captured["end"] == date(2025, 12, 31)
    assert captured["exclude_keywords"] == ["Schultraining"]

