from __future__ import annotations

import json
from datetime import datetime

import pytest

from apple_reminders_mcp.server import (
    complete_reminder,
    create_reminder,
    delete_reminder,
    move_reminder,
    quick_capture,
)
from tests.mocks import MockCalendar, MockDateComponents, MockReminder


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
            list_id=None,
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
            "rem-7", "Personal", None
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


class TestListIdentifiersOnWrites:
    """Creating into, or moving into, a duplicated list name is ambiguous the same way reads are."""

    def test_create_passes_the_id_through(self, mock_service):
        mock_service.create_reminder.return_value = MockReminder(
            title="Ship it", identifier="rem-1"
        )
        create_reminder("Ship it", list_id="cal-b")
        assert mock_service.create_reminder.call_args.kwargs["list_id"] == "cal-b"

    def test_move_passes_the_id_through(self, mock_service):
        mock_service.move_reminder.return_value = MockReminder(
            title="Ship it", identifier="rem-1"
        )
        move_reminder("rem-1", target_list_id="cal-b")
        mock_service.move_reminder.assert_called_once_with("rem-1", None, "cal-b")

    def test_move_still_accepts_a_name_alone(self, mock_service):
        mock_service.move_reminder.return_value = MockReminder(
            title="Ship it", identifier="rem-1"
        )
        move_reminder("rem-1", "Personal")
        mock_service.move_reminder.assert_called_once_with("rem-1", "Personal", None)


# ---------------------------------------------------------------------------
# Tests: the write tools return the same reminder shape the read tools do
# ---------------------------------------------------------------------------


_REMINDER_KEYS = {
    "id",
    "title",
    "due_date",
    "priority",
    "notes",
    "list",
    "list_id",
    "is_completed",
    "start_date",
    "url",
    "location",
    "created_at",
    "last_modified_at",
    "external_id",
    "time_zone",
}


class TestWriteToolsReturnTheFullReminderShape:
    def test_create_reminder(self, mock_service):
        mock_service.create_reminder.return_value = MockReminder(
            title="Ship it", identifier="rem-1", calendar=MockCalendar("Work")
        )

        result = create_reminder("Ship it")

        assert set(result) == _REMINDER_KEYS
        assert json.loads(json.dumps(result)) == result

    def test_move_reminder(self, mock_service):
        mock_service.move_reminder.return_value = MockReminder(
            title="Ship it", identifier="rem-1", calendar=MockCalendar("Work")
        )

        result = move_reminder("rem-1", "Work")

        assert set(result) == _REMINDER_KEYS
        assert json.loads(json.dumps(result)) == result

    def test_quick_capture(self, mock_service):
        mock_service.create_reminder.return_value = MockReminder(
            title="Idea", identifier="rem-1", calendar=MockCalendar("Default")
        )

        result = quick_capture("Idea")

        assert set(result) == _REMINDER_KEYS
        assert json.loads(json.dumps(result)) == result

    def test_a_completed_reminder_reports_itself_completed(self, mock_service):
        mock_service.move_reminder.return_value = MockReminder(
            title="Already done",
            identifier="rem-2",
            calendar=MockCalendar("Work"),
            completed=True,
        )

        assert move_reminder("rem-2", "Work")["is_completed"] is True
