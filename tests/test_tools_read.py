from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apple_reminders_mcp.server import (
    _format_due_date,
    _format_priority,
    _format_reminder,
    create_list,
    list_reminder_lists,
    show_all_incomplete_reminders,
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
    ):
        self._title = title
        self._identifier = identifier
        self._calendar = calendar
        self._priority = priority
        self._notes = notes
        self._due = due_components

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
        cal = MockCalendar("Work")
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
        }

    def test_minimal_reminder(self):
        cal = MockCalendar("Default")
        rem = MockReminder(title="Simple", identifier="rem-2", calendar=cal)

        result = _format_reminder(rem)

        assert result == {
            "id": "rem-2",
            "title": "Simple",
            "due_date": None,
            "priority": "none",
            "notes": None,
            "list": "Default",
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
        cal_work = MockCalendar("Work")
        cal_personal = MockCalendar("Personal")
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
            {"name": "Work", "incomplete_count": 2},
            {"name": "Personal", "incomplete_count": 1},
        ]

    def test_empty_lists(self, mock_service):
        mock_service.get_all_lists.return_value = []
        mock_service.get_all_incomplete_reminders.return_value = []

        assert list_reminder_lists() == []

    def test_list_with_zero_reminders(self, mock_service):
        cal = MockCalendar("Empty")
        mock_service.get_all_lists.return_value = [cal]
        mock_service.get_all_incomplete_reminders.return_value = []

        result = list_reminder_lists()

        assert result == [{"name": "Empty", "incomplete_count": 0}]


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
        cal = MockCalendar("Work")
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
            }
        ]
        mock_service.get_incomplete_reminders.assert_called_once_with("Work")

    def test_empty_list(self, mock_service):
        mock_service.get_incomplete_reminders.return_value = []

        assert show_incomplete_reminders("Work") == []

    def test_reminder_without_optional_fields(self, mock_service):
        cal = MockCalendar("Work")
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
