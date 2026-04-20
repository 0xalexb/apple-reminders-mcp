from __future__ import annotations

import threading
from datetime import date, datetime

from mcp.server.fastmcp import FastMCP

from apple_reminders_mcp.eventkit_service import EventKitService

mcp = FastMCP("apple-reminders")

_service: EventKitService | None = None
_service_lock = threading.Lock()


def _get_service() -> EventKitService:
    global _service
    with _service_lock:
        if _service is None:
            _service = EventKitService()
        return _service


_PRIORITY_LABELS = {0: "none", 1: "high", 5: "medium", 9: "low"}
_PRIORITY_VALUES = {"none": 0, "low": 9, "medium": 5, "high": 1}


def _format_priority(priority: int) -> str:
    return _PRIORITY_LABELS.get(priority, f"custom({priority})")


def _format_due_date(components) -> str | None:
    if components is None:
        return None
    year = components.year()
    month = components.month()
    day = components.day()
    hour = components.hour()
    minute = components.minute()
    _SENTINEL = 2**63 - 1
    if year > 9999 or month == _SENTINEL or day == _SENTINEL:
        return None
    date_str = f"{year:04d}-{month:02d}-{day:02d}"
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{date_str}T{hour:02d}:{minute:02d}"
    return date_str


def _format_reminder(reminder) -> dict:
    return {
        "id": reminder.calendarItemIdentifier(),
        "title": reminder.title(),
        "due_date": _format_due_date(reminder.dueDateComponents()),
        "priority": _format_priority(reminder.priority()),
        "notes": reminder.notes(),
        "list": reminder.calendar().title() if reminder.calendar() else None,
    }


def _format_completion_date(ns_date) -> str | None:
    if ns_date is None:
        return None
    return datetime.fromtimestamp(
        ns_date.timeIntervalSince1970()
    ).isoformat()


def _format_completed_reminder(reminder) -> dict:
    data = _format_reminder(reminder)
    data["completion_date"] = _format_completion_date(
        reminder.completionDate()
    )
    return data


@mcp.tool()
def ping() -> str:
    """Health check - returns pong."""
    return "pong"


@mcp.tool()
def list_reminder_lists() -> list[dict]:
    """Returns all reminder list names and their reminder counts."""
    service = _get_service()
    lists = service.get_all_lists()
    all_reminders = service.get_all_incomplete_reminders()
    counts: dict[str, int] = {}
    for r in all_reminders:
        cal = r.calendar()
        if cal:
            cal_id = cal.calendarIdentifier()
            counts[cal_id] = counts.get(cal_id, 0) + 1
    return [
        {
            "name": cal.title(),
            "incomplete_count": counts.get(cal.calendarIdentifier(), 0),
        }
        for cal in lists
    ]


@mcp.tool()
def create_list(name: str) -> dict:
    """Creates a new reminder list."""
    service = _get_service()
    cal = service.create_list(name)
    return {"name": cal.title(), "created": True}


@mcp.tool()
def show_incomplete_reminders(list_name: str) -> list[dict]:
    """Returns incomplete reminders for a specific list with title, due date, priority, and notes."""
    service = _get_service()
    reminders = service.get_incomplete_reminders(list_name)
    return [_format_reminder(r) for r in reminders]


@mcp.tool()
def show_all_incomplete_reminders() -> dict:
    """Returns all incomplete reminders grouped by list."""
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
    """Returns reminders completed on the given day (ISO date YYYY-MM-DD, defaults to today)."""
    service = _get_service()
    target_day = date.fromisoformat(day) if day else None
    reminders = service.get_completed_reminders_for_day(target_day)
    return [_format_completed_reminder(r) for r in reminders]


@mcp.tool()
def create_reminder(
    title: str,
    list_name: str | None = None,
    due_date: str | None = None,
    priority: str = "none",
    recurrence: str | None = None,
    notes: str | None = None,
) -> dict:
    """Creates a reminder. Optional: list_name (defaults to default list), due_date (ISO 8601 e.g. '2026-03-15' or '2026-03-15T10:30:00'), priority (none/low/medium/high), recurrence (daily/weekly/monthly/yearly), notes."""
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
def move_reminder(reminder_id: str, target_list_name: str) -> dict:
    """Moves a reminder to a different list. Takes the reminder's id and the target list name."""
    service = _get_service()
    reminder = service.move_reminder(reminder_id, target_list_name)
    return _format_reminder(reminder)


@mcp.tool()
def quick_capture(title: str, notes: str | None = None) -> dict:
    """Quickly captures a reminder in the default list with no date or priority. Optimized for fast idea capture."""
    service = _get_service()
    reminder = service.create_reminder(title=title, notes=notes)
    return _format_reminder(reminder)


def main():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-V"):
        from importlib.metadata import version
        print(f"apple-reminders-mcp {version('apple-reminders-mcp')}")
        sys.exit(0)
    mcp.run()


if __name__ == "__main__":
    main()
