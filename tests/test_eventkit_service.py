from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from apple_reminders_mcp.eventkit_service import EventKitService


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class MockCalendar:
    """Simulates an EKCalendar object."""

    def __init__(self, name: str, identifier: str = "cal-1"):
        self._title = name
        self._identifier = identifier
        self._source = MagicMock()

    def title(self):
        return self._title

    def setTitle_(self, title):
        self._title = title

    def calendarIdentifier(self):
        return self._identifier

    def source(self):
        return self._source

    def setSource_(self, source):
        self._source = source


class MockReminder:
    """Simulates an EKReminder object."""

    def __init__(self, title: str = "", identifier: str = "rem-1"):
        self._title = title
        self._identifier = identifier
        self._calendar = None
        self._priority = 0
        self._notes = None
        self._completed = False
        self._due_date_components = None
        self._recurrence_rules: list = []

    def title(self):
        return self._title

    def setTitle_(self, title):
        self._title = title

    def calendarItemIdentifier(self):
        return self._identifier

    def calendar(self):
        return self._calendar

    def setCalendar_(self, calendar):
        self._calendar = calendar

    def priority(self):
        return self._priority

    def setPriority_(self, priority):
        self._priority = priority

    def notes(self):
        return self._notes

    def setNotes_(self, notes):
        self._notes = notes

    def completed(self):
        return self._completed

    def setCompleted_(self, completed):
        self._completed = completed

    def dueDateComponents(self):
        return self._due_date_components

    def setDueDateComponents_(self, components):
        self._due_date_components = components

    def addRecurrenceRule_(self, rule):
        self._recurrence_rules.append(rule)


def _make_ek_module():
    """Create a mock EventKit module with required constants and classes."""
    ek = MagicMock()
    ek.EKEntityTypeReminder = 1
    ek.EKRecurrenceFrequencyDaily = 0
    ek.EKRecurrenceFrequencyWeekly = 1
    ek.EKRecurrenceFrequencyMonthly = 2
    ek.EKRecurrenceFrequencyYearly = 3
    return ek


def _make_store(calendars=None, reminders=None):
    """Create a mock EKEventStore."""
    store = MagicMock()
    store.calendarsForEntityType_.return_value = calendars or []

    default_cal = MockCalendar("Default", "default-cal")
    store.defaultCalendarForNewReminders.return_value = default_cal

    def fetch_reminders(predicate, callback):
        callback(reminders)

    store.fetchRemindersMatchingPredicate_completion_.side_effect = (
        fetch_reminders
    )
    store.saveCalendar_commit_error_.return_value = (True, None)
    store.saveReminder_commit_error_.return_value = (True, None)
    store.removeReminder_commit_error_.return_value = (True, None)
    return store


def _make_service(calendars=None, reminders=None, store=None, ek=None):
    """Create an EventKitService with mocked dependencies."""
    if ek is None:
        ek = _make_ek_module()
    if store is None:
        store = _make_store(calendars=calendars, reminders=reminders)
    return EventKitService(event_store=store, ek_module=ek), store, ek


# ---------------------------------------------------------------------------
# Tests: get_all_lists
# ---------------------------------------------------------------------------

class TestGetAllLists:
    def test_returns_calendars(self):
        cals = [MockCalendar("Work"), MockCalendar("Personal")]
        svc, store, _ = _make_service(calendars=cals)

        result = svc.get_all_lists()

        assert result == cals
        store.calendarsForEntityType_.assert_called_once_with(1)

    def test_returns_empty_when_none(self):
        svc, _, _ = _make_service(calendars=None)
        store = svc._store
        store.calendarsForEntityType_.return_value = None

        assert svc.get_all_lists() == []

    def test_returns_empty_list(self):
        svc, _, _ = _make_service(calendars=[])
        assert svc.get_all_lists() == []


# ---------------------------------------------------------------------------
# Tests: get_list_by_name
# ---------------------------------------------------------------------------

