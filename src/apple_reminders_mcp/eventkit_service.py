from __future__ import annotations

import threading
from datetime import datetime
from typing import Any


class EventKitService:
    """Service layer wrapping Apple EventKit for reminder operations."""

    _RECURRENCE_MAP = {
        "daily": 0,
        "weekly": 1,
        "monthly": 2,
        "yearly": 3,
    }

    def __init__(self, event_store: Any = None, ek_module: Any = None) -> None:
        if ek_module is not None:
            self._ek = ek_module
        else:
            import EventKit
            self._ek = EventKit

        if event_store is not None:
            self._store = event_store
        else:
            self._store = self._ek.EKEventStore.alloc().init()
            self._request_access()

    def _request_access(self) -> None:
        """Request and verify reminder access permission."""
        event = threading.Event()
        result: dict[str, Any] = {}

        def callback(granted: bool, error: Any) -> None:
            result["granted"] = granted
            result["error"] = error
            event.set()

        self._store.requestAccessToEntityType_completion_(
            self._ek.EKEntityTypeReminder,
            callback,
        )
        if not event.wait(timeout=30):
            raise TimeoutError(
                "Timed out waiting for reminder access permission"
            )

        if not result.get("granted"):
            raise PermissionError(
                f"Reminder access not granted: {result.get('error')}"
            )

    def get_all_lists(self) -> list[Any]:
        """Return all reminder lists (calendars of type reminder)."""
        calendars = self._store.calendarsForEntityType_(
            self._ek.EKEntityTypeReminder
        )
        return list(calendars) if calendars else []

    def get_list_by_name(self, name: str) -> Any | None:
        """Find a specific reminder list by name."""
        for cal in self.get_all_lists():
            if cal.title() == name:
                return cal
        return None

    def create_list(self, name: str) -> Any:
        """Create a new reminder list."""
        default_cal = self._store.defaultCalendarForNewReminders()
        if default_cal is None:
            raise RuntimeError(
                "No default calendar for reminders. "
                "Ensure a Reminders account is configured in System Settings."
            )
        source = default_cal.source()
        calendar = self._ek.EKCalendar.calendarForEntityType_eventStore_(
            self._ek.EKEntityTypeReminder,
            self._store,
        )
        calendar.setTitle_(name)
        calendar.setSource_(source)
        success, error = self._store.saveCalendar_commit_error_(
            calendar, True, None
        )
        if not success:
            raise RuntimeError(f"Failed to create list: {error}")
        return calendar

    def get_incomplete_reminders(self, list_name: str) -> list[Any]:
        """Fetch incomplete reminders for a specific list."""
        calendar = self.get_list_by_name(list_name)
        if calendar is None:
            raise ValueError(f"List '{list_name}' not found")
        return self._fetch_incomplete_reminders([calendar])

    def get_all_incomplete_reminders(self) -> list[Any]:
        """Fetch incomplete reminders across all lists."""
        calendars = self.get_all_lists()
        return self._fetch_incomplete_reminders(calendars)

    def _fetch_incomplete_reminders(self, calendars: list[Any]) -> list[Any]:
        predicate = (
            self._store
            .predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
                None, None, calendars
            )
        )
        event = threading.Event()
        result: list[Any | None] = [None]

        def callback(reminders: Any) -> None:
            result[0] = reminders
            event.set()

        self._store.fetchRemindersMatchingPredicate_completion_(
            predicate, callback
        )
        if not event.wait(timeout=30):
            raise TimeoutError("Timed out fetching reminders")
        return list(result[0]) if result[0] else []

    def create_reminder(
        self,
        title: str,
        list_name: str | None = None,
        due_date: datetime | None = None,
        priority: int = 0,
        recurrence: str | None = None,
        notes: str | None = None,
        include_time: bool = True,
    ) -> Any:
        """Create a reminder with optional due date, priority, recurrence, and target list."""
        reminder = self._ek.EKReminder.reminderWithEventStore_(self._store)
        reminder.setTitle_(title)

        if list_name is not None:
            calendar = self.get_list_by_name(list_name)
            if calendar is None:
                raise ValueError(f"List '{list_name}' not found")
            reminder.setCalendar_(calendar)
        else:
            default_cal = self._store.defaultCalendarForNewReminders()
            if default_cal is None:
                raise RuntimeError(
                    "No default calendar for reminders. "
                    "Ensure a Reminders account is configured in System Settings."
                )
            reminder.setCalendar_(default_cal)

        reminder.setPriority_(priority)

        if notes is not None:
            reminder.setNotes_(notes)

        if due_date:
            components = self._make_date_components(
                due_date, include_time=include_time
            )
            reminder.setDueDateComponents_(components)

        if recurrence:
            rule = self._create_recurrence_rule(recurrence)
            reminder.addRecurrenceRule_(rule)

        success, error = self._store.saveReminder_commit_error_(
            reminder, True, None
        )
        if not success:
            raise RuntimeError(f"Failed to create reminder: {error}")
        return reminder

    def complete_reminder(self, reminder_id: str) -> Any:
        """Mark a reminder as completed."""
        reminder = self._find_reminder_by_id(reminder_id)
        if reminder is None:
            raise ValueError(f"Reminder '{reminder_id}' not found")
        reminder.setCompleted_(True)
        success, error = self._store.saveReminder_commit_error_(
            reminder, True, None
        )
        if not success:
            raise RuntimeError(f"Failed to complete reminder: {error}")
        return reminder

    def delete_reminder(self, reminder_id: str) -> None:
        """Delete a reminder."""
        reminder = self._find_reminder_by_id(reminder_id)
        if reminder is None:
            raise ValueError(f"Reminder '{reminder_id}' not found")
        success, error = self._store.removeReminder_commit_error_(
            reminder, True, None
        )
        if not success:
            raise RuntimeError(f"Failed to delete reminder: {error}")

    def move_reminder(self, reminder_id: str, target_list_name: str) -> Any:
        """Move a reminder to a different list."""
        reminder = self._find_reminder_by_id(reminder_id)
        if reminder is None:
            raise ValueError(f"Reminder '{reminder_id}' not found")
        calendar = self.get_list_by_name(target_list_name)
        if calendar is None:
            raise ValueError(f"List '{target_list_name}' not found")
        reminder.setCalendar_(calendar)
        success, error = self._store.saveReminder_commit_error_(
            reminder, True, None
        )
        if not success:
            raise RuntimeError(f"Failed to move reminder: {error}")
        return reminder

    def _find_reminder_by_id(self, reminder_id: str) -> Any | None:
        """Look up a reminder by its calendarItemIdentifier."""
        return self._store.calendarItemWithIdentifier_(reminder_id)

    def _make_date_components(
        self, dt: datetime, *, include_time: bool = True
    ) -> Any:
        """Convert a Python datetime to NSDateComponents."""
        import Foundation

        components = Foundation.NSDateComponents.alloc().init()
        components.setYear_(dt.year)
        components.setMonth_(dt.month)
        components.setDay_(dt.day)
        if include_time:
            components.setHour_(dt.hour)
            components.setMinute_(dt.minute)
        if dt.tzinfo is not None:
            offset_seconds = int(dt.utcoffset().total_seconds())
            tz = Foundation.NSTimeZone.timeZoneForSecondsFromGMT_(
                offset_seconds
            )
            components.setTimeZone_(tz)
        return components

    def _create_recurrence_rule(self, recurrence: str) -> Any:
        """Create an EKRecurrenceRule from a recurrence string."""
        freq = self._RECURRENCE_MAP.get(recurrence.lower())
        if freq is None:
            raise ValueError(
                f"Invalid recurrence '{recurrence}'. "
                f"Must be one of: daily, weekly, monthly, yearly"
            )
        rule = (
            self._ek.EKRecurrenceRule.alloc()
            .initRecurrenceWithFrequency_interval_end_(freq, 1, None)
        )
        return rule
