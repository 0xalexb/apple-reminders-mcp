# Apple Reminders MCP Server

An MCP (Model Context Protocol) server that exposes Apple Reminders operations as tools, built with the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) and [pyobjc-framework-EventKit](https://pypi.org/project/pyobjc-framework-EventKit/).

> **Note:** This server requires macOS with access to Apple Reminders via EventKit.

## Installation

### Homebrew (Recommended)

```bash
brew install 0xalexb/tap/apple-reminders-mcp
```

### Using uvx (if you already have uv)

No installation needed — configure your MCP client to use uvx directly:

```json
{
  "mcpServers": {
    "apple-reminders": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/0xalexb/apple-reminders-mcp", "apple-reminders-mcp"]
    }
  }
}
```

### From source (development)

```bash
git clone https://github.com/0xalexb/apple-reminders-mcp.git
cd apple-reminders-mcp
uv sync
```

## MCP Configuration

### Claude Code

Add to your Claude Code MCP settings (`~/.claude/settings.json` or project `.mcp.json`):

```json
{
  "mcpServers": {
    "apple-reminders": {
      "command": "apple-reminders-mcp"
    }
  }
}
```

### Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "apple-reminders": {
      "command": "apple-reminders-mcp"
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `ping` | Health check - returns "pong" |
| `list_reminder_lists` | Returns every list's `id`, `name`, `incomplete_count`, `color`, `source_name`, `source_type`, `writable` and `is_subscribed` |
| `create_list` | Creates a new reminder list; returns `{name, created}` |
| `show_incomplete_reminders` | Returns incomplete reminders for a list, by `list_id` (preferred) or `list_name`, with the full reminder field set below |
| `show_all_incomplete_reminders` | Returns all incomplete reminders as an object keyed by list name, with the full reminder field set below |
| `show_completed_reminders_today` | Returns reminders completed on a given day (ISO `YYYY-MM-DD`, defaults to today), each carrying `completion_date` alongside the full reminder field set |
| `create_reminder` | Creates a reminder with optional list (`list_id` or `list_name`), due date (ISO 8601), priority (none/low/medium/high), recurrence (daily/weekly/monthly/yearly), and notes; returns the created reminder with the full field set below |
| `complete_reminder` | Marks a reminder as completed by its ID; returns `{id, completed}` |
| `delete_reminder` | Deletes a reminder by its ID; returns `{id, deleted}` |
| `move_reminder` | Moves a reminder to a different list, by `target_list_id` (preferred) or `target_list_name`; returns the moved reminder with the full field set below |
| `quick_capture` | Quickly captures a reminder in the default list with just a title and optional notes; returns the captured reminder with the full field set below |

## Returned fields

### Reminder

Every reminder returned by `show_incomplete_reminders`, `show_all_incomplete_reminders`,
`show_completed_reminders_today`, `create_reminder`, `move_reminder` and `quick_capture` carries
these keys, always present and `null` when unset:

| Key | Meaning |
|------|-------------|
| `id` | `calendarItemIdentifier` - local to this device, can change on sync |
| `title` | Reminder title |
| `due_date` | Floating wall-clock date (no UTC offset), date-only when no time is set - see [Date and time values](#date-and-time-values) |
| `priority` | `none`, `low`, `medium`, `high`, or `custom(N)` |
| `notes` | Plain-text notes |
| `list` | Name of the containing list |
| `list_id` | `calendarIdentifier` of the containing list |
| `is_completed` | Whether the reminder is done |
| `start_date` | Floating wall-clock date, same shape as `due_date` |
| `url` | Attached URL |
| `location` | Free-text location string |
| `created_at` | Absolute instant, ISO 8601 carrying the server's UTC offset |
| `last_modified_at` | Absolute instant, ISO 8601 carrying the server's UTC offset |
| `external_id` | `calendarItemExternalIdentifier` - stable across devices, shared by occurrences of a recurring item |
| `time_zone` | Time zone name; `null` means a floating date |

`show_completed_reminders_today` adds `completion_date`, an absolute instant. A timestamp outside
the range Python dates cover - `distantPast` is the unbounded sentinel a synced peer writes - comes
back as `null` rather than failing the call.

`show_all_incomplete_reminders` returns an object keyed by list **name**, with an `Unknown` bucket
for reminders whose list is missing. Two lists sharing a name share one bucket; the rows inside stay
separable by `list_id`.

Three collections are included **only when non-empty**, so bulk listings do not carry empty arrays:

- `alarms[]` - `absolute_date`, `relative_offset` (seconds, negative means before the due date;
  `null` for an absolute or geofenced alarm, where EventKit's `0.0` would be indistinguishable from
  a real zero offset), `proximity` (`none`/`enter`/`leave`) and, for a geofence, a nested `location`
  with `title` and `radius`.
- `recurrence[]` - `frequency` (`daily`/`weekly`/`monthly`/`yearly`), `interval`, `end_date` and
  `occurrence_count` always; plus `days_of_week` (each `{day, week_number}`, day 1 = Sunday),
  `days_of_month`, `months_of_year` and `set_positions` when the rule sets them.
- `attendees[]` - `name`, `url` and `status` (`unknown`, `pending`, `accepted`, `declined`,
  `tentative`, `delegated`, `completed`, `in_process`).

An EventKit enum value this server does not know reads back as `custom(N)` rather than `null`, so an
unrecognised value stays distinguishable from an unset one.

### Date and time values

Two different kinds of value share the ISO 8601 spelling, and they are not interchangeable.

**Absolute instants** - a fixed point on the timeline, emitted with the server's UTC offset
(`"2026-01-02T08:15:00+01:00"`):

- `created_at`, `last_modified_at`, `completion_date`
- `alarms[].absolute_date`
- `recurrence[].end_date`

**Floating wall-clock dates** - the values the Reminders UI shows, with no offset and often no time
at all (`"2026-03-15T10:30"`, `"2026-03-15"`):

- `due_date`, `start_date`

EventKit stores those two as date components rather than as an instant, deliberately: a reminder due
at 10:30 is still due at 10:30 after you fly somewhere else. Interpret them in the reminder's own
`time_zone` where it has one; `time_zone: null` means the value really is floating.

> **Warning:** the two kinds must not be compared directly. `datetime.fromisoformat` returns an
> offset-aware value for an instant and a naive one for a wall-clock date, and Python raises
> `TypeError: can't compare offset-naive and offset-aware datetimes` for any comparison between the
> two. Make the naive one aware first - `.replace(tzinfo=ZoneInfo(reminder["time_zone"]))`, or
> `.astimezone()` to read it as local time.

`completion_date` changed shape in this release: it previously came back with no UTC offset and now
carries one, in line with the other absolute instants. It is still ISO 8601 and still parses with
`datetime.fromisoformat`.

### List

`list_reminder_lists` returns one row per list with `id`, `name`, `incomplete_count`, `color`
(`#rrggbb`), `source_name` (the account the list lives in), `source_type` (`local`, `exchange`,
`caldav`, `mobileme`, `subscribed`, `birthdays` - iCloud accounts report as `caldav`), `writable`
and `is_subscribed`.

### Not exposed by EventKit

Subtasks and parent links, tags, the flagged bit, smart lists, sections and rich-text notes are
absent from the payloads above because EventKit does not surface them at all. They are a platform
limitation, not a gap in this server, and no amount of work here can reach them.

## List identifiers

Reminders permits two lists with the same name. A title is therefore not a key: a name-keyed lookup
picks whichever list it reaches first, with no signal that it had to choose, and reminders from both
lists look identical once returned.

Every list carries a `calendarIdentifier` that is unique and stable across renames. It is exposed as
`id` on `list_reminder_lists` and as `list_id` on every reminder, and the tools that take a list
accept `list_id` / `target_list_id` alongside the name. Where both are given, the id wins.

Prefer the id wherever one is available. `apple-calendar-mcp` has always worked this way; this brings
the two servers into line.

## Development

```bash
# Print the installed version
apple-reminders-mcp --version

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=apple_reminders_mcp

# Run linter
uv run ruff check src/ tests/
```

## Architecture

- `src/apple_reminders_mcp/server.py` - MCPServer with tool definitions
- `src/apple_reminders_mcp/eventkit_service.py` - EventKit service layer; macOS-only framework
  imports are confined to this file
- `tests/` - Test suite with mocked EventKit objects (runs on any platform)

## Uninstall

### Homebrew

```bash
brew uninstall apple-reminders-mcp
# Optional: remove the tap
brew untap 0xalexb/tap
```

### uvx

```bash
uv cache prune
```

## License

MIT
