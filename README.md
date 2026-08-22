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
| `list_reminder_lists` | Returns every list's `id`, name, and incomplete reminder count |
| `create_list` | Creates a new reminder list |
| `show_incomplete_reminders` | Returns incomplete reminders for a list, by `list_id` (preferred) or `list_name` |
| `show_all_incomplete_reminders` | Returns all incomplete reminders grouped by list |
| `create_reminder` | Creates a reminder with optional list (`list_id` or `list_name`), due date (ISO 8601), priority (none/low/medium/high), recurrence (daily/weekly/monthly/yearly), and notes |
| `complete_reminder` | Marks a reminder as completed by its ID |
| `delete_reminder` | Deletes a reminder by its ID |
| `move_reminder` | Moves a reminder to a different list, by `target_list_id` (preferred) or `target_list_name` |
| `quick_capture` | Quickly captures a reminder in the default list with just a title and optional notes |

## Development

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=apple_reminders_mcp

# Run linter
uv run ruff check src/ tests/
```

## Architecture

- `src/apple_reminders_mcp/server.py` - MCPServer with tool definitions
- `src/apple_reminders_mcp/eventkit_service.py` - EventKit service layer wrapping pyobjc calls
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

## List identifiers

Reminders permits two lists with the same name. A title is therefore not a key: a name-keyed lookup
picks whichever list it reaches first, with no signal that it had to choose, and reminders from both
lists look identical once returned.

Every list carries a `calendarIdentifier` that is unique and stable across renames. It is exposed as
`id` on `list_reminder_lists` and as `list_id` on every reminder, and the tools that take a list
accept `list_id` / `target_list_id` alongside the name. Where both are given, the id wins.

Prefer the id wherever one is available. `apple-calendar-mcp` has always worked this way; this brings
the two servers into line.
