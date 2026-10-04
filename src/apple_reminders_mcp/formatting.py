from __future__ import annotations

from datetime import datetime


_PRIORITY_LABELS = {0: "none", 1: "high", 5: "medium", 9: "low"}
_ALARM_PROXIMITY_LABELS = {0: "none", 1: "enter", 2: "leave"}
_RECURRENCE_FREQUENCY_LABELS = {0: "daily", 1: "weekly", 2: "monthly", 3: "yearly"}
_PARTICIPANT_STATUS_LABELS = {
    0: "unknown",
    1: "pending",
    2: "accepted",
    3: "declined",
    4: "tentative",
    5: "delegated",
    6: "completed",
    7: "in_process",
}
_SOURCE_TYPE_LABELS = {
    0: "local",
    1: "exchange",
    2: "caldav",
    3: "mobileme",
    4: "subscribed",
    5: "birthdays",
}


_UNSET_COMPONENT = 2**63 - 1


def _format_enum(value: int, labels: dict[int, str]) -> str:
    return labels.get(value, f"custom({value})")


def _format_priority(priority: int) -> str:
    return _format_enum(priority, _PRIORITY_LABELS)


def _format_alarm_proximity(proximity: int) -> str:
    return _format_enum(proximity, _ALARM_PROXIMITY_LABELS)


def _format_recurrence_frequency(frequency: int) -> str:
    return _format_enum(frequency, _RECURRENCE_FREQUENCY_LABELS)


def _format_participant_status(status: int) -> str:
    return _format_enum(status, _PARTICIPANT_STATUS_LABELS)


def _format_source_type(source_type: int) -> str:
    return _format_enum(source_type, _SOURCE_TYPE_LABELS)


def _format_due_date(components) -> str | None:
    if components is None:
        return None
    year = components.year()
    month = components.month()
    day = components.day()
    hour = components.hour()
    minute = components.minute()
    if year > 9999 or month == _UNSET_COMPONENT or day == _UNSET_COMPONENT:
        return None
    date_str = f"{year:04d}-{month:02d}-{day:02d}"
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{date_str}T{hour:02d}:{minute:02d}"
    return date_str


def _format_url(ns_url) -> str | None:
    if ns_url is None:
        return None
    return ns_url.absoluteString()


def _format_ns_date(ns_date) -> str | None:
    if ns_date is None:
        return None
    try:
        timestamp = ns_date.timeIntervalSince1970()
        return datetime.fromtimestamp(timestamp).astimezone().isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def _format_alarm(alarm) -> dict:
    absolute = alarm.absoluteDate()
    structured = alarm.structuredLocation()
    data = {
        "absolute_date": _format_ns_date(absolute),
        "relative_offset": (
            None
            if absolute is not None or structured is not None
            else alarm.relativeOffset()
        ),
        "proximity": _format_alarm_proximity(alarm.proximity()),
    }
    if structured is not None:
        data["location"] = {
            "title": structured.title(),
            "radius": structured.radius(),
        }
    return data


def _format_recurrence_rule(rule) -> dict:
    data = {
        "frequency": _format_recurrence_frequency(rule.frequency()),
        "interval": rule.interval(),
    }
    days_of_week = rule.daysOfTheWeek()
    if days_of_week:
        data["days_of_week"] = [
            {"day": day.dayOfTheWeek(), "week_number": day.weekNumber() or None}
            for day in days_of_week
        ]
    days_of_month = rule.daysOfTheMonth()
    if days_of_month:
        data["days_of_month"] = [int(value) for value in days_of_month]
    months_of_year = rule.monthsOfTheYear()
    if months_of_year:
        data["months_of_year"] = [int(value) for value in months_of_year]
    set_positions = rule.setPositions()
    if set_positions:
        data["set_positions"] = [int(value) for value in set_positions]
    end = rule.recurrenceEnd()
    if end is not None:
        data["end_date"] = _format_ns_date(end.endDate())
        data["occurrence_count"] = end.occurrenceCount() or None
    else:
        data["end_date"] = None
        data["occurrence_count"] = None
    return data


def _format_attendee(participant) -> dict:
    return {
        "name": participant.name(),
        "url": _format_url(participant.URL()),
        "status": _format_participant_status(participant.participantStatus()),
    }


def _format_reminder(reminder) -> dict:
    time_zone = reminder.timeZone()
    data = {
        "id": reminder.calendarItemIdentifier(),
        "title": reminder.title(),
        "due_date": _format_due_date(reminder.dueDateComponents()),
        "priority": _format_priority(reminder.priority()),
        "notes": reminder.notes(),
        "list": reminder.calendar().title() if reminder.calendar() else None,
        "list_id": (
            reminder.calendar().calendarIdentifier() if reminder.calendar() else None
        ),
        "is_completed": reminder.isCompleted(),
        "start_date": _format_due_date(reminder.startDateComponents()),
        "url": _format_url(reminder.URL()),
        "location": reminder.location(),
        "created_at": _format_ns_date(reminder.creationDate()),
        "last_modified_at": _format_ns_date(reminder.lastModifiedDate()),
        "external_id": reminder.calendarItemExternalIdentifier(),
        "time_zone": time_zone.name() if time_zone is not None else None,
    }
    alarms = reminder.alarms()
    if alarms:
        data["alarms"] = [_format_alarm(alarm) for alarm in alarms]
    rules = reminder.recurrenceRules()
    if rules:
        data["recurrence"] = [_format_recurrence_rule(rule) for rule in rules]
    attendees = reminder.attendees()
    if attendees:
        data["attendees"] = [_format_attendee(attendee) for attendee in attendees]
    return data


def _format_completed_reminder(reminder) -> dict:
    data = _format_reminder(reminder)
    data["completion_date"] = _format_ns_date(reminder.completionDate())
    return data
