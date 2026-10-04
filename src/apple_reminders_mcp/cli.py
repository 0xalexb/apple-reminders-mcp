from __future__ import annotations

import argparse
import json
import sys

from apple_reminders_mcp.eventkit_service import EventKitService
from apple_reminders_mcp.formatting import _format_reminder

EXIT_OK = 0
EXIT_BAD_INPUT = 1
EXIT_NO_ACCESS = 2


class _Parser(argparse.ArgumentParser):
    # argparse exits 2 on a usage error, which callers would read as "access denied".
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        sys.exit(EXIT_BAD_INPUT)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="reminders",
        description="Apple Reminders from the shell. JSON on stdout, errors on stderr.",
        epilog="Exit codes: 0 ok, 1 not found or bad input, 2 Reminders access denied or timed out.",
    )
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    find = sub.add_parser("find", help="open reminders in a list, optionally by title substring")
    find.add_argument("--list", required=True, dest="list_name")
    find.add_argument("--query")

    create = sub.add_parser("create", help="create a reminder")
    create.add_argument("--list", required=True, dest="list_name")
    create.add_argument("--title", required=True)
    create.add_argument("--notes")

    update = sub.add_parser("update", help="change a reminder's title or notes")
    update.add_argument("reminder_id")
    update.add_argument("--title")
    notes = update.add_mutually_exclusive_group()
    notes.add_argument("--notes")
    notes.add_argument("--append-notes")
    return parser


def _run(args: argparse.Namespace) -> object:
    service = EventKitService()
    if args.command == "find":
        reminders = service.find_reminders(list_name=args.list_name, query=args.query)
        return [_format_reminder(r) for r in reminders]
    if args.command == "create":
        reminder = service.create_reminder(
            title=args.title, list_name=args.list_name, notes=args.notes
        )
        return _format_reminder(reminder)
    reminder = service.update_reminder(
        args.reminder_id,
        title=args.title,
        notes=args.notes,
        append_notes=args.append_notes,
    )
    return _format_reminder(reminder)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = _run(args)
    except (PermissionError, TimeoutError) as exc:
        print(f"reminders: {exc}", file=sys.stderr)
        return EXIT_NO_ACCESS
    except (ValueError, RuntimeError) as exc:
        print(f"reminders: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
