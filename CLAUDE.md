# Apple Reminders MCP Server

## Build & Test Commands

- Install: `uv sync`
- Run tests: `uv run pytest`
- Run single test: `uv run pytest tests/test_file.py::test_name`
- Run tests with coverage: `uv run pytest --cov=apple_reminders_mcp`
- Lint: `uv run ruff check src/ tests/`
- Run server: `uv run apple-reminders-mcp`

## Architecture

- `src/apple_reminders_mcp/server.py` - FastMCP tool definitions, formatting helpers, lazy-init service
- `src/apple_reminders_mcp/eventkit_service.py` - EventKit wrapper; all pyobjc calls are isolated here
- Tests mock EventKit objects since pyobjc only works on macOS

## Conventions

- Python 3.11+, type hints via `from __future__ import annotations`
- Priority mapping: 0=none, 1=high, 5=medium, 9=low (Apple's EventKit values)
- Due dates use ISO 8601 format at the tool API level
- Recurrence mapping: "daily"=0, "weekly"=1, "monthly"=2, "yearly"=3 (EventKit EKRecurrenceFrequency values)
- Invalid inputs raise `ValueError`; failed EventKit operations raise `RuntimeError`; timeouts raise `TimeoutError`
- EventKitService is lazily initialized on first tool call via `_get_service()`
