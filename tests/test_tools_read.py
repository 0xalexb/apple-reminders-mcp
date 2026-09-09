from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from apple_reminders_mcp.server import (
    _format_alarm,
    _format_attendee,
    _format_completed_reminder,
    _format_due_date,
    _format_ns_date,
    _format_priority,
    _format_recurrence_rule,
    _format_reminder,
    create_list,
    list_reminder_lists,
    show_all_incomplete_reminders,
    show_completed_reminders_today,
    show_incomplete_reminders,
)
from tests.mocks import (
    MockAlarm,
    MockCalendar,
    MockDateComponents,
    MockDayOfWeek,
    MockNSDate,
    MockNSNumber,
    MockNSTimeZone,
    MockNSURL,
    MockParticipant,
    MockRecurrenceEnd,
    MockRecurrenceRule,
    MockReminder,
    MockSource,
    MockStructuredLocation,
)


def _iso(*args) -> str:
    """The local-time ISO 8601 string, carrying the UTC offset the formatter emits."""
    return datetime(*args).astimezone().isoformat()


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
            "is_completed": False,
            "start_date": None,
            "url": None,
            "location": None,
            "created_at": None,
            "last_modified_at": None,
            "external_id": None,
            "time_zone": None,
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
            "is_completed": False,
            "start_date": None,
            "url": None,
            "location": None,
            "created_at": None,
            "last_modified_at": None,
            "external_id": None,
            "time_zone": None,
        }

    def test_reminder_without_calendar(self):
        rem = MockReminder(title="Orphan", identifier="rem-3")

        result = _format_reminder(rem)

        assert result["list"] is None

    def test_all_scalar_fields_populated(self):
        cal = MockCalendar("Work", identifier="cal-work")
        created = datetime(2026, 1, 2, 8, 15).timestamp()
        modified = datetime(2026, 1, 3, 9, 45, 30).timestamp()
        rem = MockReminder(
            title="Ship it",
            identifier="rem-7",
            calendar=cal,
            completion_date=MockNSDate(modified),
            start_components=MockDateComponents(2026, 3, 1, 9, 0),
            url=MockNSURL("https://example.com/task"),
            location="Office",
            creation_date=MockNSDate(created),
            last_modified_date=MockNSDate(modified),
            external_id="ext-7",
            time_zone=MockNSTimeZone("Europe/Berlin"),
        )

        result = _format_reminder(rem)

        assert result["is_completed"] is True
        assert result["start_date"] == "2026-03-01T09:00"
        assert result["url"] == "https://example.com/task"
        assert result["location"] == "Office"
        assert result["created_at"] == _iso(2026, 1, 2, 8, 15)
        assert result["last_modified_at"] == _iso(2026, 1, 3, 9, 45, 30)
        assert result["external_id"] == "ext-7"
        assert result["time_zone"] == "Europe/Berlin"

    def test_bare_reminder_emits_scalars_rather_than_omitting_them(self):
        rem = MockReminder(title="Bare", identifier="rem-8")

        result = _format_reminder(rem)

        assert len(result) == 15
        assert result["is_completed"] is False
        for key in (
            "start_date",
            "url",
            "location",
            "created_at",
            "last_modified_at",
            "external_id",
            "time_zone",
        ):
            assert key in result
            assert result[key] is None

    def test_start_date_unset_sentinel_returns_none(self):
        rem = MockReminder(
            title="Floating",
            identifier="rem-10",
            start_components=MockDateComponents(2**63 - 1, 3, 15),
        )

        assert _format_reminder(rem)["start_date"] is None


# ---------------------------------------------------------------------------
# Tests: _format_alarm
# ---------------------------------------------------------------------------