class TestGetListByName:
    def test_found(self):
        work = MockCalendar("Work")
        personal = MockCalendar("Personal")
        svc, _, _ = _make_service(calendars=[work, personal])

        assert svc.get_list_by_name("Personal") is personal

    def test_not_found(self):
        svc, _, _ = _make_service(calendars=[MockCalendar("Work")])

        assert svc.get_list_by_name("Missing") is None


# ---------------------------------------------------------------------------
# Tests: create_list
# ---------------------------------------------------------------------------

class TestCreateList:
    def test_success(self):
        ek = _make_ek_module()
        mock_cal = MockCalendar("", "new-cal")
        ek.EKCalendar.calendarForEntityType_eventStore_.return_value = mock_cal
        store = _make_store()
        svc = EventKitService(event_store=store, ek_module=ek)

        result = svc.create_list("Shopping")

        assert result is mock_cal
        assert mock_cal.title() == "Shopping"
        store.saveCalendar_commit_error_.assert_called_once_with(
            mock_cal, True, None
        )

    def test_failure_raises(self):
        ek = _make_ek_module()
        mock_cal = MockCalendar("", "new-cal")
        ek.EKCalendar.calendarForEntityType_eventStore_.return_value = mock_cal
        store = _make_store()
        store.saveCalendar_commit_error_.return_value = (False, "save error")
        svc = EventKitService(event_store=store, ek_module=ek)

        with pytest.raises(RuntimeError, match="Failed to create list"):
            svc.create_list("Shopping")


# ---------------------------------------------------------------------------
# Tests: get_incomplete_reminders
# ---------------------------------------------------------------------------

class TestGetIncompleteReminders:
    def test_returns_reminders_for_list(self):
        cal = MockCalendar("Work")
        rem = MockReminder("Buy milk")
        svc, store, _ = _make_service(calendars=[cal], reminders=[rem])

        result = svc.get_incomplete_reminders("Work")

        assert result == [rem]
        store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_.assert_called_once_with(
            None, None, [cal]
        )

    def test_list_not_found_raises(self):
        svc, _, _ = _make_service(calendars=[])

        with pytest.raises(ValueError, match="List 'Missing' not found"):
            svc.get_incomplete_reminders("Missing")

    def test_returns_empty_when_no_reminders(self):
        cal = MockCalendar("Work")
        svc, _, _ = _make_service(calendars=[cal], reminders=None)

        result = svc.get_incomplete_reminders("Work")

        assert result == []


# ---------------------------------------------------------------------------
# Tests: get_all_incomplete_reminders
# ---------------------------------------------------------------------------

class TestGetAllIncompleteReminders:
    def test_returns_all(self):
        cals = [MockCalendar("Work"), MockCalendar("Home")]
        rems = [MockReminder("Task A"), MockReminder("Task B")]
        svc, store, _ = _make_service(calendars=cals, reminders=rems)

        result = svc.get_all_incomplete_reminders()

        assert result == rems
        store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_.assert_called_once_with(
            None, None, cals
        )

    def test_returns_empty(self):
        svc, _, _ = _make_service(calendars=[], reminders=None)

        assert svc.get_all_incomplete_reminders() == []


# ---------------------------------------------------------------------------
# Tests: create_reminder
# ---------------------------------------------------------------------------

