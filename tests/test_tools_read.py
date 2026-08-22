from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from apple_reminders_mcp.server import (
    _format_completed_reminder,
    _format_completion_date,
    _format_due_date,
    _format_priority,
    _format_reminder,
    create_list,
    list_reminder_lists,
    show_all_incomplete_reminders,
    show_completed_reminders_today,
    show_incomplete_reminders,
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockCalendar:
    _counter = 0

    def __init__(self, name: str, identifier: str | None = None):
        self._title = name
        if identifier is not None:
            self._identifier = identifier
        else:
            MockCalendar._counter += 1
            self._identifier = f"cal-{MockCalendar._counter}"

    def title(self):
        return self._title

    def calendarIdentifier(self):
        return self._identifier


class MockReminder:
    def __init__(
        self,
        title: str = "",
        identifier: str = "rem-1",
        calendar: MockCalendar | None = None,
        priority: int = 0,
        notes: str | None = None,
        due_components=None,
        completion_date=None,
    ):
        self._title = title
        self._identifier = identifier
        self._calendar = calendar
        self._priority = priority
        self._notes = notes
        self._due = due_components
        self._completion_date = completion_date

    def title(self):
        return self._title

    def calendarItemIdentifier(self):
        return self._identifier

    def calendar(self):
        return self._calendar

    def priority(self):
        return self._priority

    def notes(self):
        return self._notes

    def dueDateComponents(self):
        return self._due

    def completionDate(self):
        return self._completion_date


class MockNSDate:
    def __init__(self, timestamp: float):
        self._timestamp = timestamp

    def timeIntervalSince1970(self):
        return self._timestamp


class MockDateComponents:
    def __init__(self, year, month, day, hour=None, minute=None):
        self._year = year
        self._month = month
        self._day = day
        self._hour = hour if hour is not None else 2**63 - 1
        self._minute = minute if minute is not None else 2**63 - 1

    def year(self):
        return self._year

    def month(self):
        return self._month

    def day(self):
        return self._day

    def hour(self):
        return self._hour

    def minute(self):
        return self._minute


@pytest.fixture()
def mock_service():
    service = MagicMock()
    with patch(
        "apple_reminders_mcp.server._get_service", return_value=service
    ):
        yield service


# ---------------------------------------------------------------------------
# Tests: _format_priority
# ---------------------------------------------------------------------------


class TestFormatPriority:
    @pytest.mark.parametrize(
        "priority,expected",
        [
            (0, "none"),
            (1, "high"),
            (5, "medium"),
            (9, "low"),
            (3, "custom(3)"),
        ],
    )
    def test_formats(self, priority, expected):
        assert _format_priority(priority) == expected


# ---------------------------------------------------------------------------
# Tests: _format_due_date
# ---------------------------------------------------------------------------


class TestFormatDueDate:
    def test_none_components(self):
        assert _format_due_date(None) is None

    def test_date_with_time(self):
        dc = MockDateComponents(2026, 3, 15, 10, 30)
        assert _format_due_date(dc) == "2026-03-15T10:30"

    def test_date_only_when_time_undefined(self):
        dc = MockDateComponents(2026, 3, 15)
        assert _format_due_date(dc) == "2026-03-15"

    def test_undefined_year_returns_none(self):
        dc = MockDateComponents(2**63 - 1, 3, 15)
        assert _format_due_date(dc) is None

    def test_midnight_time(self):
        dc = MockDateComponents(2026, 1, 1, 0, 0)
        assert _format_due_date(dc) == "2026-01-01T00:00"


# ---------------------------------------------------------------------------
# Tests: _format_reminder
# ---------------------------------------------------------------------------


class TestFormatReminder:
    def test_full_reminder(self):
        cal = MockCalendar("Work", identifier="cal-work")
        due = MockDateComponents(2026, 3, 15, 10, 30)
        rem = MockReminder(
            title="Buy milk",
            identifier="rem-1",
            calendar=cal,
            priority=1,
            notes="Whole milk",
            due_components=due,
        )

        result = _format_reminder(rem)

        assert result == {
            "id": "rem-1",
            "title": "Buy milk",
            "due_date": "2026-03-15T10:30",
            "priority": "high",
            "notes": "Whole milk",
            "list": "Work",
            "list_id": "cal-work",
        }

    def test_minimal_reminder(self):
        cal = MockCalendar("Default", identifier="cal-default")
        rem = MockReminder(title="Simple", identifier="rem-2", calendar=cal)

        result = _format_reminder(rem)

        assert result == {
            "id": "rem-2",
            "title": "Simple",
            "due_date": None,
            "priority": "none",
            "notes": None,
            "list": "Default",
            "list_id": "cal-default",
        }

    def test_reminder_without_calendar(self):
        rem = MockReminder(title="Orphan", identifier="rem-3")

        result = _format_reminder(rem)

        assert result["list"] is None


# ---------------------------------------------------------------------------
# Tests: list_reminder_lists
# ---------------------------------------------------------------------------


class TestListReminderLists:
    def test_returns_lists_with_counts(self, mock_service):
        cal_work = MockCalendar("Work", identifier="cal-work")
        cal_personal = MockCalendar("Personal", identifier="cal-personal")
        mock_service.get_all_lists.return_value = [cal_work, cal_personal]

        rem1 = MockReminder("Task 1", calendar=cal_work)
        rem2 = MockReminder("Task 2", calendar=cal_work)
        rem3 = MockReminder("Task 3", calendar=cal_personal)
        mock_service.get_all_incomplete_reminders.return_value = [
            rem1,
            rem2,
            rem3,
        ]

        result = list_reminder_lists()

        assert result == [
            {"id": "cal-work", "name": "Work", "incomplete_count": 2},
            {"id": "cal-personal", "name": "Personal", "incomplete_count": 1},
        ]

    def test_empty_lists(self, mock_service):
        mock_service.get_all_lists.return_value = []
        mock_service.get_all_incomplete_reminders.return_value = []

        assert list_reminder_lists() == []

    def test_list_with_zero_reminders(self, mock_service):
        cal = MockCalendar("Empty", identifier="cal-empty")
        mock_service.get_all_lists.return_value = [cal]
        mock_service.get_all_incomplete_reminders.return_value = []

        result = list_reminder_lists()

        assert result == [
            {"id": "cal-empty", "name": "Empty", "incomplete_count": 0}
        ]


# ---------------------------------------------------------------------------
# Tests: create_list
# ---------------------------------------------------------------------------


class TestCreateList:
    def test_creates_list(self, mock_service):
        mock_cal = MockCalendar("Shopping")
        mock_service.create_list.return_value = mock_cal

        result = create_list("Shopping")

        assert result == {"name": "Shopping", "created": True}
        mock_service.create_list.assert_called_once_with("Shopping")


# ---------------------------------------------------------------------------
# Tests: show_incomplete_reminders
# ---------------------------------------------------------------------------


class TestShowIncompleteReminders:
    def test_returns_formatted_reminders(self, mock_service):
        cal = MockCalendar("Work", identifier="cal-work")
        due = MockDateComponents(2026, 3, 15, 10, 30)
        rem = MockReminder(
            title="Buy milk",
            identifier="rem-1",
            calendar=cal,
            priority=1,
            notes="Whole milk",
            due_components=due,
        )
        mock_service.get_incomplete_reminders.return_value = [rem]

        result = show_incomplete_reminders("Work")

        assert result == [
            {
                "id": "rem-1",
                "title": "Buy milk",
                "due_date": "2026-03-15T10:30",
                "priority": "high",
                "notes": "Whole milk",
                "list": "Work",
                "list_id": "cal-work",
            }
        ]
        mock_service.get_incomplete_reminders.assert_called_once_with("Work", None)

    def test_empty_list(self, mock_service):
        mock_service.get_incomplete_reminders.return_value = []

        assert show_incomplete_reminders("Work") == []

    def test_reminder_without_optional_fields(self, mock_service):
        cal = MockCalendar("Work", identifier="cal-work")
        rem = MockReminder(
            title="Simple task", identifier="rem-2", calendar=cal
        )
        mock_service.get_incomplete_reminders.return_value = [rem]

        result = show_incomplete_reminders("Work")

        assert result == [
            {
                "id": "rem-2",
                "title": "Simple task",
                "due_date": None,
                "priority": "none",
                "notes": None,
                "list": "Work",
                "list_id": "cal-work",
            }
        ]


# ---------------------------------------------------------------------------
# Tests: show_all_incomplete_reminders
# ---------------------------------------------------------------------------


class TestShowAllIncompleteReminders:
    def test_groups_by_list(self, mock_service):
        cal_work = MockCalendar("Work")
        cal_personal = MockCalendar("Personal")
        rem1 = MockReminder(
            title="Task 1", identifier="rem-1", calendar=cal_work
        )
        rem2 = MockReminder(
            title="Task 2", identifier="rem-2", calendar=cal_personal
        )
        rem3 = MockReminder(
            title="Task 3", identifier="rem-3", calendar=cal_work
        )
        mock_service.get_all_incomplete_reminders.return_value = [
            rem1,
            rem2,
            rem3,
        ]

        result = show_all_incomplete_reminders()

        assert "Work" in result
        assert "Personal" in result
        assert len(result["Work"]) == 2
        assert len(result["Personal"]) == 1
        assert result["Work"][0]["title"] == "Task 1"
        assert result["Work"][1]["title"] == "Task 3"
        assert result["Personal"][0]["title"] == "Task 2"

    def test_empty(self, mock_service):
        mock_service.get_all_incomplete_reminders.return_value = []

        assert show_all_incomplete_reminders() == {}

    def test_reminder_without_calendar_goes_to_unknown(self, mock_service):
        rem = MockReminder(title="Orphan", identifier="rem-1")
        mock_service.get_all_incomplete_reminders.return_value = [rem]

        result = show_all_incomplete_reminders()

        assert "Unknown" in result
        assert result["Unknown"][0]["title"] == "Orphan"


# ---------------------------------------------------------------------------
# Tests: completion date formatting + completed reminder formatting
# ---------------------------------------------------------------------------


class TestFormatCompletionDate:
    def test_none(self):
        assert _format_completion_date(None) is None

    def test_formats_iso(self):
        ts = datetime(2026, 4, 20, 14, 30, 5).timestamp()
        assert (
            _format_completion_date(MockNSDate(ts))
            == "2026-04-20T14:30:05"
        )


class TestFormatCompletedReminder:
    def test_includes_completion_date(self):
        cal = MockCalendar("Work", identifier="cal-work")
        ts = datetime(2026, 4, 20, 9, 0).timestamp()
        rem = MockReminder(
            title="Done",
            identifier="rem-9",
            calendar=cal,
            completion_date=MockNSDate(ts),
        )

        result = _format_completed_reminder(rem)

        assert result["id"] == "rem-9"
        assert result["title"] == "Done"
        assert result["list"] == "Work"
        assert result["completion_date"] == "2026-04-20T09:00:00"

    def test_missing_completion_date(self):
        cal = MockCalendar("Work")
        rem = MockReminder(title="Done", identifier="rem-9", calendar=cal)

        result = _format_completed_reminder(rem)

        assert result["completion_date"] is None


# ---------------------------------------------------------------------------
# Tests: show_completed_reminders_today
# ---------------------------------------------------------------------------


class TestShowCompletedRemindersToday:
    def test_defaults_to_today(self, mock_service):
        cal = MockCalendar("Work", identifier="cal-work")
        ts = datetime(2026, 4, 20, 9, 0).timestamp()
        rem = MockReminder(
            title="Finished",
            identifier="rem-1",
            calendar=cal,
            completion_date=MockNSDate(ts),
        )
        mock_service.get_completed_reminders_for_day.return_value = [rem]

        result = show_completed_reminders_today()

        assert result == [
            {
                "id": "rem-1",
                "title": "Finished",
                "due_date": None,
                "priority": "none",
                "notes": None,
                "list": "Work",
                "list_id": "cal-work",
                "completion_date": "2026-04-20T09:00:00",
            }
        ]
        mock_service.get_completed_reminders_for_day.assert_called_once_with(
            None
        )

    def test_specific_day(self, mock_service):
        mock_service.get_completed_reminders_for_day.return_value = []

        result = show_completed_reminders_today("2026-04-19")

        assert result == []
        mock_service.get_completed_reminders_for_day.assert_called_once_with(
            date(2026, 4, 19)
        )

    def test_invalid_date_raises(self, mock_service):
        with pytest.raises(ValueError):
            show_completed_reminders_today("not-a-date")


# ---------------------------------------------------------------------------
# Tests: list identifiers on the tool surface
#
# `apple-calendar-mcp` already returns `calendar_id` everywhere and documents it
# as "preferred, stable across renames". These bring this server to parity.
# ---------------------------------------------------------------------------


class TestListIdentifiers:
    def test_two_lists_sharing_a_name_are_distinguishable_by_id(self, mock_service):
        """The case the ids exist for. Without them these two rows are identical."""
        a = MockCalendar("Projects", identifier="cal-a")
        b = MockCalendar("Projects", identifier="cal-b")
        mock_service.get_all_lists.return_value = [a, b]
        mock_service.get_all_incomplete_reminders.return_value = []

        result = list_reminder_lists()

        assert [row["id"] for row in result] == ["cal-a", "cal-b"]
        assert {row["name"] for row in result} == {"Projects"}

    def test_a_reminder_carries_the_id_of_the_list_holding_it(self, mock_service):
        cal = MockCalendar("Projects", identifier="cal-b")
        rem = MockReminder(title="Ship it", identifier="rem-9", calendar=cal)
        mock_service.get_incomplete_reminders.return_value = [rem]

        result = show_incomplete_reminders(list_id="cal-b")

        assert result[0]["list_id"] == "cal-b"
        mock_service.get_incomplete_reminders.assert_called_once_with(None, "cal-b")

    def test_an_id_is_passed_through_in_preference_to_a_name(self, mock_service):
        mock_service.get_incomplete_reminders.return_value = []
        show_incomplete_reminders(list_name="Projects", list_id="cal-b")
        mock_service.get_incomplete_reminders.assert_called_once_with("Projects", "cal-b")

    def test_a_reminder_with_no_list_reports_no_id(self, mock_service):
        rem = MockReminder(title="Orphan", identifier="rem-0", calendar=None)
        mock_service.get_incomplete_reminders.return_value = [rem]

        result = show_incomplete_reminders(list_name="Whatever")

        assert result[0]["list"] is None
        assert result[0]["list_id"] is None
