# Apple Reminders MCP Server

An MCP (Model Context Protocol) server that exposes Apple Reminders operations as tools, built with [FastMCP](https://github.com/modelcontextprotocol/python-sdk) and [pyobjc-framework-EventKit](https://pypi.org/project/pyobjc-framework-EventKit/).

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
| `list_reminder_lists` | Returns all reminder list names and their incomplete reminder counts |
| `create_list` | Creates a new reminder list |
| `show_incomplete_reminders` | Returns incomplete reminders for a specific list with title, due date, priority, and notes |
| `show_all_incomplete_reminders` | Returns all incomplete reminders grouped by list |
| `create_reminder` | Creates a reminder with optional list, due date (ISO 8601), priority (none/low/medium/high), recurrence (daily/weekly/monthly/yearly), and notes |
| `complete_reminder` | Marks a reminder as completed by its ID |
| `delete_reminder` | Deletes a reminder by its ID |
| `move_reminder` | Moves a reminder to a different list |
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

- `src/apple_reminders_mcp/server.py` - FastMCP server with tool definitions
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