class TestCreateReminder:
    def test_basic_with_default_list(self):
        ek = _make_ek_module()
        mock_rem = MockReminder()
        ek.EKReminder.reminderWithEventStore_.return_value = mock_rem
        store = _make_store()
        svc = EventKitService(event_store=store, ek_module=ek)

        result = svc.create_reminder("Buy groceries")

        assert result is mock_rem
        assert mock_rem.title() == "Buy groceries"
        assert mock_rem.priority() == 0
        assert mock_rem.calendar() is store.defaultCalendarForNewReminders()
        store.saveReminder_commit_error_.assert_called_once_with(
            mock_rem, True, None
        )

    def test_with_specific_list(self):
        ek = _make_ek_module()
        mock_rem = MockReminder()
        ek.EKReminder.reminderWithEventStore_.return_value = mock_rem
        target_cal = MockCalendar("Shopping")
        store = _make_store(calendars=[target_cal])
        svc = EventKitService(event_store=store, ek_module=ek)

        result = svc.create_reminder("Apples", list_name="Shopping")

        assert result.calendar() is target_cal

    def test_with_priority_and_notes(self):
        ek = _make_ek_module()
        mock_rem = MockReminder()
        ek.EKReminder.reminderWithEventStore_.return_value = mock_rem
        store = _make_store()
        svc = EventKitService(event_store=store, ek_module=ek)

        svc.create_reminder("Task", priority=5, notes="Important")

        assert mock_rem.priority() == 5
        assert mock_rem.notes() == "Important"

    def test_with_due_date(self):
        ek = _make_ek_module()
        mock_rem = MockReminder()
        ek.EKReminder.reminderWithEventStore_.return_value = mock_rem
        store = _make_store()
        svc = EventKitService(event_store=store, ek_module=ek)

        mock_components = MagicMock()
        with patch.object(svc, "_make_date_components", return_value=mock_components):
            svc.create_reminder("Task", due_date=datetime(2026, 3, 15, 10, 0))

        assert mock_rem.dueDateComponents() is mock_components

    def test_with_recurrence(self):
        ek = _make_ek_module()
        mock_rem = MockReminder()
        ek.EKReminder.reminderWithEventStore_.return_value = mock_rem
        mock_rule = MagicMock()
        ek.EKRecurrenceRule.alloc().initRecurrenceWithFrequency_interval_end_.return_value = mock_rule
        store = _make_store()
        svc = EventKitService(event_store=store, ek_module=ek)

        svc.create_reminder("Daily standup", recurrence="daily")

        assert mock_rule in mock_rem._recurrence_rules

    def test_list_not_found_raises(self):
        ek = _make_ek_module()
        mock_rem = MockReminder()
        ek.EKReminder.reminderWithEventStore_.return_value = mock_rem
        store = _make_store(calendars=[])
        svc = EventKitService(event_store=store, ek_module=ek)

        with pytest.raises(ValueError, match="List 'NonExistent' not found"):
            svc.create_reminder("Task", list_name="NonExistent")

    def test_save_failure_raises(self):
        ek = _make_ek_module()
        mock_rem = MockReminder()
        ek.EKReminder.reminderWithEventStore_.return_value = mock_rem
        store = _make_store()
        store.saveReminder_commit_error_.return_value = (False, "disk full")
        svc = EventKitService(event_store=store, ek_module=ek)

        with pytest.raises(RuntimeError, match="Failed to create reminder"):
            svc.create_reminder("Task")

    def test_no_default_calendar_raises(self):
        ek = _make_ek_module()
        mock_rem = MockReminder()
        ek.EKReminder.reminderWithEventStore_.return_value = mock_rem
        store = _make_store()
        store.defaultCalendarForNewReminders.return_value = None
        svc = EventKitService(event_store=store, ek_module=ek)

        with pytest.raises(RuntimeError, match="No default calendar"):
            svc.create_reminder("Task")


# ---------------------------------------------------------------------------
# Tests: complete_reminder
# ---------------------------------------------------------------------------