class TestFormatAlarm:
    def test_absolute_time_alarm(self):
        ts = datetime(2026, 3, 15, 9, 0).timestamp()
        alarm = MockAlarm(absolute_date=MockNSDate(ts))

        assert _format_alarm(alarm) == {
            "absolute_date": _iso(2026, 3, 15, 9, 0),
            "relative_offset": None,
            "proximity": "none",
        }

    def test_relative_offset_alarm(self):
        alarm = MockAlarm(relative_offset=-3600.0)

        assert _format_alarm(alarm) == {
            "absolute_date": None,
            "relative_offset": -3600.0,
            "proximity": "none",
        }

    def test_geofence_alarm(self):
        alarm = MockAlarm(
            proximity=1,
            structured_location=MockStructuredLocation("Home", 150.0),
        )

        assert _format_alarm(alarm) == {
            "absolute_date": None,
            "relative_offset": None,
            "proximity": "enter",
            "location": {"title": "Home", "radius": 150.0},
        }

    def test_leave_proximity(self):
        alarm = MockAlarm(
            proximity=2,
            structured_location=MockStructuredLocation("Office", 200.0),
        )

        result = _format_alarm(alarm)

        assert result["proximity"] == "leave"
        assert result["relative_offset"] is None
        assert result["location"] == {"title": "Office", "radius": 200.0}


class TestReminderAlarms:
    def test_alarms_included_when_present(self):
        ts = datetime(2026, 3, 15, 9, 0).timestamp()
        rem = MockReminder(
            title="Wake up",
            identifier="rem-11",
            alarms=[
                MockAlarm(absolute_date=MockNSDate(ts)),
                MockAlarm(relative_offset=-900.0),
            ],
        )

        result = _format_reminder(rem)

        assert result["alarms"] == [
            {
                "absolute_date": _iso(2026, 3, 15, 9, 0),
                "relative_offset": None,
                "proximity": "none",
            },
            {
                "absolute_date": None,
                "relative_offset": -900.0,
                "proximity": "none",
            },
        ]

    def test_no_alarms_key_absent(self):
        rem = MockReminder(title="Bare", identifier="rem-12")

        assert "alarms" not in _format_reminder(rem)


# ---------------------------------------------------------------------------
# Tests: _format_recurrence_rule
# ---------------------------------------------------------------------------


class TestFormatRecurrenceRule:
    def test_simple_daily_rule(self):
        rule = MockRecurrenceRule(frequency=0, interval=1)

        assert _format_recurrence_rule(rule) == {
            "frequency": "daily",
            "interval": 1,
            "end_date": None,
            "occurrence_count": None,
        }

    def test_every_two_weeks_on_monday_and_wednesday(self):
        rule = MockRecurrenceRule(
            frequency=1,
            interval=2,
            days_of_week=[MockDayOfWeek(2), MockDayOfWeek(4)],
        )

        result = _format_recurrence_rule(rule)

        assert result["frequency"] == "weekly"
        assert result["interval"] == 2
        assert result["days_of_week"] == [
            {"day": 2, "week_number": None},
            {"day": 4, "week_number": None},
        ]

    def test_first_monday_of_every_month(self):
        rule = MockRecurrenceRule(
            frequency=2,
            days_of_week=[MockDayOfWeek(2, week_number=1)],
        )

        result = _format_recurrence_rule(rule)

        assert result["frequency"] == "monthly"
        assert result["days_of_week"] == [{"day": 2, "week_number": 1}]

    def test_numeric_collections_are_coerced_to_int(self):
        rule = MockRecurrenceRule(
            frequency=3,
            days_of_month=[MockNSNumber(1), MockNSNumber(15)],
            months_of_year=[MockNSNumber(6)],
            set_positions=[MockNSNumber(-1)],
        )

        result = _format_recurrence_rule(rule)

        assert result["days_of_month"] == [1, 15]
        assert result["months_of_year"] == [6]
        assert result["set_positions"] == [-1]
        for value in (
            result["days_of_month"]
            + result["months_of_year"]
            + result["set_positions"]
        ):
            assert type(value) is int

    def test_rule_ending_on_a_date(self):
        ts = datetime(2026, 6, 30, 12, 0).timestamp()
        rule = MockRecurrenceRule(
            frequency=1,
            interval=2,
            recurrence_end=MockRecurrenceEnd(end_date=MockNSDate(ts)),
        )

        result = _format_recurrence_rule(rule)

        assert result["end_date"] == _iso(2026, 6, 30, 12, 0)
        assert result["occurrence_count"] is None

    def test_rule_ending_after_occurrences(self):
        rule = MockRecurrenceRule(
            frequency=0,
            recurrence_end=MockRecurrenceEnd(occurrence_count=10),
        )

        result = _format_recurrence_rule(rule)

        assert result["end_date"] is None
        assert result["occurrence_count"] == 10

    def test_empty_collections_are_omitted(self):
        rule = MockRecurrenceRule(
            frequency=0,
            days_of_week=[],
            days_of_month=[],
            months_of_year=[],
            set_positions=[],
        )

        result = _format_recurrence_rule(rule)

        for key in ("days_of_week", "days_of_month", "months_of_year", "set_positions"):
            assert key not in result


