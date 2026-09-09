# Expose all remaining EventKit reminder and list fields

## Overview

The server returns 7 fields per reminder (`id`, `title`, `due_date`, `priority`, `notes`, `list`,
`list_id`) and 3 per list. EventKit exposes considerably more, and some of what is missing is not
cosmetic: an alarm ("remind me at 09:00", or a geofence) is a separate object from the due date and
is currently invisible, so a reminder that fires tomorrow morning reads back as having no time at
all. Recurrence is worse than absent — it is write-only and lossy: `create_reminder` always writes
`interval=1` with no end, and nothing ever reads a rule back, so "every 2 weeks until June" reads as
no recurrence whatsoever.

This plan closes the read-side gap: every documented public field on `EKReminder`,
`EKCalendarItem` and `EKCalendar` that carries user data is surfaced through the existing tools,
except those named under "Deliberately excluded" in Technical Details.
No new tools, no changes to write paths.

Benefits: a client can round-trip a reminder's real state, sort by creation/modification date,
see why a write to a subscribed list will fail before attempting it, and distinguish two lists
named "Reminders" living in different accounts.

## Context (from discovery)

- **Files involved**: `src/apple_reminders_mcp/server.py` (tool definitions + `_format_*` helpers),
  `src/apple_reminders_mcp/eventkit_service.py` (pyobjc wrapper), `tests/test_tools_read.py`,
  `tests/test_tools_write.py`, `README.md`.
- **Existing pattern to copy**: `_PRIORITY_LABELS = {0: "none", 1: "high", 5: "medium", 9: "low"}`
  in `server.py:25` — a plain int-keyed dict, not an EventKit constant lookup. Every new enum map
  follows this shape.
- **Existing pattern to copy**: `_datetime_to_nsdate` in `eventkit_service.py` does a *function-local*
  `import Foundation`. Any macOS-only import added by this plan uses the same local-import form.
- **Dependencies actually installed** (re-derive with `uv pip list | grep -i pyobjc`):
  `pyobjc-core`, `pyobjc-framework-cocoa`, `pyobjc-framework-eventkit`. That is Foundation and
  AppKit — **not** Quartz, **not** CoreLocation. This constrains Tasks 2 and 5.
- **All selectors below were verified present** with
  `uv run python -c "import EventKit; print(hasattr(EventKit.EKReminder,'startDateComponents'))"`
  and equivalents. Re-derive the full sweep with the probe in "Technical Details".

## Development Approach

- **testing approach**: Regular (code first, then tests) — the shape of each formatter is settled by
  the EventKit API, so there is nothing for a test to discover first.
- complete each task fully before moving to the next
- make small, focused changes
- **every task MUST include new/updated tests** for the code it changes
- **all tests must pass before starting the next task** — `uv run pytest`
- **update this plan file when scope changes during implementation**
- maintain backward compatibility: no existing key is renamed or removed, only added

## Testing Strategy

- **unit tests**: required per task. This project has no e2e suite and no UI; unit tests over the
  `_format_*` helpers and the tool functions are the whole strategy.
- ⚠️ The mocks in `tests/` are **hand-written classes with explicit selectors**, not `MagicMock`.
  `MockReminder` in `test_tools_read.py:45` and the near-duplicate in `test_tools_write.py:64`
  define exactly the seven selectors used today. Adding a field to `_format_reminder` without
  adding the matching method to **both** mocks raises `AttributeError`, not `None` — and
  `test_tools_write.py` is affected too, because `create_reminder`, `move_reminder` and
  `quick_capture` all return `_format_reminder(...)`. Every task that touches `_format_reminder`
  must update both files in the same task.
- ⚠️ A second, larger trap the mocks hide: five existing tests assert **full dict equality**
  against today's 7-key reminder shape, and two more against the 3-key list row. Adding any key
  fails them. Reminder-shape assertions, all in `tests/test_tools_read.py`: L193
  (`TestFormatReminder.test_full_reminder`), L209 (`test_minimal_reminder`), L309
  (`TestShowIncompleteReminders.test_returns_formatted_reminders`), L336
  (`test_reminder_without_optional_fields`), L461
  (`TestShowCompletedRemindersToday.test_defaults_to_today`). List-row assertions: L249
  (`TestListReminderLists.test_returns_lists_with_counts`), L267 (`test_list_with_zero_reminders`).
  `TestListIdentifiers` and `tests/test_tools_write.py` assert key-by-key and survive — they need
  new mock selectors only, not assertion edits.