class TestCompleteReminder:
    def test_success(self):
        mock_rem = MockReminder("Task", "rem-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_rem
        svc, _, _ = _make_service(store=store)

        result = svc.complete_reminder("rem-42")

        assert result is mock_rem
        assert mock_rem.completed() is True
        store.saveReminder_commit_error_.assert_called_once_with(
            mock_rem, True, None
        )

    def test_not_found_raises(self):
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = None
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="Reminder 'rem-99' not found"):
            svc.complete_reminder("rem-99")

    def test_save_failure_raises(self):
        mock_rem = MockReminder("Task", "rem-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_rem
        store.saveReminder_commit_error_.return_value = (False, "err")
        svc, _, _ = _make_service(store=store)

        with pytest.raises(RuntimeError, match="Failed to complete reminder"):
            svc.complete_reminder("rem-42")


# ---------------------------------------------------------------------------
# Tests: delete_reminder
# ---------------------------------------------------------------------------

class TestDeleteReminder:
    def test_success(self):
        mock_rem = MockReminder("Task", "rem-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_rem
        svc, _, _ = _make_service(store=store)

        svc.delete_reminder("rem-42")

        store.removeReminder_commit_error_.assert_called_once_with(
            mock_rem, True, None
        )

    def test_not_found_raises(self):
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = None
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="Reminder 'rem-99' not found"):
            svc.delete_reminder("rem-99")

    def test_remove_failure_raises(self):
        mock_rem = MockReminder("Task", "rem-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_rem
        store.removeReminder_commit_error_.return_value = (False, "err")
        svc, _, _ = _make_service(store=store)

        with pytest.raises(RuntimeError, match="Failed to delete reminder"):
            svc.delete_reminder("rem-42")


# ---------------------------------------------------------------------------
# Tests: move_reminder
# ---------------------------------------------------------------------------

class TestMoveReminder:
    def test_success(self):
        mock_rem = MockReminder("Task", "rem-42")
        target_cal = MockCalendar("Personal", "cal-2")
        store = _make_store(calendars=[target_cal])
        store.calendarItemWithIdentifier_.return_value = mock_rem
        svc, _, _ = _make_service(store=store)

        result = svc.move_reminder("rem-42", "Personal")

        assert result is mock_rem
        assert mock_rem.calendar() is target_cal
        store.saveReminder_commit_error_.assert_called_once_with(
            mock_rem, True, None
        )

    def test_reminder_not_found_raises(self):
        store = _make_store(calendars=[MockCalendar("Personal")])
        store.calendarItemWithIdentifier_.return_value = None
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="Reminder 'rem-99' not found"):
            svc.move_reminder("rem-99", "Personal")

    def test_target_list_not_found_raises(self):
        mock_rem = MockReminder("Task", "rem-42")
        store = _make_store(calendars=[])
        store.calendarItemWithIdentifier_.return_value = mock_rem
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="List 'Missing' not found"):
            svc.move_reminder("rem-42", "Missing")

    def test_save_failure_raises(self):
        mock_rem = MockReminder("Task", "rem-42")
        target_cal = MockCalendar("Personal")
        store = _make_store(calendars=[target_cal])
        store.calendarItemWithIdentifier_.return_value = mock_rem
        store.saveReminder_commit_error_.return_value = (False, "err")
        svc, _, _ = _make_service(store=store)

        with pytest.raises(RuntimeError, match="Failed to move reminder"):
            svc.move_reminder("rem-42", "Personal")


# ---------------------------------------------------------------------------
# Tests: _find_reminder_by_id
# ---------------------------------------------------------------------------

class TestFindReminderById:
    def test_found(self):
        mock_rem = MockReminder("Task", "rem-42")
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = mock_rem
        svc, _, _ = _make_service(store=store)

        assert svc._find_reminder_by_id("rem-42") is mock_rem
        store.calendarItemWithIdentifier_.assert_called_once_with("rem-42")

    def test_not_found(self):
        store = _make_store()
        store.calendarItemWithIdentifier_.return_value = None
        svc, _, _ = _make_service(store=store)

        assert svc._find_reminder_by_id("missing") is None


# ---------------------------------------------------------------------------
# Tests: _create_recurrence_rule
# ---------------------------------------------------------------------------