class TestReminderRecurrence:
    def test_recurrence_included_when_present(self):
        rem = MockReminder(
            title="Standup",
            identifier="rem-13",
            recurrence_rules=[MockRecurrenceRule(frequency=1, interval=2)],
        )

        result = _format_reminder(rem)

        assert result["recurrence"] == [
            {
                "frequency": "weekly",
                "interval": 2,
                "end_date": None,
                "occurrence_count": None,
            }
        ]

    def test_no_rules_key_absent(self):
        rem = MockReminder(title="Bare", identifier="rem-14")

        assert "recurrence" not in _format_reminder(rem)


# ---------------------------------------------------------------------------
# Tests: _format_attendee
# ---------------------------------------------------------------------------


class TestFormatAttendee:
    def test_attendee_with_url_and_status(self):
        participant = MockParticipant(
            "Alice", url=MockNSURL("mailto:alice@example.com"), status=2
        )

        assert _format_attendee(participant) == {
            "name": "Alice",
            "url": "mailto:alice@example.com",
            "status": "accepted",
        }

    def test_attendee_without_url(self):
        participant = MockParticipant("Bob", status=1)

        assert _format_attendee(participant) == {
            "name": "Bob",
            "url": None,
            "status": "pending",
        }


class TestReminderAttendees:
    def test_attendees_included_when_present(self):
        rem = MockReminder(
            title="Shared task",
            identifier="rem-15",
            attendees=[
                MockParticipant(
                    "Alice", url=MockNSURL("mailto:alice@example.com"), status=2
                ),
                MockParticipant(
                    "Bob", url=MockNSURL("mailto:bob@example.com"), status=3
                ),
            ],
        )

        result = _format_reminder(rem)

        assert result["attendees"] == [
            {
                "name": "Alice",
                "url": "mailto:alice@example.com",
                "status": "accepted",
            },
            {
                "name": "Bob",
                "url": "mailto:bob@example.com",
                "status": "declined",
            },
        ]

    def test_none_attendees_key_absent(self):
        rem = MockReminder(title="Bare", identifier="rem-16", attendees=None)

        assert "attendees" not in _format_reminder(rem)

    def test_empty_attendees_key_absent(self):
        rem = MockReminder(title="Bare", identifier="rem-17", attendees=[])

        assert "attendees" not in _format_reminder(rem)


# ---------------------------------------------------------------------------
# Tests: list_reminder_lists
# ---------------------------------------------------------------------------