- **Migration policy for those seven**: extend the expected dict literal in place; do **not**
  loosen them to subset checks. Exact equality is what makes an accidentally added or renamed key
  fail loudly, and that property is worth more here than the edit cost.
- ⚠️ Editing existing tests requires asking first per the global rules. The confirmed batch is
  these four categories, all mechanical consequences of a contract change the maintainer asked
  for — proposed together rather than as one question per edit:
  1. extending the seven exact-equality literals named above;
  2. renaming the `_format_completion_date` import (`tests/test_tools_read.py:10`) and its two call
     sites inside `TestFormatCompletionDate` (L405, L410), which the clean rename in Task 1 forces;
  3. adding the new mock selectors to `MockReminder` in both `test_tools_read.py` and
     `test_tools_write.py`, and to `MockCalendar` in `test_tools_read.py`;
  4. stubbing `calendar_color_hex` on the `mock_service` fixture where Task 6 needs it.
  Any test edit outside those four — changing what an existing assertion *means*, deleting a test,
  loosening equality to a subset check — is out of scope and stops for its own question.
- The two `MockReminder` classes stay duplicated rather than being hoisted into a shared
  `conftest.py`: they already diverge (only the read one has `completionDate`), the duplication is
  pre-existing and local, and a shared fixture would couple the read and write suites for no gain.
  ⚠️ That rationale was sized for 6-7 methods each; Tasks 1-4 take both to roughly 18. Re-take the
  decision at the end of Task 4 rather than now: if the two classes are by then identical apart
  from `completionDate`, a shared base in `conftest.py` with a read-side subclass is the cheaper
  option and is in scope. If they have diverged further, leave them duplicated.

## Progress Tracking

- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix
- keep this plan in sync with the actual work

## Solution Overview

Formatting stays in `server.py`, next to the existing `_format_reminder` / `_format_due_date` /
`_format_ns_date` helpers (the last renamed from `_format_completion_date` in Task 1). Two hard constraints shape everything else:

1. **`server.py` must never import EventKit.** The test suite runs on any OS and only
   `eventkit_service.py` touches pyobjc. So every enum is a plain int-keyed dict in `server.py`,
   mirroring `_PRIORITY_LABELS`. The integer values are pinned from the framework itself (see
   Technical Details) rather than from memory.
2. **Anything needing a macOS-only *framework* goes in `eventkit_service.py`.** Exactly one field
   hits this: list colour, which needs `AppKit.NSColor`. It gets a service method with a
   function-local import, matching `_datetime_to_nsdate`.

Note on `CLAUDE.md`: it states "all pyobjc calls are isolated here [`eventkit_service.py`]". That
has not been true for some time — `server.py` already calls `reminder.title()`, `.priority()`,
`.calendar()` and `NSDate.timeIntervalSince1970()` directly. This plan follows the code as it
actually is rather than half-migrating, and Task 8 corrects the `CLAUDE.md` wording to describe the
real boundary: *framework imports* are isolated in the service; *selector calls on objects already
handed back* happen in either file.

**Payload shape.** Scalars are always present, including as explicit `null` — this matches how
`due_date` and `notes` already behave and keeps the JSON shape predictable for an LLM consumer.
Nested collections (`alarms`, `recurrence`, `attendees`) are emitted **only when non-empty**, so
`show_all_incomplete_reminders` across hundreds of reminders does not balloon with empty arrays.

The eight always-present scalars are the plan's largest token cost in bulk listings, so they are a
decision rather than a default: `created_at` / `last_modified_at` / `time_zone` earn their place
because sorting by recency and telling a floating date from a pinned one are exactly the queries
the bulk listing exists to answer, and both are impossible to reconstruct client-side.
`external_id` is kept despite duplicating `id`'s identity role — the two identifiers are not
interchangeable (`calendarItemIdentifier` is local to this device and can change on sync;
`calendarItemExternalIdentifier` is what survives across devices and can match several occurrences
of a recurring item), and a client reconciling against another store has no way to derive one from
the other.

## Technical Details

### Enum maps (values pinned from the framework, not from memory)

Re-derive all of them at any time with:

