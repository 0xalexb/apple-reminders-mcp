# Apple Reminders MCP Server

## Overview

Create a Python MCP server using FastMCP and pyobjc-framework-EventKit that exposes Apple Reminders operations as MCP tools. The server will support listing, creating, completing, deleting, and moving reminders, as well as managing reminder lists.

## Context

- Files involved: greenfield project, all files are new
- Related patterns: FastMCP decorator-based tool definitions, pyobjc EventKit framework bindings
- Dependencies: mcp (Python SDK), pyobjc-framework-EventKit, pytest (dev)

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- EventKit service layer is separated from MCP tool definitions for testability
- Tests mock the EventKit/pyobjc layer since it requires macOS and Reminders access
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/apple_reminders_mcp/__init__.py`
- Create: `src/apple_reminders_mcp/server.py` (minimal FastMCP skeleton)
- Create: `tests/__init__.py`

- [x] Create `pyproject.toml` with project metadata, dependencies (`mcp[cli]>=1.12`, `pyobjc-framework-EventKit`), dev dependencies (`pytest`), and entry point `apple-reminders-mcp = "apple_reminders_mcp.server:main"`
- [x] Create `src/apple_reminders_mcp/__init__.py` (empty)
- [x] Create `src/apple_reminders_mcp/server.py` with minimal FastMCP server that has a single placeholder tool and a `main()` function calling `mcp.run()`
- [x] Create `tests/__init__.py` (empty)
- [x] Write a smoke test that imports the server module successfully
- [x] Run project test suite - must pass before task 2

### Task 2: EventKit service layer

**Files:**
- Create: `src/apple_reminders_mcp/eventkit_service.py`
- Create: `tests/test_eventkit_service.py`

- [x] Implement `EventKitService` class with:
  - `__init__`: initialize `EKEventStore`, request access to reminders
  - `_request_access`: request and verify reminder access permission
  - `get_all_lists`: return all reminder lists (calendar objects of type reminder)
  - `get_list_by_name`: find a specific reminder list by name
  - `create_list`: create a new reminder list
  - `get_incomplete_reminders`: fetch incomplete reminders for a specific list
  - `get_all_incomplete_reminders`: fetch incomplete reminders across all lists
  - `create_reminder`: create a reminder with optional due date, priority, recurrence rule, and target list
  - `complete_reminder`: mark a reminder as completed
  - `delete_reminder`: delete a reminder
  - `move_reminder`: move a reminder to a different list
  - `_find_reminder_by_id`: helper to look up a reminder by its `calendarItemIdentifier`
- [x] Write tests with mocked EventKit objects covering each service method
- [x] Run project test suite - must pass before task 3

### Task 3: MCP tools - list and read operations

**Files:**
- Modify: `src/apple_reminders_mcp/server.py`
- Create: `tests/test_tools_read.py`

- [x] Add `list_reminder_lists` tool - returns all reminder list names and their reminder counts
- [x] Add `create_list` tool - creates a new reminder list, takes `name` parameter
- [x] Add `show_incomplete_reminders` tool - takes `list_name`, returns incomplete reminders with title, due date, priority, notes
- [x] Add `show_all_incomplete_reminders` tool - returns all incomplete reminders grouped by list
- [x] Write tests for each tool (mock the EventKitService)
- [x] Run project test suite - must pass before task 4

### Task 4: MCP tools - create, update, delete, and quick capture

**Files:**
- Modify: `src/apple_reminders_mcp/server.py`
- Create: `tests/test_tools_write.py`

- [x] Add `create_reminder` tool - takes `title`, optional `list_name` (defaults to default list), optional `due_date` (ISO 8601 string), optional `priority` (none/low/medium/high), optional `recurrence` (daily/weekly/monthly/yearly), optional `notes`
- [x] Add `complete_reminder` tool - takes `reminder_id`, marks it complete
- [x] Add `delete_reminder` tool - takes `reminder_id`, deletes the reminder
- [x] Add `move_reminder` tool - takes `reminder_id` and `target_list_name`
- [x] Add `quick_capture` tool - takes `title` and optional `notes`, creates reminder in default list with no date/priority (optimized for fast idea capture)
- [x] Write tests for each tool (mock the EventKitService)
- [x] Run project test suite - must pass before task 5

### Task 5: Verify acceptance criteria

- [x] Manual test: configure MCP server in Claude Code config and verify `list_reminder_lists` returns real data on macOS (skipped - requires macOS; verified all tools are properly wired)
- [x] Run full test suite (`uv run pytest`) - 80/80 passed
- [x] Run linter (`uv run ruff check src/ tests/`) - all checks passed
- [x] Verify test coverage meets 80%+ - 92% coverage

### Task 6: Update documentation

- [x] Update README.md with project description, installation instructions, MCP configuration example (for Claude Desktop and Claude Code), and list of available tools
- [x] Update CLAUDE.md if internal patterns changed
- [x] Move this plan to `docs/plans/completed/`