class TestListReminderLists:
    def test_returns_lists_with_counts(self, mock_service):
        cal_work = MockCalendar("Work", identifier="cal-work")
        cal_personal = MockCalendar("Personal", identifier="cal-personal")
        mock_service.get_all_lists.return_value = [cal_work, cal_personal]
        mock_service.calendar_color_hex.return_value = "#ff0080"

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
            {
                "id": "cal-work",
                "name": "Work",
                "incomplete_count": 2,
                "color": "#ff0080",
                "source_name": None,
                "source_type": None,
                "writable": True,
                "is_subscribed": False,
            },
            {
                "id": "cal-personal",
                "name": "Personal",
                "incomplete_count": 1,
                "color": "#ff0080",
                "source_name": None,
                "source_type": None,
                "writable": True,
                "is_subscribed": False,
            },
        ]

    def test_empty_lists(self, mock_service):
        mock_service.get_all_lists.return_value = []
        mock_service.get_all_incomplete_reminders.return_value = []

        assert list_reminder_lists() == []

    def test_list_with_zero_reminders(self, mock_service):
        cal = MockCalendar("Empty", identifier="cal-empty")
        mock_service.get_all_lists.return_value = [cal]
        mock_service.get_all_incomplete_reminders.return_value = []
        mock_service.calendar_color_hex.return_value = None

        result = list_reminder_lists()

        assert result == [
            {
                "id": "cal-empty",
                "name": "Empty",
                "incomplete_count": 0,
                "color": None,
                "source_name": None,
                "source_type": None,
                "writable": True,
                "is_subscribed": False,
            }
        ]

    def test_writable_icloud_list(self, mock_service):
        cal = MockCalendar(
            "Groceries",
            identifier="cal-icloud",
            source=MockSource("iCloud", 2),
        )
        mock_service.get_all_lists.return_value = [cal]
        mock_service.get_all_incomplete_reminders.return_value = []
        mock_service.calendar_color_hex.return_value = "#ff0080"

        row = list_reminder_lists()[0]

        assert len(row) == 8
        assert row["color"] == "#ff0080"
        assert row["source_name"] == "iCloud"
        assert row["source_type"] == "caldav"
        assert row["writable"] is True
        assert row["is_subscribed"] is False

    def test_read_only_subscribed_list(self, mock_service):
        cal = MockCalendar(
            "Holidays",
            identifier="cal-sub",
            source=MockSource("Subscribed Calendars", 4),
            allows_modifications=False,
            subscribed=True,
        )
        mock_service.get_all_lists.return_value = [cal]
        mock_service.get_all_incomplete_reminders.return_value = []
        mock_service.calendar_color_hex.return_value = "#00ff00"

        row = list_reminder_lists()[0]

        assert row["source_type"] == "subscribed"
        assert row["writable"] is False
        assert row["is_subscribed"] is True

    def test_list_without_a_source(self, mock_service):
        cal = MockCalendar("Orphan", identifier="cal-orphan", source=None)
        mock_service.get_all_lists.return_value = [cal]
        mock_service.get_all_incomplete_reminders.return_value = []
        mock_service.calendar_color_hex.return_value = None

        row = list_reminder_lists()[0]

        assert row["source_name"] is None
        assert row["source_type"] is None

    def test_each_row_carries_its_own_colour_and_source(self, mock_service):
        """Two rows, two colours, two accounts: proves the per-row lookup, not one shared answer."""
        work = MockCalendar(
            "Work", identifier="cal-work", source=MockSource("iCloud", 2)
        )
        local = MockCalendar(
            "Local",
            identifier="cal-local",
            source=MockSource("On My Mac", 0),
            allows_modifications=False,
            subscribed=True,
        )
        colors = {"cal-work": "#ff0080", "cal-local": "#00ff00"}
        mock_service.get_all_lists.return_value = [work, local]
        mock_service.get_all_incomplete_reminders.return_value = []
        mock_service.calendar_color_hex.side_effect = (
            lambda cal: colors[cal.calendarIdentifier()]
        )

        rows = {row["id"]: row for row in list_reminder_lists()}

        assert rows["cal-work"]["color"] == "#ff0080"
        assert rows["cal-local"]["color"] == "#00ff00"
        assert rows["cal-work"]["source_name"] == "iCloud"
        assert rows["cal-local"]["source_name"] == "On My Mac"
        assert rows["cal-work"]["source_type"] == "caldav"
        assert rows["cal-local"]["source_type"] == "local"
        assert rows["cal-work"]["writable"] is True
        assert rows["cal-local"]["writable"] is False
        assert rows["cal-work"]["is_subscribed"] is False
        assert rows["cal-local"]["is_subscribed"] is True
        assert [
            call.args[0] for call in mock_service.calendar_color_hex.call_args_list
        ] == [work, local]


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
                "is_completed": False,
                "start_date": None,
                "url": None,
                "location": None,
                "created_at": None,
                "last_modified_at": None,
                "external_id": None,
                "time_zone": None,
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
                "is_completed": False,
                "start_date": None,
                "url": None,
                "location": None,
                "created_at": None,
                "last_modified_at": None,
                "external_id": None,
                "time_zone": None,
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