```sh
uv run python -c "
import EventKit as EK
print({n: getattr(EK, 'EKAlarmProximity'+n) for n in ('None','Enter','Leave')})
print({n: getattr(EK, 'EKRecurrenceFrequency'+n) for n in ('Daily','Weekly','Monthly','Yearly')})
print({n: getattr(EK, 'EKParticipantStatus'+n) for n in ('Unknown','Pending','Accepted','Declined','Tentative','Delegated','Completed','InProcess')})
print({n: getattr(EK, 'EKSourceType'+n) for n in ('Local','Exchange','CalDAV','MobileMe','Subscribed','Birthdays')})"
```

Current values:

- `EKAlarmProximity`: 0 none, 1 enter, 2 leave
- `EKRecurrenceFrequency`: 0 daily, 1 weekly, 2 monthly, 3 yearly (the inverse of the existing
  `EventKitService._RECURRENCE_MAP`)
- `EKParticipantStatus`: 0 unknown, 1 pending, 2 accepted, 3 declined, 4 tentative, 5 delegated,
  6 completed, 7 in_process
- `EKSourceType`: 0 local, 1 exchange, 2 caldav, 3 mobileme, 4 subscribed, 5 birthdays
  (iCloud accounts report as `caldav`)
- `EKRecurrenceDayOfWeek.dayOfTheWeek()`: 1 = Sunday … 7 = Saturday

### Field inventory

Reminder scalars, added to `_format_reminder`:

| Key | Selector | Notes |
|---|---|---|
| `is_completed` | `isCompleted()` | today, completion is only implied by which tool was called |
| `start_date` | `startDateComponents()` | reuse `_format_due_date`, same `NSDateComponents` shape |
| `url` | `URL()` | `NSURL` → `absoluteString()`; often `None` |
| `location` | `location()` | plain string |
| `created_at` | `creationDate()` | `NSDate` → reuse `_format_ns_date` |
| `last_modified_at` | `lastModifiedDate()` | `NSDate` |
| `external_id` | `calendarItemExternalIdentifier()` | stable across devices, unlike `calendarItemIdentifier` |
| `time_zone` | `timeZone()` | `NSTimeZone` → `name()`; `None` means a floating date |

Reminder collections (omitted when empty):

- `alarms[]`: `absolute_date`, `relative_offset` (seconds; negative = before due),
  `proximity`, `location` (`structuredLocation()` → `title()`, `radius()`)
- `recurrence[]`: `frequency`, `interval`, `days_of_week` (each `{day, week_number}`),
  `days_of_month`, `months_of_year`, `set_positions`, `end_date`, `occurrence_count`
- `attendees[]`: `name`, `url`, `status`

List fields, added to `list_reminder_lists` rows: `color`, `source_name`, `source_type`,
`writable`, `is_subscribed`.

**Deliberately excluded**: `attachments()` (present on the class, effectively unused for reminders
on macOS); `displayOrder` and `isAllDay` (exist on `EKReminder` but are undocumented private API);
`EKRecurrenceRule.weeksOfTheYear()` and `daysOfTheYear()` (real public API, but the Reminders UI
offers no way to author either, so a rule carrying them cannot originate from this data source —
add them if a CalDAV-synced rule is ever observed using them).
**Not in EventKit at all**, so not reachable by any amount of work here: subtasks/parent links,
tags, the flagged bit, smart lists, sections, rich-text notes.

## What Goes Where

- **Implementation Steps**: all code, tests and docs — everything is inside this repo.
- **Post-Completion**: verification against a real Reminders database, which needs a Mac with
  granted TCC permission and cannot be done from the test suite.

## Implementation Steps

### Task 1: Add scalar reminder fields to `_format_reminder`

**Files:**
- Modify: `src/apple_reminders_mcp/server.py`
- Modify: `tests/test_tools_read.py`
- Modify: `tests/test_tools_write.py`

- [x] rename `_format_completion_date` to `_format_ns_date` outright — no back-compat alias, it is
      a private helper with exactly one caller (`_format_completed_reminder`, `server.py:74`) and
      one test import (`tests/test_tools_read.py:10`); update both. `TestFormatCompletionDate`
      keeps working once its calls are renamed
- [x] add `_format_url(ns_url)` returning `absoluteString()` or `None`
- [x] add `_format_time_zone(ns_tz)` returning `name()` or `None`
- [x] extend `_format_reminder` with `is_completed`, `start_date`, `url`, `location`, `created_at`,
      `last_modified_at`, `external_id`, `time_zone` — each guarded against `None`
