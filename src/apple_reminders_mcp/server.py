from __future__ import annotations

import threading
from datetime import date, datetime
from importlib.metadata import version

from mcp.server import MCPServer

from apple_reminders_mcp.eventkit_service import EventKitService
from apple_reminders_mcp.formatting import (
    _format_completed_reminder,
    _format_reminder,
    _format_source_type,
)

mcp = MCPServer("apple-reminders", version=version("apple-reminders-mcp"))

_service: EventKitService | None = None
_service_lock = threading.Lock()


def _get_service() -> EventKitService:
    global _service
    with _service_lock:
        if _service is None:
            _service = EventKitService()
        return _service


_PRIORITY_VALUES = {"none": 0, "low": 9, "medium": 5, "high": 1}


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
    service = _get_service()
    lists = service.get_all_lists()
    all_reminders = service.get_all_incomplete_reminders()
    counts: dict[str, int] = {}
    for r in all_reminders:
        cal = r.calendar()
        if cal:
            cal_id = cal.calendarIdentifier()
            counts[cal_id] = counts.get(cal_id, 0) + 1
    rows = []
    for cal in lists:
        cal_id = cal.calendarIdentifier()
        source = cal.source()
        rows.append(
            {
                "id": cal_id,
                "name": cal.title(),
                "incomplete_count": counts.get(cal_id, 0),
                "color": service.calendar_color_hex(cal),
                "source_name": source.title() if source else None,
                "source_type": (
                    _format_source_type(source.sourceType()) if source else None
                ),
                "writable": cal.allowsContentModifications(),
                "is_subscribed": cal.isSubscribed(),
            }
        )
    return rows


@mcp.tool()
def create_list(name: str) -> dict:
    """Creates a new reminder list."""
    service = _get_service()
    cal = service.create_list(name)
    return {"name": cal.title(), "created": True}


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
    service = _get_service()
    reminders = service.get_incomplete_reminders(list_name, list_id)
    return [_format_reminder(r) for r in reminders]


@mcp.tool()
def show_all_incomplete_reminders() -> dict:
    """Returns all incomplete reminders as an object keyed by list name.

    A reminder with no list lands under 'Unknown'; each reminder carries the
    same fields as show_incomplete_reminders. Two lists sharing a name share one
    bucket; their rows stay separable by list_id.
    """
    service = _get_service()
    reminders = service.get_all_incomplete_reminders()
    grouped: dict[str, list[dict]] = {}
    for r in reminders:
        list_name = r.calendar().title() if r.calendar() else "Unknown"
        if list_name not in grouped:
            grouped[list_name] = []
        grouped[list_name].append(_format_reminder(r))
    return grouped


@mcp.tool()
def show_completed_reminders_today(day: str | None = None) -> list[dict]:
    """Returns reminders completed on the given day.

    The day is an ISO date YYYY-MM-DD and defaults to today; each reminder
    carries completion_date alongside the same fields as
    show_incomplete_reminders.
    """
    service = _get_service()
    target_day = date.fromisoformat(day) if day else None
    reminders = service.get_completed_reminders_for_day(target_day)
    return [_format_completed_reminder(r) for r in reminders]


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
    service = _get_service()
    priority_lower = priority.lower()
    if priority_lower not in _PRIORITY_VALUES:
        raise ValueError(
            f"Invalid priority '{priority}'. "
            f"Must be one of: {', '.join(_PRIORITY_VALUES)}"
        )
    priority_int = _PRIORITY_VALUES[priority_lower]
    parsed_due: datetime | None = None
    has_time = False
    if due_date:
        parsed_due = datetime.fromisoformat(due_date)
        has_time = len(due_date) > 10
    reminder = service.create_reminder(
        title=title,
        list_name=list_name,
        list_id=list_id,
        due_date=parsed_due,
        priority=priority_int,
        recurrence=recurrence,
        notes=notes,
        include_time=has_time,
    )
    return _format_reminder(reminder)


@mcp.tool()
def complete_reminder(reminder_id: str) -> dict:
    """Marks a reminder as completed. Takes the reminder's id."""
    service = _get_service()
    reminder = service.complete_reminder(reminder_id)
    return {"id": reminder.calendarItemIdentifier(), "completed": True}


@mcp.tool()
def delete_reminder(reminder_id: str) -> dict:
    """Deletes a reminder. Takes the reminder's id."""
    service = _get_service()
    service.delete_reminder(reminder_id)
    return {"id": reminder_id, "deleted": True}


@mcp.tool()
def move_reminder(
    reminder_id: str,
    target_list_name: str | None = None,
    target_list_id: str | None = None,
) -> dict:
    """Moves a reminder to a different list. Provide target_list_name, target_list_id (preferred, unique and stable across renames), or both."""
    service = _get_service()
    reminder = service.move_reminder(reminder_id, target_list_name, target_list_id)
    return _format_reminder(reminder)


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
    service = _get_service()
    reminders = service.find_reminders(list_name=list_name, list_id=list_id, query=query)
    return [_format_reminder(r) for r in reminders]


@mcp.tool()
def quick_capture(title: str, notes: str | None = None) -> dict:
    """Quickly captures a reminder in the default list with no date or priority. Optimized for fast idea capture."""
    service = _get_service()
    reminder = service.create_reminder(title=title, notes=notes)
    return _format_reminder(reminder)


def main():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-V"):
        print(f"apple-reminders-mcp {version('apple-reminders-mcp')}")
        sys.exit(0)
    mcp.run()


if __name__ == "__main__":
    main()
