from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from apple_reminders_mcp.eventkit_service import EventKitService


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class MockWritableCalendar:
    """Simulates an EKCalendar object."""

    def __init__(self, name: str, identifier: str = "cal-1", color=None):
        self._title = name
        self._identifier = identifier
        self._source = MagicMock()
        self._color = color

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

    def color(self):
        return self._color


class MockWritableReminder:
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

    default_cal = MockWritableCalendar("Default", "default-cal")
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
        cals = [MockWritableCalendar("Work"), MockWritableCalendar("Personal")]
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
        work = MockWritableCalendar("Work")
        personal = MockWritableCalendar("Personal")
        svc, _, _ = _make_service(calendars=[work, personal])

        assert svc.get_list_by_name("Personal") is personal

    def test_not_found(self):
        svc, _, _ = _make_service(calendars=[MockWritableCalendar("Work")])

        assert svc.get_list_by_name("Missing") is None


# ---------------------------------------------------------------------------
# Tests: create_list
# ---------------------------------------------------------------------------

class TestCreateList:
    def test_success(self):
        ek = _make_ek_module()
        mock_cal = MockWritableCalendar("", "new-cal")
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
        mock_cal = MockWritableCalendar("", "new-cal")
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
        cal = MockWritableCalendar("Work")
        rem = MockWritableReminder("Buy milk")
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
        cal = MockWritableCalendar("Work")
        svc, _, _ = _make_service(calendars=[cal], reminders=None)

        result = svc.get_incomplete_reminders("Work")

        assert result == []


# ---------------------------------------------------------------------------
# Tests: get_all_incomplete_reminders
# ---------------------------------------------------------------------------

class TestGetAllIncompleteReminders:
    def test_returns_all(self):
        cals = [MockWritableCalendar("Work"), MockWritableCalendar("Home")]
        rems = [MockWritableReminder("Task A"), MockWritableReminder("Task B")]
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
# Tests: get_completed_reminders_for_day
# ---------------------------------------------------------------------------

class TestGetCompletedRemindersForDay:
    def test_returns_reminders_for_specified_day(self):
        cal = MockWritableCalendar("Work")
        rem = MockWritableReminder("Finished task")
        svc, store, _ = _make_service(calendars=[cal], reminders=[rem])

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc.get_completed_reminders_for_day(date(2026, 4, 20))

        assert result == [rem]
        store.predicateForCompletedRemindersWithCompletionDateStarting_ending_calendars_.assert_called_once()
        args = store.predicateForCompletedRemindersWithCompletionDateStarting_ending_calendars_.call_args.args
        assert args[2] == [cal]

    def test_defaults_to_today(self):
        cal = MockWritableCalendar("Work")
        svc, store, _ = _make_service(calendars=[cal], reminders=None)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc.get_completed_reminders_for_day()

        assert result == []
        # Verify NSDate conversion used today's midnight and next midnight
        calls = mock_foundation.NSDate.dateWithTimeIntervalSince1970_.call_args_list
        assert len(calls) == 2
        start_ts, end_ts = calls[0].args[0], calls[1].args[0]
        assert end_ts - start_ts == 24 * 60 * 60

    def test_returns_empty_when_no_reminders(self):
        cal = MockWritableCalendar("Work")
        svc, _, _ = _make_service(calendars=[cal], reminders=None)

        mock_foundation = MagicMock()
        with patch.dict("sys.modules", {"Foundation": mock_foundation}):
            result = svc.get_completed_reminders_for_day(date(2026, 4, 20))

        assert result == []


# ---------------------------------------------------------------------------
# Tests: create_reminder
# ---------------------------------------------------------------------------