- [x] ⚠️ add the eight matching methods to `MockReminder` in **both** `tests/test_tools_read.py` and
      `tests/test_tools_write.py`, defaulting to `None`, or the whole suite fails with
      `AttributeError`
- [x] ⚠️ make `isCompleted()` return `self._completion_date is not None` in the
      `test_tools_read.py` mock, not a flat `False`. A flat default would have
      `test_defaults_to_today` assert `is_completed: False` alongside a non-null `completion_date`
      — a state EventKit cannot produce. The `test_tools_write.py` mock has no completion date, so
      a flat `False` is correct there
- [x] write tests: a fully-populated reminder emits all eight keys with correct values
- [x] write tests: a bare reminder emits all eight keys as `None`/`False` rather than omitting them
- [x] write a test asserting `start_date` returns `None` for `NSDateComponents` carrying the
      `2**63-1` unset sentinel, the same guard `_format_due_date` already applies
- [x] ⚠️ extend the five existing exact-equality dict literals to the new 15-key shape — 16 keys in
      `test_defaults_to_today`, which goes through `_format_completed_reminder` and so also carries
      `completion_date`. Find them by test name, not line number, since editing the earlier ones
      shifts the later ones: `test_full_reminder`, `test_minimal_reminder`,
      `test_returns_formatted_reminders`, `test_reminder_without_optional_fields`,
      `test_defaults_to_today` — all in `tests/test_tools_read.py`. Keep them exact-equality (see
      Testing Strategy); they are the only assertions that break in this task
- [x] verify: `uv run pytest` passes and `_format_reminder` returns exactly 15 keys —
      `uv run pytest tests/test_tools_read.py -k FormatReminder -q`

### Task 2: Add alarm formatting

**Files:**
- Modify: `src/apple_reminders_mcp/server.py`
- Modify: `tests/test_tools_read.py`
- Modify: `tests/test_tools_write.py`

- [x] add `_ALARM_PROXIMITY_LABELS = {0: "none", 1: "enter", 2: "leave"}`
- [x] add `_format_alarm(alarm)` returning `absolute_date` (`absoluteDate()` is an `NSDate` — use
      `_format_ns_date` from Task 1, not `_format_due_date`), `relative_offset`, `proximity`, and a
      nested `location` (`title`, `radius`) when `structuredLocation()` is not `None`
- [x] ⚠️ do **not** read `geoLocation()` coordinates: `CoreLocation` is not an installed dependency
      (`uv pip list | grep -i pyobjc` shows only core, cocoa, eventkit), so pyobjc has no metadata to
      decode the returned `CLLocationCoordinate2D` struct. The location `title` and `radius` are the
      useful parts; adding `pyobjc-framework-CoreLocation` for a lat/lon pair is a separate decision
- [x] wire `alarms` into `_format_reminder`, present only when `alarms()` is non-empty
- [x] add `alarms()` returning `[]` to `MockReminder` in both test files
- [x] write tests for a time alarm (absolute), an offset alarm (negative `relative_offset`), and a
      geofence alarm (proximity + structured location)
- [x] write tests: no alarms → the `alarms` key is absent from the dict entirely
- [x] verify: `uv run pytest -q` passes and `"alarms" not in _format_reminder(bare_reminder)`

### Task 3: Add recurrence rule read-back

**Files:**
- Modify: `src/apple_reminders_mcp/server.py`
- Modify: `tests/test_tools_read.py`
- Modify: `tests/test_tools_write.py`

- [ ] add `_RECURRENCE_FREQUENCY_LABELS = {0: "daily", 1: "weekly", 2: "monthly", 3: "yearly"}`
- [ ] add `_format_recurrence_rule(rule)`. Selectors are non-obvious here, so they are named
      explicitly — `frequency()`, `interval()`, `daysOfTheWeek()`, `daysOfTheMonth()`,
      `monthsOfTheYear()`, `setPositions()`, `recurrenceEnd()`. There is no `daysOfWeek()`;
      guessing the short forms yields `AttributeError`
- [ ] map each `daysOfTheWeek()` entry (`EKRecurrenceDayOfWeek`) to
      `{"day": dayOfTheWeek(), "week_number": weekNumber() or None}` — dropping `weekNumber()`
      would read "first Monday of every month" back as plain "Monday", which is the same class of
      lossiness this task exists to fix. `weekNumber()` is `0` when unset; emit `None`
