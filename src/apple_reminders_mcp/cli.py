from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable

from apple_reminders_mcp import operations
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

    sub.add_parser("lists", help="every reminder list")

    create_list = sub.add_parser("create-list", help="create a reminder list")
    create_list.add_argument("--name", required=True)

    incomplete = sub.add_parser("incomplete", help="incomplete reminders of one list")
    incomplete.add_argument("--list-name")
    incomplete.add_argument("--list-id")

    sub.add_parser("all-incomplete", help="incomplete reminders of every list, keyed by list name")

    completed = sub.add_parser("completed-today", help="reminders completed on a day")
    completed.add_argument("--day", help="ISO date YYYY-MM-DD, default today")

    complete = sub.add_parser("complete", help="mark a reminder completed")
    complete.add_argument("--reminder-id", required=True)

    delete = sub.add_parser("delete", help="delete a reminder")
    delete.add_argument("--reminder-id", required=True)

    move = sub.add_parser("move", help="move a reminder to another list")
    move.add_argument("--reminder-id", required=True)
    move.add_argument("--target-list-name")
    move.add_argument("--target-list-id")

    quick = sub.add_parser("quick-capture", help="capture a reminder in the default list")
    quick.add_argument("--title", required=True)
    quick.add_argument("--notes")

    find = sub.add_parser("find", help="open reminders, optionally by list and title substring")
    find.add_argument("--list", dest="list_name")
    find.add_argument("--list-id")
    find.add_argument("--query")

    create = sub.add_parser("create", help="create a reminder")
    create.add_argument("--list", dest="list_name")
    create.add_argument("--list-id")
    create.add_argument("--title", required=True)
    create.add_argument("--due-date", help="ISO 8601, e.g. 2026-03-15 or 2026-03-15T10:30:00")
    create.add_argument("--priority", default="none", help="none, low, medium or high")
    create.add_argument("--recurrence", help="daily, weekly, monthly or yearly")
    create.add_argument("--notes")

    update = sub.add_parser("update", help="change a reminder's title or notes")
    update.add_argument("reminder_id")
    update.add_argument("--title")
    notes = update.add_mutually_exclusive_group()
    notes.add_argument("--notes")
    notes.add_argument("--append-notes")
    return parser


def _update(service: EventKitService, args: argparse.Namespace) -> object:
    reminder = service.update_reminder(
        args.reminder_id,
        title=args.title,
        notes=args.notes,
        append_notes=args.append_notes,
    )
    return _format_reminder(reminder)


_COMMANDS: dict[str, Callable[[EventKitService, argparse.Namespace], object]] = {
    "lists": lambda s, a: operations.list_reminder_lists(s),
    "create-list": lambda s, a: operations.create_list(s, a.name),
    "incomplete": lambda s, a: operations.show_incomplete_reminders(
        s, a.list_name, a.list_id
    ),
    "all-incomplete": lambda s, a: operations.show_all_incomplete_reminders(s),
    "completed-today": lambda s, a: operations.show_completed_reminders_today(s, a.day),
    "complete": lambda s, a: operations.complete_reminder(s, a.reminder_id),
    "delete": lambda s, a: operations.delete_reminder(s, a.reminder_id),
    "move": lambda s, a: operations.move_reminder(
        s, a.reminder_id, a.target_list_name, a.target_list_id
    ),
    "quick-capture": lambda s, a: operations.quick_capture(s, a.title, a.notes),
    "find": lambda s, a: operations.find_reminders(s, a.list_name, a.list_id, a.query),
    "create": lambda s, a: operations.create_reminder(
        s,
        a.title,
        a.list_name,
        a.list_id,
        a.due_date,
        a.priority,
        a.recurrence,
        a.notes,
    ),
    "update": _update,
}


def _run(args: argparse.Namespace) -> object:
    service = EventKitService()
    return _COMMANDS[args.command](service, args)


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
    payload = json.dumps(result, ensure_ascii=False) + "\n"
    sys.stdout.write(payload)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