class TestFormatNsDate:
    def test_none(self):
        assert _format_ns_date(None) is None

    def test_an_nsdate_becomes_an_offset_carrying_iso_string(self):
        ts = datetime(2026, 4, 20, 14, 30, 5).timestamp()

        result = _format_ns_date(MockNSDate(ts))

        assert result == _iso(2026, 4, 20, 14, 30, 5)
        assert datetime.fromisoformat(result).utcoffset() is not None

    @pytest.mark.parametrize(
        "timestamp",
        [
            -63114076800.0,  # NSDate.distantPast, year 1
            1e18,
            -1e18,
        ],
    )
    def test_unrepresentable_dates_return_none_rather_than_raising(self, timestamp):
        assert _format_ns_date(MockNSDate(timestamp)) is None

    def test_one_unrepresentable_date_does_not_sink_the_whole_reminder(self):
        rem = MockReminder(
            title="Synced from elsewhere",
            identifier="rem-18",
            creation_date=MockNSDate(-63114076800.0),
        )

        result = _format_reminder(rem)

        assert result["created_at"] is None
        assert result["title"] == "Synced from elsewhere"


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
        assert result["completion_date"] == _iso(2026, 4, 20, 9, 0)

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
                "is_completed": True,
                "start_date": None,
                "url": None,
                "location": None,
                "created_at": None,
                "last_modified_at": None,
                "external_id": None,
                "time_zone": None,
                "completion_date": _iso(2026, 4, 20, 9, 0),
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


# ---------------------------------------------------------------------------
# Tests: unmapped EventKit enum values
# ---------------------------------------------------------------------------


class TestUnmappedEnumValues:
    def test_an_unknown_alarm_proximity(self):
        assert _format_alarm(MockAlarm(proximity=99))["proximity"] == "custom(99)"

    def test_an_unknown_recurrence_frequency(self):
        rule = MockRecurrenceRule(frequency=99)
        assert _format_recurrence_rule(rule)["frequency"] == "custom(99)"

    def test_an_unknown_participant_status(self):
        participant = MockParticipant("Alice", status=99)
        assert _format_attendee(participant)["status"] == "custom(99)"

    def test_an_unknown_source_type(self, mock_service):
        cal = MockCalendar(
            "Odd", identifier="cal-odd", source=MockSource("Elsewhere", 99)
        )
        mock_service.get_all_lists.return_value = [cal]
        mock_service.get_all_incomplete_reminders.return_value = []

        assert list_reminder_lists()[0]["source_type"] == "custom(99)"


# ---------------------------------------------------------------------------
# Tests: a reminder carrying every collection at once
# ---------------------------------------------------------------------------


def _kitchen_sink_reminder(completion_date=None):
    return MockReminder(
        completion_date=completion_date,
        title="Everything",
        identifier="rem-20",
        calendar=MockCalendar("Work", identifier="cal-work"),
        priority=5,
        notes="All of it",
        due_components=MockDateComponents(2026, 3, 15, 10, 30),
        start_components=MockDateComponents(2026, 3, 1, 9, 0),
        url=MockNSURL("https://example.com/task"),
        location="Office",
        creation_date=MockNSDate(datetime(2026, 1, 2, 8, 15).timestamp()),
        last_modified_date=MockNSDate(datetime(2026, 1, 3, 9, 45).timestamp()),
        external_id="ext-20",
        time_zone=MockNSTimeZone("Europe/Berlin"),
        alarms=[
            MockAlarm(relative_offset=-900.0),
            MockAlarm(
                proximity=1,
                structured_location=MockStructuredLocation("Home", 150.0),
            ),
            MockAlarm(
                proximity=2,
                structured_location=MockStructuredLocation("Office", 200.0),
            ),
        ],
        recurrence_rules=[
            MockRecurrenceRule(
                frequency=1, interval=2, days_of_week=[MockDayOfWeek(2)]
            ),
            MockRecurrenceRule(
                frequency=2,
                days_of_month=[MockNSNumber(1)],
                recurrence_end=MockRecurrenceEnd(occurrence_count=5),
            ),
        ],
        attendees=[MockParticipant("Alice", status=2)],
    )