class TestCreateReminder:
    def test_basic_with_default_list(self):
        ek = _make_ek_module()
        mock_rem = MockWritableReminder()
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
        mock_rem = MockWritableReminder()
        ek.EKReminder.reminderWithEventStore_.return_value = mock_rem
        target_cal = MockWritableCalendar("Shopping")
        store = _make_store(calendars=[target_cal])
        svc = EventKitService(event_store=store, ek_module=ek)

        result = svc.create_reminder("Apples", list_name="Shopping")

        assert result.calendar() is target_cal

    def test_with_priority_and_notes(self):
        ek = _make_ek_module()
        mock_rem = MockWritableReminder()
        ek.EKReminder.reminderWithEventStore_.return_value = mock_rem
        store = _make_store()
        svc = EventKitService(event_store=store, ek_module=ek)

        svc.create_reminder("Task", priority=5, notes="Important")

        assert mock_rem.priority() == 5
        assert mock_rem.notes() == "Important"

    def test_with_due_date(self):
        ek = _make_ek_module()
        mock_rem = MockWritableReminder()
        ek.EKReminder.reminderWithEventStore_.return_value = mock_rem
        store = _make_store()
        svc = EventKitService(event_store=store, ek_module=ek)

        mock_components = MagicMock()
        with patch.object(svc, "_make_date_components", return_value=mock_components):
            svc.create_reminder("Task", due_date=datetime(2026, 3, 15, 10, 0))

        assert mock_rem.dueDateComponents() is mock_components

    def test_with_recurrence(self):
        ek = _make_ek_module()
        mock_rem = MockWritableReminder()
        ek.EKReminder.reminderWithEventStore_.return_value = mock_rem
        mock_rule = MagicMock()
        ek.EKRecurrenceRule.alloc().initRecurrenceWithFrequency_interval_end_.return_value = mock_rule
        store = _make_store()
        svc = EventKitService(event_store=store, ek_module=ek)

        svc.create_reminder("Daily standup", recurrence="daily")

        assert mock_rule in mock_rem._recurrence_rules

    def test_list_not_found_raises(self):
        ek = _make_ek_module()
        mock_rem = MockWritableReminder()
        ek.EKReminder.reminderWithEventStore_.return_value = mock_rem
        store = _make_store(calendars=[])
        svc = EventKitService(event_store=store, ek_module=ek)

        with pytest.raises(ValueError, match="List 'NonExistent' not found"):
            svc.create_reminder("Task", list_name="NonExistent")

    def test_save_failure_raises(self):
        ek = _make_ek_module()
        mock_rem = MockWritableReminder()
        ek.EKReminder.reminderWithEventStore_.return_value = mock_rem
        store = _make_store()
        store.saveReminder_commit_error_.return_value = (False, "disk full")
        svc = EventKitService(event_store=store, ek_module=ek)

        with pytest.raises(RuntimeError, match="Failed to create reminder"):
            svc.create_reminder("Task")

    def test_no_default_calendar_raises(self):
        ek = _make_ek_module()
        mock_rem = MockWritableReminder()
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
        mock_rem = MockWritableReminder("Task", "rem-42")
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
        mock_rem = MockWritableReminder("Task", "rem-42")
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
        mock_rem = MockWritableReminder("Task", "rem-42")
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
        mock_rem = MockWritableReminder("Task", "rem-42")
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
        mock_rem = MockWritableReminder("Task", "rem-42")
        target_cal = MockWritableCalendar("Personal", "cal-2")
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
        store = _make_store(calendars=[MockWritableCalendar("Personal")])
        store.calendarItemWithIdentifier_.return_value = None
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="Reminder 'rem-99' not found"):
            svc.move_reminder("rem-99", "Personal")

    def test_target_list_not_found_raises(self):
        mock_rem = MockWritableReminder("Task", "rem-42")
        store = _make_store(calendars=[])
        store.calendarItemWithIdentifier_.return_value = mock_rem
        svc, _, _ = _make_service(store=store)

        with pytest.raises(ValueError, match="List 'Missing' not found"):
            svc.move_reminder("rem-42", "Missing")

    def test_save_failure_raises(self):
        mock_rem = MockWritableReminder("Task", "rem-42")
        target_cal = MockWritableCalendar("Personal")
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
        mock_rem = MockWritableReminder("Task", "rem-42")
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


# ---------------------------------------------------------------------------
# Tests: resolving a list by id
#
# Reminders permits two lists with the same title. Every name-keyed lookup then
# silently picks one, which is why identifiers exist on the API at all.
# ---------------------------------------------------------------------------


class TestResolveList:
    def _service(self, calendars):
        service = EventKitService.__new__(EventKitService)
        service.get_all_lists = lambda: calendars
        return service

    def test_an_id_resolves_to_its_list(self):
        a, b = MockWritableCalendar("Projects", "cal-a"), MockWritableCalendar("Projects", "cal-b")
        service = self._service([a, b])
        assert service.get_list_by_id("cal-b") is b

    def test_a_duplicate_title_is_exactly_why_the_id_matters(self):
        """Both lists answer to the same name; only the id distinguishes them."""
        a, b = MockWritableCalendar("Projects", "cal-a"), MockWritableCalendar("Projects", "cal-b")
        service = self._service([a, b])
        assert service.get_list_by_name("Projects") is a
        assert service.get_list_by_id("cal-b") is b

    def test_an_id_wins_when_both_are_given(self):
        a, b = MockWritableCalendar("Work", "cal-a"), MockWritableCalendar("Personal", "cal-b")
        service = self._service([a, b])
        assert service.resolve_list("Work", "cal-b") is b

    def test_a_name_still_resolves_on_its_own(self):
        a = MockWritableCalendar("Work", "cal-a")
        assert self._service([a]).resolve_list("Work") is a

    def test_an_unknown_id_names_the_id(self):
        service = self._service([MockWritableCalendar("Work", "cal-a")])
        with pytest.raises(ValueError, match="cal-zz"):
            service.resolve_list(None, "cal-zz")

    def test_an_unknown_name_names_the_name(self):
        service = self._service([MockWritableCalendar("Work", "cal-a")])
        with pytest.raises(ValueError, match="Nope"):
            service.resolve_list("Nope")

    def test_neither_is_refused(self):
        service = self._service([MockWritableCalendar("Work", "cal-a")])
        with pytest.raises(ValueError, match="list_name or list_id"):
            service.resolve_list()