class TestCreateRecurrenceRule:
    @pytest.mark.parametrize("recurrence,freq", [
        ("daily", 0),
        ("weekly", 1),
        ("monthly", 2),
        ("yearly", 3),
        ("Daily", 0),
        ("WEEKLY", 1),
    ])
    def test_valid_recurrence(self, recurrence, freq):
        ek = _make_ek_module()
        mock_rule = MagicMock()
        ek.EKRecurrenceRule.alloc().initRecurrenceWithFrequency_interval_end_.return_value = mock_rule
        svc = EventKitService(event_store=_make_store(), ek_module=ek)

        result = svc._create_recurrence_rule(recurrence)

        assert result is mock_rule
        ek.EKRecurrenceRule.alloc().initRecurrenceWithFrequency_interval_end_.assert_called_with(
            freq, 1, None
        )

    def test_invalid_recurrence_raises(self):
        svc, _, _ = _make_service()
        with pytest.raises(ValueError, match="Invalid recurrence"):
            svc._create_recurrence_rule("biweekly")


# ---------------------------------------------------------------------------
# Tests: _make_date_components
# ---------------------------------------------------------------------------

class TestMakeDateComponents:
    def test_creates_components(self):
        svc, _, _ = _make_service()

        mock_components = MagicMock()
        mock_foundation = MagicMock()
        mock_foundation.NSDateComponents.alloc().init.return_value = (
            mock_components
        )

        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc._make_date_components(datetime(2026, 3, 15, 10, 30))

        assert result is mock_components
        mock_components.setYear_.assert_called_once_with(2026)
        mock_components.setMonth_.assert_called_once_with(3)
        mock_components.setDay_.assert_called_once_with(15)
        mock_components.setHour_.assert_called_once_with(10)
        mock_components.setMinute_.assert_called_once_with(30)

    def test_timezone_aware_utc(self):
        svc, _, _ = _make_service()

        mock_components = MagicMock()
        mock_foundation = MagicMock()
        mock_foundation.NSDateComponents.alloc().init.return_value = (
            mock_components
        )

        dt = datetime(2026, 3, 15, 10, 30, tzinfo=timezone.utc)
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc._make_date_components(dt)

        assert result is mock_components
        mock_components.setYear_.assert_called_once_with(2026)
        mock_components.setHour_.assert_called_once_with(10)
        mock_foundation.NSTimeZone.timeZoneForSecondsFromGMT_.assert_called_once_with(0)
        mock_components.setTimeZone_.assert_called_once()

    def test_timezone_aware_positive_offset(self):
        svc, _, _ = _make_service()

        mock_components = MagicMock()
        mock_foundation = MagicMock()
        mock_foundation.NSDateComponents.alloc().init.return_value = (
            mock_components
        )

        tz = timezone(timedelta(hours=5, minutes=30))
        dt = datetime(2026, 3, 15, 10, 30, tzinfo=tz)
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            svc._make_date_components(dt)

        mock_foundation.NSTimeZone.timeZoneForSecondsFromGMT_.assert_called_once_with(19800)
        mock_components.setTimeZone_.assert_called_once()

    def test_naive_datetime_no_timezone_set(self):
        svc, _, _ = _make_service()

        mock_components = MagicMock()
        mock_foundation = MagicMock()
        mock_foundation.NSDateComponents.alloc().init.return_value = (
            mock_components
        )

        dt = datetime(2026, 3, 15, 10, 30)
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            svc._make_date_components(dt)

        mock_components.setTimeZone_.assert_not_called()

    def test_date_only_omits_time(self):
        svc, _, _ = _make_service()

        mock_components = MagicMock()
        mock_foundation = MagicMock()
        mock_foundation.NSDateComponents.alloc().init.return_value = (
            mock_components
        )

        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc._make_date_components(
                datetime(2026, 3, 15), include_time=False
            )

        assert result is mock_components
        mock_components.setYear_.assert_called_once_with(2026)
        mock_components.setMonth_.assert_called_once_with(3)
        mock_components.setDay_.assert_called_once_with(15)
        mock_components.setHour_.assert_not_called()
        mock_components.setMinute_.assert_not_called()