class TestReminderWithEveryCollection:
    def test_the_full_eighteen_key_shape(self):
        result = _format_reminder(_kitchen_sink_reminder())

        assert result == {
            "id": "rem-20",
            "title": "Everything",
            "due_date": "2026-03-15T10:30",
            "priority": "medium",
            "notes": "All of it",
            "list": "Work",
            "list_id": "cal-work",
            "is_completed": False,
            "start_date": "2026-03-01T09:00",
            "url": "https://example.com/task",
            "location": "Office",
            "created_at": _iso(2026, 1, 2, 8, 15),
            "last_modified_at": _iso(2026, 1, 3, 9, 45),
            "external_id": "ext-20",
            "time_zone": "Europe/Berlin",
            "alarms": [
                {
                    "absolute_date": None,
                    "relative_offset": -900.0,
                    "proximity": "none",
                },
                {
                    "absolute_date": None,
                    "relative_offset": None,
                    "proximity": "enter",
                    "location": {"title": "Home", "radius": 150.0},
                },
                {
                    "absolute_date": None,
                    "relative_offset": None,
                    "proximity": "leave",
                    "location": {"title": "Office", "radius": 200.0},
                },
            ],
            "recurrence": [
                {
                    "frequency": "weekly",
                    "interval": 2,
                    "days_of_week": [{"day": 2, "week_number": None}],
                    "end_date": None,
                    "occurrence_count": None,
                },
                {
                    "frequency": "monthly",
                    "interval": 1,
                    "days_of_month": [1],
                    "end_date": None,
                    "occurrence_count": 5,
                },
            ],
            "attendees": [{"name": "Alice", "url": None, "status": "accepted"}],
        }

    def test_null_collections_leave_the_keys_absent(self):
        rem = MockReminder(
            title="Never synced",
            identifier="rem-21",
            alarms=None,
            recurrence_rules=None,
            attendees=None,
        )

        result = _format_reminder(rem)

        assert "alarms" not in result
        assert "recurrence" not in result
        assert "attendees" not in result


# ---------------------------------------------------------------------------
# Tests: every tool payload survives a JSON round-trip
# ---------------------------------------------------------------------------


class TestPayloadsAreJsonSerialisable:
    def test_list_reminder_lists(self, mock_service):
        cal = MockCalendar(
            "Work", identifier="cal-work", source=MockSource("iCloud", 2)
        )
        mock_service.get_all_lists.return_value = [cal]
        mock_service.get_all_incomplete_reminders.return_value = []

        payload = list_reminder_lists()

        assert json.loads(json.dumps(payload)) == payload

    def test_show_incomplete_reminders(self, mock_service):
        mock_service.get_incomplete_reminders.return_value = [
            _kitchen_sink_reminder()
        ]

        payload = show_incomplete_reminders("Work")

        assert json.loads(json.dumps(payload)) == payload

    def test_show_all_incomplete_reminders(self, mock_service):
        mock_service.get_all_incomplete_reminders.return_value = [
            _kitchen_sink_reminder()
        ]

        payload = show_all_incomplete_reminders()

        assert json.loads(json.dumps(payload)) == payload

    def test_show_completed_reminders_today(self, mock_service):
        rem = _kitchen_sink_reminder(
            completion_date=MockNSDate(datetime(2026, 4, 20, 9, 0).timestamp())
        )
        mock_service.get_completed_reminders_for_day.return_value = [rem]

        payload = show_completed_reminders_today()

        assert json.loads(json.dumps(payload)) == payload
