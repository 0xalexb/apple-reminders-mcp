# Apple Reminders MCP Server

## Build & Test Commands

- Install: `uv sync`
- Run tests: `uv run pytest`
- Run single test: `uv run pytest tests/test_file.py::test_name`
- Run tests with coverage: `uv run pytest --cov=apple_reminders_mcp`
- Lint: `uv run ruff check src/ tests/`
- Run server: `uv run apple-reminders-mcp`

## Architecture

- `src/apple_reminders_mcp/server.py` - MCPServer tool definitions, formatting helpers, lazy-init service
- `src/apple_reminders_mcp/eventkit_service.py` - EventKit wrapper; the macOS-only framework imports (EventKit, AppKit, Foundation) are isolated here and are all function-local
- Selector calls on objects the service hands back (`reminder.title()`, `cal.source()`, `ns_date.timeIntervalSince1970()`) happen in both files; `server.py` must stay importable off macOS, so it never imports a framework and maps EventKit enums with plain int-keyed dicts
- Tests mock EventKit objects since pyobjc only works on macOS. The shared mocks live in `tests/mocks.py` (`MockReminder`, `MockCalendar`, `MockNSDate`, …), `tests/conftest.py` holds only the `mock_service` fixture, and `tests/test_eventkit_service.py` keeps its own write-side mocks
- ⚠️ The mocks are hand-written classes with explicit selectors, not `MagicMock`: adding a field to `_format_reminder` without adding the selector to `tests/mocks.py` raises `AttributeError`, not `None`. Several tests assert full dict equality, so any new key fails them too — extend the literals rather than loosening the assertions
- `mock_service` is `create_autospec(EventKitService)`, so a renamed or re-signatured service method fails the tool tests instead of passing silently

## Conventions

- Python 3.11+, type hints via `from __future__ import annotations`
- Priority mapping: 0=none, 1=high, 5=medium, 9=low (Apple's EventKit values)
- Due dates use ISO 8601 format at the tool API level
- Two kinds of date, never unified: `_format_due_date` renders EventKit date components as a floating wall-clock string (no offset, date-only when no time is set) for `due_date` and `start_date`; `_format_ns_date` renders an `NSDate` as an absolute instant carrying the local UTC offset for `created_at`, `last_modified_at`, `completion_date`, `alarms[].absolute_date` and `recurrence[].end_date`
- Ordering or subtracting the two kinds raises `TypeError`, but `==` does not - it silently returns `False` for every instant/wall-clock pair. Never document the comparison hazard as "any comparison raises"; the silent equality case is the one consumers get wrong
- `time_zone` is `NSTimeZone.name()`, which is an IANA key only when the zone came from a region; a zone built from an offset (as `_make_date_components` does for a due date carrying one) names itself `GMT`, `GMT+0200` or `GMT-0500`. Bare `GMT` is a tzdata entry and `ZoneInfo` resolves it; only the signed forms raise `ZoneInfoNotFoundError`. The README's "Date and time values" section carries the recipe, and its sign convention is Foundation's, inverted from tzdata's `Etc/GMT+2`
- Recurrence mapping: "daily"=0, "weekly"=1, "monthly"=2, "yearly"=3 (EventKit EKRecurrenceFrequency values)
- Alarm proximity mapping: 0=none, 1=enter, 2=leave (EKAlarmProximity)
- Participant status mapping: 0=unknown, 1=pending, 2=accepted, 3=declined, 4=tentative, 5=delegated, 6=completed, 7=in_process (EKParticipantStatus)
- Source type mapping: 0=local, 1=exchange, 2=caldav, 3=mobileme, 4=subscribed, 5=birthdays (EKSourceType); iCloud accounts report as caldav
- Reminder payloads: scalars are always present (explicitly `null` when unset); the `alarms`, `recurrence` and `attendees` collections are emitted only when non-empty
- Enum lookups go through `_format_enum`, which falls back to `custom(N)` — an unmapped EventKit value never reads back as `null`
- `NSDate` values outside `datetime`'s range (`distantPast`, and whatever a CalDAV peer writes) format as `null`, never an exception; timestamps carry the local UTC offset
- Invalid inputs raise `ValueError`; failed EventKit operations raise `RuntimeError`; timeouts raise `TimeoutError`
- EventKitService is lazily initialized on first tool call via `_get_service()`
