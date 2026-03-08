from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from apple_reminders_mcp.server import (
    complete_reminder,
    create_reminder,
    delete_reminder,
    move_reminder,
    quick_capture,
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


@pytest.fixture()
def mock_service():
    service = MagicMock()
    with patch(
        "apple_reminders_mcp.server._get_service", return_value=service
    ):
        yield service


# ---------------------------------------------------------------------------
# Tests: create_reminder
# ---------------------------------------------------------------------------


class TestCreateReminder:
    def test_minimal_create(self, mock_service):
        cal = MockCalendar("Default")
        rem = MockReminder(
            title="Buy milk", identifier="rem-1", calendar=cal
        )
        mock_service.create_reminder.return_value = rem

        result = create_reminder("Buy milk")

        assert result["title"] == "Buy milk"
        assert result["id"] == "rem-1"
        assert result["list"] == "Default"
        mock_service.create_reminder.assert_called_once_with(
            title="Buy milk",
            list_name=None,
            due_date=None,
            priority=0,
            recurrence=None,
            notes=None,
            include_time=False,
        )

    def test_with_all_options(self, mock_service):
        cal = MockCalendar("Work")
        due = MockDateComponents(2026, 3, 15, 10, 30)
        rem = MockReminder(
            title="Meeting prep",
            identifier="rem-2",
            calendar=cal,
            priority=1,
            notes="Prepare slides",
            due_components=due,
        )
        mock_service.create_reminder.return_value = rem

        result = create_reminder(
            title="Meeting prep",
            list_name="Work",
            due_date="2026-03-15T10:30:00",
            priority="high",
            recurrence="weekly",
            notes="Prepare slides",
        )

        assert result["title"] == "Meeting prep"
        assert result["priority"] == "high"
        assert result["notes"] == "Prepare slides"
        assert result["due_date"] == "2026-03-15T10:30"
        assert result["list"] == "Work"
        call_kwargs = mock_service.create_reminder.call_args.kwargs
        assert call_kwargs["title"] == "Meeting prep"
        assert call_kwargs["list_name"] == "Work"
        assert call_kwargs["due_date"] == datetime(2026, 3, 15, 10, 30)
        assert call_kwargs["priority"] == 1
        assert call_kwargs["recurrence"] == "weekly"
        assert call_kwargs["notes"] == "Prepare slides"
        assert call_kwargs["include_time"] is True

    def test_priority_mapping(self, mock_service):
        cal = MockCalendar("Default")
        rem = MockReminder(title="T", calendar=cal)
        mock_service.create_reminder.return_value = rem

        for label, expected_int in [
            ("none", 0),
            ("low", 9),
            ("medium", 5),
            ("high", 1),
        ]:
            create_reminder(title="T", priority=label)
            call_kwargs = mock_service.create_reminder.call_args.kwargs
            assert call_kwargs["priority"] == expected_int, (
                f"Priority '{label}' should map to {expected_int}"
            )

    def test_invalid_priority_raises_value_error(self, mock_service):
        with pytest.raises(ValueError, match="Invalid priority 'urgent'"):
            create_reminder(title="T", priority="urgent")

    def test_due_date_parsing_date_only(self, mock_service):
        cal = MockCalendar("Default")
        rem = MockReminder(title="T", calendar=cal)
        mock_service.create_reminder.return_value = rem

        create_reminder(title="T", due_date="2026-03-15")

        call_kwargs = mock_service.create_reminder.call_args.kwargs
        assert call_kwargs["due_date"] == datetime(2026, 3, 15)
        assert call_kwargs["include_time"] is False

    def test_due_date_parsing_with_time(self, mock_service):
        cal = MockCalendar("Default")
        rem = MockReminder(title="T", calendar=cal)
        mock_service.create_reminder.return_value = rem

        create_reminder(title="T", due_date="2026-03-15T14:30:00")

        call_kwargs = mock_service.create_reminder.call_args.kwargs
        assert call_kwargs["due_date"] == datetime(2026, 3, 15, 14, 30)
        assert call_kwargs["include_time"] is True

    def test_service_error_propagates(self, mock_service):
        mock_service.create_reminder.side_effect = ValueError(
            "List 'Missing' not found"
        )

        with pytest.raises(ValueError, match="not found"):
            create_reminder(title="T", list_name="Missing")


# ---------------------------------------------------------------------------
# Tests: complete_reminder
# ---------------------------------------------------------------------------


class TestCompleteReminder:
    def test_completes_reminder(self, mock_service):
        rem = MockReminder(title="Done", identifier="rem-5")
        mock_service.complete_reminder.return_value = rem

        result = complete_reminder("rem-5")

        assert result == {"id": "rem-5", "completed": True}
        mock_service.complete_reminder.assert_called_once_with("rem-5")

    def test_not_found_propagates(self, mock_service):
        mock_service.complete_reminder.side_effect = ValueError(
            "Reminder 'bad-id' not found"
        )

        with pytest.raises(ValueError, match="not found"):
            complete_reminder("bad-id")


# ---------------------------------------------------------------------------
# Tests: delete_reminder
# ---------------------------------------------------------------------------


class TestDeleteReminder:
    def test_deletes_reminder(self, mock_service):
        mock_service.delete_reminder.return_value = None

        result = delete_reminder("rem-6")

        assert result == {"id": "rem-6", "deleted": True}
        mock_service.delete_reminder.assert_called_once_with("rem-6")

    def test_not_found_propagates(self, mock_service):
        mock_service.delete_reminder.side_effect = ValueError(
            "Reminder 'bad-id' not found"
        )

        with pytest.raises(ValueError, match="not found"):
            delete_reminder("bad-id")


# ---------------------------------------------------------------------------
# Tests: move_reminder
# ---------------------------------------------------------------------------


class TestMoveReminder:
    def test_moves_reminder(self, mock_service):
        cal = MockCalendar("Personal")
        rem = MockReminder(
            title="Moved task", identifier="rem-7", calendar=cal
        )
        mock_service.move_reminder.return_value = rem

        result = move_reminder("rem-7", "Personal")

        assert result["id"] == "rem-7"
        assert result["title"] == "Moved task"
        assert result["list"] == "Personal"
        mock_service.move_reminder.assert_called_once_with(
            "rem-7", "Personal"
        )

    def test_reminder_not_found_propagates(self, mock_service):
        mock_service.move_reminder.side_effect = ValueError(
            "Reminder 'bad-id' not found"
        )

        with pytest.raises(ValueError, match="not found"):
            move_reminder("bad-id", "Personal")

    def test_target_list_not_found_propagates(self, mock_service):
        mock_service.move_reminder.side_effect = ValueError(
            "List 'Missing' not found"
        )

        with pytest.raises(ValueError, match="not found"):
            move_reminder("rem-7", "Missing")


# ---------------------------------------------------------------------------
# Tests: quick_capture
# ---------------------------------------------------------------------------


class TestQuickCapture:
    def test_captures_with_title_only(self, mock_service):
        cal = MockCalendar("Default")
        rem = MockReminder(
            title="Quick idea", identifier="rem-8", calendar=cal
        )
        mock_service.create_reminder.return_value = rem

        result = quick_capture("Quick idea")

        assert result["title"] == "Quick idea"
        assert result["id"] == "rem-8"
        assert result["list"] == "Default"
        mock_service.create_reminder.assert_called_once_with(
            title="Quick idea", notes=None
        )

    def test_captures_with_notes(self, mock_service):
        cal = MockCalendar("Default")
        rem = MockReminder(
            title="Idea",
            identifier="rem-9",
            calendar=cal,
            notes="Some details",
        )
        mock_service.create_reminder.return_value = rem

        result = quick_capture("Idea", notes="Some details")

        assert result["title"] == "Idea"
        assert result["notes"] == "Some details"
        mock_service.create_reminder.assert_called_once_with(
            title="Idea", notes="Some details"
        )
