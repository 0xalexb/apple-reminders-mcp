from __future__ import annotations

import threading
from importlib.metadata import version

from mcp.server import MCPServer

from apple_reminders_mcp import operations
from apple_reminders_mcp.eventkit_service import EventKitService
from apple_reminders_mcp.formatting import _format_reminder

mcp = MCPServer("apple-reminders", version=version("apple-reminders-mcp"))

_service: EventKitService | None = None
_service_lock = threading.Lock()


def _get_service() -> EventKitService:
    global _service
    with _service_lock:
        if _service is None:
            _service = EventKitService()
        return _service


@mcp.tool()
def ping() -> str:
    """Health check - returns pong."""
    return "pong"


@mcp.tool()
def list_reminder_lists() -> list[dict]:
    """Returns one row per reminder list.

    Each row carries id, name, incomplete_count, color ('#rrggbb'), source_name
    (the account it lives in), source_type
    (local/exchange/caldav/mobileme/subscribed/birthdays), writable and
    is_subscribed.
    """
    return operations.list_reminder_lists(_get_service())


@mcp.tool()
def create_list(name: str) -> dict:
    """Creates a new reminder list."""
    return operations.create_list(_get_service(), name)


@mcp.tool()
def show_incomplete_reminders(
    list_name: str | None = None, list_id: str | None = None
) -> list[dict]:
    """Returns incomplete reminders for a specific list.

    Each carries id, title, due_date, priority, notes, list, list_id,
    is_completed, start_date, url, location, created_at, last_modified_at,
    external_id and time_zone, plus alarms, recurrence and attendees when the
    reminder has them. Provide list_name, list_id (preferred, unique and stable
    across renames), or both.
    """
    return operations.show_incomplete_reminders(_get_service(), list_name, list_id)


@mcp.tool()
def show_all_incomplete_reminders() -> dict:
    """Returns all incomplete reminders as an object keyed by list name.

    A reminder with no list lands under 'Unknown'; each reminder carries the
    same fields as show_incomplete_reminders. Two lists sharing a name share one
    bucket; their rows stay separable by list_id.
    """
    return operations.show_all_incomplete_reminders(_get_service())


@mcp.tool()
def show_completed_reminders_today(day: str | None = None) -> list[dict]:
    """Returns reminders completed on the given day.

    The day is an ISO date YYYY-MM-DD and defaults to today; each reminder
    carries completion_date alongside the same fields as
    show_incomplete_reminders.
    """
    return operations.show_completed_reminders_today(_get_service(), day)


@mcp.tool()
def create_reminder(
    title: str,
    list_name: str | None = None,
    list_id: str | None = None,
    due_date: str | None = None,
    priority: str = "none",
    recurrence: str | None = None,
    notes: str | None = None,
) -> dict:
    """Creates a reminder. Optional: list_name or list_id (preferred, unique and stable across renames; defaults to the default list), due_date (ISO 8601 e.g. '2026-03-15' or '2026-03-15T10:30:00'), priority (none/low/medium/high), recurrence (daily/weekly/monthly/yearly), notes."""
    return operations.create_reminder(
        _get_service(),
        title,
        list_name,
        list_id,
        due_date,
        priority,
        recurrence,
        notes,
    )


@mcp.tool()
def complete_reminder(reminder_id: str) -> dict:
    """Marks a reminder as completed. Takes the reminder's id."""
    return operations.complete_reminder(_get_service(), reminder_id)


@mcp.tool()
def delete_reminder(reminder_id: str) -> dict:
    """Deletes a reminder. Takes the reminder's id."""
    return operations.delete_reminder(_get_service(), reminder_id)


@mcp.tool()
def move_reminder(
    reminder_id: str,
    target_list_name: str | None = None,
    target_list_id: str | None = None,
) -> dict:
    """Moves a reminder to a different list. Provide target_list_name, target_list_id (preferred, unique and stable across renames), or both."""
    return operations.move_reminder(
        _get_service(), reminder_id, target_list_name, target_list_id
    )


@mcp.tool()
def update_reminder(
    reminder_id: str,
    title: str | None = None,
    notes: str | None = None,
    append_notes: str | None = None,
) -> dict:
    """Updates a reminder's title and notes; omitted fields are left as they are. Takes the reminder's id. append_notes adds its text on a new line after the existing notes (or becomes the notes when there are none) and cannot be combined with notes."""
    service = _get_service()
    reminder = service.update_reminder(
        reminder_id, title=title, notes=notes, append_notes=append_notes
    )
    return _format_reminder(reminder)


@mcp.tool()
def find_reminders(
    list_name: str | None = None,
    list_id: str | None = None,
    query: str | None = None,
) -> list[dict]:
    """Returns open reminders whose title contains query, case-insensitively; with no query, every open reminder. Provide list_name or list_id (preferred, unique and stable across renames) to search one list; with neither, every list is searched. Each reminder carries the same fields as show_incomplete_reminders."""
    return operations.find_reminders(_get_service(), list_name, list_id, query)


@mcp.tool()
def quick_capture(title: str, notes: str | None = None) -> dict:
    """Quickly captures a reminder in the default list with no date or priority. Optimized for fast idea capture."""
    return operations.quick_capture(_get_service(), title, notes)


def main():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-V"):
        print(f"apple-reminders-mcp {version('apple-reminders-mcp')}")
        sys.exit(0)
    mcp.run()


if __name__ == "__main__":
    main()
