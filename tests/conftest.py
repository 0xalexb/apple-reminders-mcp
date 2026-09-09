from __future__ import annotations


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
        self._alarms = alarms or []
        self._recurrence_rules = recurrence_rules or []
        self._attendees = attendees

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
        return False

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