- [ ] include `set_positions` from `setPositions()` for the same reason
- [ ] ⚠️ `daysOfTheMonth()`, `monthsOfTheYear()` and `setPositions()` return `NSNumber` arrays —
      coerce with `int()` so the JSON payload carries plain integers
- [ ] emit `end_date` (via `_format_ns_date` — `EKRecurrenceEnd.endDate()` is an `NSDate`, not
      `NSDateComponents`) and `occurrence_count` from `recurrenceEnd()`
- [ ] ⚠️ `recurrenceEnd()` is `None` for an open-ended rule, and when present exactly one of
      `endDate()` / `occurrenceCount()` is meaningful — `occurrenceCount()` is `0` for a date-bounded
      rule. Emit `None` for the one that does not apply rather than `0`
- [ ] wire `recurrence` into `_format_reminder`, present only when `recurrenceRules()` is non-empty
- [ ] add `recurrenceRules()` returning `[]` to `MockReminder` in both test files
- [ ] write tests: simple daily rule; "every 2 weeks on Mon/Wed"; "first Monday of every month"
      (asserting `week_number == 1`); rule ending on a date; rule ending after N occurrences
- [ ] write tests: no rules → the `recurrence` key is absent
- [ ] verify: `uv run pytest -q` passes and a mocked `interval=2` rule round-trips as `2`, proving
      the old always-1 lossiness is gone on the read side

### Task 4: Add attendee formatting

**Files:**
- Modify: `src/apple_reminders_mcp/server.py`
- Modify: `tests/test_tools_read.py`
- Modify: `tests/test_tools_write.py`

- [ ] add `_PARTICIPANT_STATUS_LABELS` for values 0–7 per the table in Technical Details
- [ ] add `_format_attendee(participant)` returning `name`, `url` (via `_format_url`) and `status`
      — the selector is `participantStatus()`, not `status()`; `status` is the output key only
- [ ] wire `attendees` into `_format_reminder`, present only when `attendees()` is non-empty
- [ ] ⚠️ `attendees()` returns `None`, not `[]`, on a reminder that has never been shared — guard on
      falsiness, not on `len()`
- [ ] ⚠️ Why this survives the exclusion rule applied to `weeksOfTheYear()`: that rule turns on
      whether the Reminders UI can author the value, and Reminders *does* author per-item
      assignment — "Assign Reminder" on a shared list, distinct from sharing the list itself. What
      is unverified is whether EventKit surfaces an assignee as an `EKParticipant`; Apple documents
      `attendees` primarily for events. Implement it, and if the manual check in Post-Completion
      finds a real assigned reminder reporting no attendees, delete this task's code rather than
      leaving a formatter that can never fire
- [ ] add `attendees()` returning `None` to `MockReminder` in both test files
- [ ] write tests: two attendees with differing statuses; `None` attendees → key absent
- [ ] verify: `uv run pytest -q` passes and `"attendees" not in _format_reminder(bare_reminder)`

### Task 5: Add list colour to the service layer

**Files:**
- Modify: `src/apple_reminders_mcp/eventkit_service.py`
- Modify: `tests/test_eventkit_service.py`

- [ ] add `EventKitService.calendar_color_hex(calendar)` returning `"#rrggbb"` or `None`
- [ ] implement with a **function-local** `import AppKit` (matching `_datetime_to_nsdate`'s local
      `import Foundation`): `calendar.color()`, then
      `colorUsingColorSpace_(AppKit.NSColorSpace.sRGBColorSpace())`, then `redComponent()`,
      `greenComponent()` and `blueComponent()` scaled to 0–255
- [ ] ⚠️ this method must live in the service, not `server.py`: it is the one new field needing a
      macOS-only framework import, and `server.py` must stay importable on any OS
- [ ] ⚠️ `colorUsingColorSpace_` returns `None` for a colour that cannot be converted — return
      `None` rather than raising
- [ ] write tests with a fake AppKit module injected, covering a normal colour, a `color()` of
      `None`, and a failed colourspace conversion
- [ ] verify: `uv run pytest tests/test_eventkit_service.py -q` passes and a mocked (1.0, 0.0, 0.5)
      colour yields exactly `"#ff0080"`

### Task 6: Add list metadata to `list_reminder_lists`

**Files:**
- Modify: `src/apple_reminders_mcp/server.py`
- Modify: `tests/test_tools_read.py`

- [ ] add `_SOURCE_TYPE_LABELS = {0: "local", 1: "exchange", 2: "caldav", 3: "mobileme",
      4: "subscribed", 5: "birthdays"}`
