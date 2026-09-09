from __future__ import annotations

from uuid import uuid4

from apple_reminders_mcp.server import _UNSET_COMPONENT

REMINDER_KEYS = {
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


class MockSource:
    def __init__(self, title: str, source_type: int):
        self._title = title
        self._source_type = source_type

    def title(self):
        return self._title

    def sourceType(self):
        return self._source_type


class MockCalendar:
    def __init__(
        self,
        name: str,
        identifier: str | None = None,
        source=None,
        allows_modifications: bool = True,
        subscribed: bool = False,
    ):
        self._title = name
        self._identifier = identifier or f"cal-{uuid4().hex[:8]}"
        self._source = source
        self._allows_modifications = allows_modifications
        self._subscribed = subscribed

    def title(self):
        return self._title

    def calendarIdentifier(self):
        return self._identifier

    def source(self):
        return self._source

    def allowsContentModifications(self):
        return self._allows_modifications

    def isSubscribed(self):
        return self._subscribed


class MockReminder:
    def __init__(
        self,
        title: str = "",
        identifier: str = "rem-1",
        calendar=None,
        priority: int = 0,
        notes: str | None = None,
        due_components=None,
        start_components=None,
        url=None,
        location=None,
        creation_date=None,
        last_modified_date=None,
        external_id=None,
        time_zone=None,
        alarms=None,
        recurrence_rules=None,
        attendees=None,
        completed: bool | None = None,
        completion_date=None,
    ):
        self._title = title
        self._identifier = identifier
        self._calendar = calendar
        self._priority = priority
        self._notes = notes
        self._due = due_components
        self._start = start_components
        self._url = url
        self._location = location
        self._creation_date = creation_date
        self._last_modified_date = last_modified_date
        self._external_id = external_id
        self._time_zone = time_zone
        self._alarms = alarms
        self._recurrence_rules = recurrence_rules
        self._attendees = attendees
        self._completed = (
            completion_date is not None if completed is None else completed
        )
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

    def isCompleted(self):
        return self._completed

    def completionDate(self):
        return self._completion_date

    def startDateComponents(self):
        return self._start

    def URL(self):
        return self._url

    def location(self):
        return self._location

    def creationDate(self):
        return self._creation_date

    def lastModifiedDate(self):
        return self._last_modified_date

    def calendarItemExternalIdentifier(self):
        return self._external_id

    def timeZone(self):
        return self._time_zone

    def alarms(self):
        return self._alarms

    def recurrenceRules(self):
        return self._recurrence_rules

    def attendees(self):
        return self._attendees


class MockDateComponents:
    def __init__(self, year, month, day, hour=None, minute=None):
        self._year = year
        self._month = month
        self._day = day
        self._hour = hour if hour is not None else _UNSET_COMPONENT
        self._minute = minute if minute is not None else _UNSET_COMPONENT

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


class MockNSDate:
    def __init__(self, timestamp: float):
        self._timestamp = timestamp

    def timeIntervalSince1970(self):
        return self._timestamp


class MockNSURL:
    def __init__(self, url: str):
        self._url = url

    def absoluteString(self):
        return self._url


class MockNSTimeZone:
    def __init__(self, name: str):
        self._name = name

    def name(self):
        return self._name


class MockStructuredLocation:
    def __init__(self, title: str, radius: float):
        self._title = title
        self._radius = radius

    def title(self):
        return self._title

    def radius(self):
        return self._radius


class MockAlarm:
    def __init__(
        self,
        absolute_date=None,
        relative_offset: float = 0.0,
        proximity: int = 0,
        structured_location=None,
    ):
        self._absolute_date = absolute_date
        self._relative_offset = relative_offset
        self._proximity = proximity
        self._structured_location = structured_location

    def absoluteDate(self):
        return self._absolute_date

    def relativeOffset(self):
        return self._relative_offset

    def proximity(self):
        return self._proximity

    def structuredLocation(self):
        return self._structured_location


class MockParticipant:
    def __init__(self, name: str, url=None, status: int = 0):
        self._name = name
        self._url = url
        self._status = status

    def name(self):
        return self._name

    def URL(self):
        return self._url

    def participantStatus(self):
        return self._status


class MockDayOfWeek:
    def __init__(self, day: int, week_number: int = 0):
        self._day = day
        self._week_number = week_number

    def dayOfTheWeek(self):
        return self._day

    def weekNumber(self):
        return self._week_number


class MockRecurrenceEnd:
    def __init__(self, end_date=None, occurrence_count: int = 0):
        self._end_date = end_date
        self._occurrence_count = occurrence_count

    def endDate(self):
        return self._end_date

    def occurrenceCount(self):
        return self._occurrence_count


class MockNSNumber:
    def __init__(self, value: int):
        self._value = value

    def __int__(self):
        return self._value


class MockRecurrenceRule:
    def __init__(
        self,
        frequency: int = 0,
        interval: int = 1,
        days_of_week=None,
        days_of_month=None,
        months_of_year=None,
        set_positions=None,
        recurrence_end=None,
    ):
        self._frequency = frequency
        self._interval = interval
        self._days_of_week = days_of_week
        self._days_of_month = days_of_month
        self._months_of_year = months_of_year
        self._set_positions = set_positions
        self._recurrence_end = recurrence_end

    def frequency(self):
        return self._frequency

    def interval(self):
        return self._interval

    def daysOfTheWeek(self):
        return self._days_of_week

    def daysOfTheMonth(self):
        return self._days_of_month

    def monthsOfTheYear(self):
        return self._months_of_year

    def setPositions(self):
        return self._set_positions

    def recurrenceEnd(self):
        return self._recurrence_end
