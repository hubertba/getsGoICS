from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence

from .inviter import export_calendars, export_team_calendars, import_invites


def parse_boundary(value: str) -> datetime | date:
    if "T" in value:
        try:
            dt = datetime.fromisoformat(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid datetime value: {value}") from exc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date value: {value}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate RSVP-friendly invites from one or more ICS feeds."
    )
    parser.add_argument(
        "urls",
        nargs="+",
        help="One or more ICS URLs to import (e.g. Vereinsplaner, Google Calendar).",
    )
    parser.add_argument(
        "--attendee-email",
        required=True,
        help="Email of the attendee who will receive the invitations.",
    )
    parser.add_argument(
        "--attendee-name",
        help="Display name of the attendee (defaults to attendee email).",
    )
    parser.add_argument(
        "--organizer-email",
        help="Email address to set as the organizer (defaults to attendee email).",
    )
    parser.add_argument(
        "--output-dir",
        default="invites",
        help="Directory where invitation files should be written (default: invites).",
    )
    parser.add_argument(
        "--start",
        type=parse_boundary,
        help="Only import events starting on/after this ISO date (YYYY-MM-DD) or datetime.",
    )
    parser.add_argument(
        "--end",
        type=parse_boundary,
        help="Only import events starting on/before this ISO date (YYYY-MM-DD) or datetime.",
    )
    parser.add_argument(
        "--exclude-keyword",
        action="append",
        dest="exclude_keywords",
        help=(
            "Exclude events whose summary contains this keyword (case-insensitive). "
            "Can be provided multiple times. Defaults to filtering out U9, U10, and Schultraining events."
        ),
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--aggregate",
        action="store_true",
        help="Combine events per source into standalone ICS files instead of invitations.",
    )
    mode_group.add_argument(
        "--team-calendars",
        action="store_true",
        help="Generate separate ICS files for each team (U9, U10, U12.1, U12, mU14, wU14).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress informational output.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    if args.exclude_keywords is not None:
        exclude_keywords = args.exclude_keywords
    elif args.team_calendars:
        exclude_keywords = ["Schultraining"]
    else:
        exclude_keywords = ["U9", "U10", "Schultraining"]

    if args.aggregate:
        written = export_calendars(
            urls=list(args.urls),
            output_dir=output_dir,
            start=args.start,
            end=args.end,
            exclude_keywords=exclude_keywords,
        )

        if not args.quiet:
            resolved = output_dir.resolve()
            print(f"Wrote {len(written)} calendar files to {resolved}")
            for url, path in written.items():
                print(f" - {path.name}: {url}")

        return 0

    if args.team_calendars:
        written = export_team_calendars(
            urls=list(args.urls),
            output_dir=output_dir,
            start=args.start,
            end=args.end,
            exclude_keywords=exclude_keywords,
        )

        if not args.quiet:
            resolved = output_dir.resolve()
            print(f"Wrote {len(written)} team calendars to {resolved}")
            for team, path in written.items():
                print(f" - {path.name}: {team}")

        return 0

    written = import_invites(
        urls=list(args.urls),
        attendee_email=args.attendee_email,
        attendee_name=args.attendee_name,
        organizer_email=args.organizer_email,
        output_dir=output_dir,
        start=args.start,
        end=args.end,
        exclude_keywords=exclude_keywords,
    )

    if not args.quiet:
        print(f"Wrote {len(written)} invitation files to {output_dir.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