- [ ] extend the `list_reminder_lists` rows with `color` (via `service.calendar_color_hex(cal)`),
      `source_name`, `source_type`, `writable` (`allowsContentModifications()`) and
      `is_subscribed` (`isSubscribed()`)
- [ ] ⚠️ `source()` can be `None` — emit `None` for both source keys rather than raising
- [ ] add `source()`, `allowsContentModifications()`, `isSubscribed()` to `MockCalendar` in
      `tests/test_tools_read.py`; leave the `MockCalendar` copies in the other two test files alone,
      since neither exercises `list_reminder_lists`
- [ ] ⚠️ stub `mock_service.calendar_color_hex.return_value` in every affected test. The
      `mock_service` fixture (`tests/test_tools_read.py:118`) is a bare `MagicMock`, so an unstubbed
      call puts a non-serialisable `MagicMock` in the `color` field while a key-count assertion
      still passes
- [ ] ⚠️ extend the two existing exact-equality list-row literals to the new 8-key shape — by test
      name, not line: `test_returns_lists_with_counts` and `test_list_with_zero_reminders`, both in
      `TestListReminderLists`. `TestListIdentifiers` asserts key-by-key and needs no change
- [ ] write tests: a writable iCloud list, a read-only subscribed list, and a list whose `source()`
      is `None`
- [ ] verify: `uv run pytest tests/test_tools_read.py -k ListReminderLists -q` passes, each row has
      exactly 8 keys, and a stubbed colour arrives as `row["color"] == "#ff0080"` rather than a
      `MagicMock`

### Task 7: Verify acceptance criteria

- [ ] verify every field in the Technical Details inventory appears in the output of the read tools
- [ ] verify no pre-existing key was renamed or dropped: `id`, `title`, `due_date`, `priority`,
      `notes`, `list`, `list_id`, `completion_date` all still present with unchanged semantics
- [ ] verify `server.py` still has no EventKit import: `grep -n "import EventKit" src/apple_reminders_mcp/server.py`
      must produce no output
- [ ] verify the empty-collection rule holds: a bare reminder's dict contains none of `alarms`,
      `recurrence`, `attendees`
- [ ] run the full suite: `uv run pytest`
- [ ] verify coverage did not regress against the pre-change baseline measured with
      `uv run pytest --cov=apple_reminders_mcp -q` on 2026-09-09: **109 passed, TOTAL 91%**
      (`server.py` 92%, `eventkit_service.py` 90%). Re-run the same command and compare

### Task 8: Update documentation

- [ ] update the README "Available Tools" table (`README.md:70-81`): the **two** existing `show_*`
      rows and `list_reminder_lists` describe the fields they now return
- [ ] ➕ add the missing `show_completed_reminders_today` row — the tool exists in `server.py` but
      was never listed in the table
- [ ] add a short "Returned fields" section to the README listing reminder and list keys, and
      naming what EventKit does not expose (subtasks, tags, flagged, sections) so the omission
      reads as a platform limit rather than a gap
- [ ] correct the `CLAUDE.md` Architecture line that claims all pyobjc calls are isolated in
      `eventkit_service.py` — state that macOS-only *framework imports* are isolated there, while
      selector calls on returned objects happen in both files
- [ ] add the enum maps to the `CLAUDE.md` Conventions list alongside the existing priority and
      recurrence mappings
- [ ] verify: `grep -c "alarms" README.md` returns at least 1
- [ ] move this plan to `docs/plans/completed/`

## Post-Completion

*Informational — needs a Mac with granted Reminders permission, out of reach of the test suite.*

**Manual verification**: run the server against a real Reminders database and confirm against the
Reminders app — an assigned reminder on a shared list reports attendees (if it does not, Task 4's
formatter is dead code and should be deleted); a reminder with a 09:00 alert reports an alarm; a geofenced reminder reports its
location title and radius; an "every 2 weeks" reminder reports `interval: 2`; a subscribed list
reports `writable: false`; two same-named lists in different accounts are separable by
`source_name`.

**Follow-up work, deliberately out of scope here** — this plan is read-side only, which leaves an
asymmetry worth closing next: the write path cannot set `url`, `location`, `start_date` or alarms;
recurrence can only be written as `interval=1` with no end date and no weekday selection; and there
is no `update_reminder` tool at all, so title, notes, due date and priority are effectively
write-once.