def _make_ns_color(components=(1.0, 0.0, 0.5), converts=True):
    """Create a mock NSColor whose sRGB conversion yields the given components."""
    color = MagicMock()
    if not converts:
        color.colorUsingColorSpace_.return_value = None
        return color
    srgb = MagicMock()
    srgb.redComponent.return_value = components[0]
    srgb.greenComponent.return_value = components[1]
    srgb.blueComponent.return_value = components[2]
    color.colorUsingColorSpace_.return_value = srgb
    return color


class TestCalendarColorHex:
    def _hex(self, calendar):
        with patch.dict("sys.modules", {"AppKit": MagicMock()}):
            return EventKitService.calendar_color_hex(calendar)

    def test_components_become_a_hex_string(self):
        calendar = MockWritableCalendar("Work", color=_make_ns_color((1.0, 0.0, 0.5)))
        assert self._hex(calendar) == "#ff0080"

    def test_black_keeps_both_digits(self):
        calendar = MockWritableCalendar("Work", color=_make_ns_color((0.0, 0.0, 0.0)))
        assert self._hex(calendar) == "#000000"

    def test_conversion_uses_the_srgb_color_space(self):
        color = _make_ns_color()
        appkit = MagicMock()
        calendar = MockWritableCalendar("Work", color=color)
        with patch.dict("sys.modules", {"AppKit": appkit}):
            EventKitService.calendar_color_hex(calendar)

        color.colorUsingColorSpace_.assert_called_once_with(
            appkit.NSColorSpace.sRGBColorSpace()
        )

    def test_a_list_without_a_color(self):
        assert self._hex(MockWritableCalendar("Work")) is None

    def test_a_color_that_cannot_be_converted(self):
        calendar = MockWritableCalendar("Work", color=_make_ns_color(converts=False))
        assert self._hex(calendar) is None

    @pytest.mark.parametrize(
        "components,expected",
        [
            ((-0.05, 1.02, 0.5), "#00ff80"),
            ((2.0, -1.0, 0.0), "#ff0000"),
        ],
    )
    def test_wide_gamut_components_are_clamped(self, components, expected):
        """colorUsingColorSpace_ can hand back components outside 0..1; unclamped they format as '#-d10480'."""
        calendar = MockWritableCalendar("Work", color=_make_ns_color(components))
        assert self._hex(calendar) == expected

    def test_a_missing_appkit_does_not_take_down_the_caller(self):
        calendar = MockWritableCalendar("Work", color=_make_ns_color())
        with patch.dict("sys.modules", {"AppKit": None}):
            assert EventKitService.calendar_color_hex(calendar) is None


class TestFetchTimeout:
    def _service_whose_fetch_never_calls_back(self):
        store = _make_store()
        store.fetchRemindersMatchingPredicate_completion_.side_effect = (
            lambda predicate, callback: None
        )
        service, _, _ = _make_service(store=store)
        return service

    def _never_signalled(self):
        event = MagicMock()
        event.wait.return_value = False
        return patch(
            "apple_reminders_mcp.eventkit_service.threading.Event",
            return_value=event,
        )

    def test_incomplete_reminders_time_out(self):
        service = self._service_whose_fetch_never_calls_back()
        with self._never_signalled():
            with pytest.raises(TimeoutError, match="Timed out fetching reminders"):
                service.get_all_incomplete_reminders()

    def test_completed_reminders_time_out(self):
        service = self._service_whose_fetch_never_calls_back()
        with patch.dict("sys.modules", {"Foundation": MagicMock()}):
            with self._never_signalled():
                with pytest.raises(TimeoutError, match="Timed out fetching reminders"):
                    service.get_completed_reminders_for_day(date(2026, 4, 20))
