from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from apple_reminders_mcp.formatting import (
    _format_completed_reminder,
    _format_reminder,
    _format_source_type,
)

if TYPE_CHECKING:
    from apple_reminders_mcp.eventkit_service import EventKitService

_PRIORITY_VALUES = {"none": 0, "low": 9, "medium": 5, "high": 1}


def list_reminder_lists(service: EventKitService) -> list[dict]:
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


def create_list(service: EventKitService, name: str) -> dict:
    cal = service.create_list(name)
    return {"name": cal.title(), "created": True}


def show_incomplete_reminders(
    service: EventKitService, list_name: str | None, list_id: str | None
) -> list[dict]:
    reminders = service.get_incomplete_reminders(list_name, list_id)
    return [_format_reminder(r) for r in reminders]


def show_all_incomplete_reminders(service: EventKitService) -> dict:
    reminders = service.get_all_incomplete_reminders()
    grouped: dict[str, list[dict]] = {}
    for r in reminders:
        list_name = r.calendar().title() if r.calendar() else "Unknown"
        if list_name not in grouped:
            grouped[list_name] = []
        grouped[list_name].append(_format_reminder(r))
    return grouped


def show_completed_reminders_today(
    service: EventKitService, day: str | None
) -> list[dict]:
    target_day = date.fromisoformat(day) if day else None
    reminders = service.get_completed_reminders_for_day(target_day)
    return [_format_completed_reminder(r) for r in reminders]


def create_reminder(
    service: EventKitService,
    title: str,
    list_name: str | None,
    list_id: str | None,
    due_date: str | None,
    priority: str,
    recurrence: str | None,
    notes: str | None,
) -> dict:
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


def complete_reminder(service: EventKitService, reminder_id: str) -> dict:
    reminder = service.complete_reminder(reminder_id)
    return {"id": reminder.calendarItemIdentifier(), "completed": True}


def delete_reminder(service: EventKitService, reminder_id: str) -> dict:
    service.delete_reminder(reminder_id)
    return {"id": reminder_id, "deleted": True}


def move_reminder(
    service: EventKitService,
    reminder_id: str,
    target_list_name: str | None,
    target_list_id: str | None,
) -> dict:
    reminder = service.move_reminder(reminder_id, target_list_name, target_list_id)
    return _format_reminder(reminder)


def find_reminders(
    service: EventKitService,
    list_name: str | None,
    list_id: str | None,
    query: str | None,
) -> list[dict]:
    reminders = service.find_reminders(list_name=list_name, list_id=list_id, query=query)
    return [_format_reminder(r) for r in reminders]


def quick_capture(
    service: EventKitService, title: str, notes: str | None
) -> dict:
    reminder = service.create_reminder(title=title, notes=notes)
    return _format_reminder(reminder)
