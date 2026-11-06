from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import subprocess
import sys
from datetime import date
from unittest.mock import patch

import pytest

from apple_reminders_mcp import cli
from apple_reminders_mcp import server
from apple_reminders_mcp.server import (
    complete_reminder,
    create_list,
    create_reminder,
    delete_reminder,
    find_reminders,
    list_reminder_lists,
    move_reminder,
    quick_capture,
    show_all_incomplete_reminders,
    show_completed_reminders_today,
    show_incomplete_reminders,
    update_reminder,
)
from tests.mocks import MockCalendar, MockNSDate, MockReminder, MockSource


@pytest.fixture()
def cli_service(mock_service):
    with patch.object(cli, "EventKitService", return_value=mock_service):
        yield mock_service


def _run(capsys, *argv):
    rc = cli.main(list(argv))
    out, err = capsys.readouterr()
    return rc, out, err


def _reminder(**kwargs):
    defaults = {"title": "Fix drift", "identifier": "rem-7", "calendar": MockCalendar("Projects")}
    return MockReminder(**{**defaults, **kwargs})


_CASES = {
    "lists": (["lists"], "get_all_lists", []),
    "create-list": (["create-list", "--name", "Inbox"], "create_list", MockCalendar("Inbox")),
    "incomplete": (["incomplete", "--list-name", "Projects"], "get_incomplete_reminders", []),
    "all-incomplete": (["all-incomplete"], "get_all_incomplete_reminders", []),
    "completed-today": (["completed-today"], "get_completed_reminders_for_day", []),
    "complete": (["complete", "--reminder-id", "rem-7"], "complete_reminder", _reminder()),
    "delete": (["delete", "--reminder-id", "rem-7"], "delete_reminder", None),
    "move": (
        ["move", "--reminder-id", "rem-7", "--target-list-name", "Inbox"],
        "move_reminder",
        _reminder(),
    ),
    "quick-capture": (["quick-capture", "--title", "Idea"], "create_reminder", _reminder()),
    "find": (["find"], "find_reminders", []),
    "create": (["create", "--title", "Fix drift"], "create_reminder", _reminder()),
    "update": (["update", "rem-7", "--title", "x"], "update_reminder", _reminder()),
}

_VERB_TOOLS = {
    "lists": list_reminder_lists,
    "create-list": create_list,
    "incomplete": show_incomplete_reminders,
    "all-incomplete": show_all_incomplete_reminders,
    "completed-today": show_completed_reminders_today,
    "complete": complete_reminder,
    "delete": delete_reminder,
    "move": move_reminder,
    "quick-capture": quick_capture,
    "find": find_reminders,
    "create": create_reminder,
    "update": update_reminder,
}

_VERB_TOOL_NAMES = {
    "lists": "list_reminder_lists",
    "create-list": "create_list",
    "incomplete": "show_incomplete_reminders",
    "all-incomplete": "show_all_incomplete_reminders",
    "completed-today": "show_completed_reminders_today",
    "complete": "complete_reminder",
    "delete": "delete_reminder",
    "move": "move_reminder",
    "quick-capture": "quick_capture",
    "find": "find_reminders",
    "create": "create_reminder",
    "update": "update_reminder",
}


def _arm(service, verb):
    argv, method, value = _CASES[verb]
    getattr(service, method).return_value = value
    if verb == "lists":
        service.get_all_incomplete_reminders.return_value = []
    return argv, method


class TestJsonMatchesTools:
    def test_find(self, cli_service, capsys):
        cli_service.find_reminders.return_value = [_reminder(), _reminder(identifier="rem-8")]

        rc, out, _ = _run(capsys, "find", "--list", "Projects", "--query", "drift")

        assert rc == 0
        assert json.loads(out) == find_reminders(list_name="Projects", query="drift")
        cli_service.find_reminders.assert_any_call(
            list_name="Projects", list_id=None, query="drift"
        )

    def test_find_by_list_id(self, cli_service, capsys):
        cli_service.find_reminders.return_value = [_reminder()]

        rc, out, _ = _run(capsys, "find", "--list-id", "cal-1")

        assert rc == 0
        assert json.loads(out) == find_reminders(list_id="cal-1")
        cli_service.find_reminders.assert_any_call(list_name=None, list_id="cal-1", query=None)

    def test_find_empty_is_empty_array(self, cli_service, capsys):
        cli_service.find_reminders.return_value = []

        rc, out, _ = _run(capsys, "find", "--list", "Projects")

        assert (rc, json.loads(out)) == (0, [])

    def test_create(self, cli_service, capsys):
        cli_service.create_reminder.return_value = _reminder(notes="Ticket: u")

        rc, out, _ = _run(
            capsys, "create", "--list", "Projects", "--title", "Fix drift", "--notes", "Ticket: u"
        )

        assert rc == 0
        assert json.loads(out) == create_reminder("Fix drift", list_name="Projects", notes="Ticket: u")
        cli_service.create_reminder.assert_any_call(
            title="Fix drift",
            list_name="Projects",
            list_id=None,
            due_date=None,
            priority=0,
            recurrence=None,
            notes="Ticket: u",
            include_time=False,
        )

    def test_create_with_every_flag(self, cli_service, capsys):
        cli_service.create_reminder.return_value = _reminder()

        rc, out, _ = _run(
            capsys,
            "create",
            "--list-id",
            "cal-1",
            "--title",
            "Fix drift",
            "--due-date",
            "2026-03-15T10:30:00",
            "--priority",
            "high",
            "--recurrence",
            "weekly",
            "--notes",
            "n",
        )

        assert rc == 0
        assert json.loads(out) == create_reminder(
            "Fix drift",
            list_id="cal-1",
            due_date="2026-03-15T10:30:00",
            priority="high",
            recurrence="weekly",
            notes="n",
        )
        call = cli_service.create_reminder.call_args_list[0]
        assert call.kwargs["priority"] == 1
        assert call.kwargs["recurrence"] == "weekly"
        assert call.kwargs["include_time"] is True
        assert call.kwargs["due_date"].isoformat() == "2026-03-15T10:30:00"
        assert call.kwargs["list_id"] == "cal-1"

    def test_create_date_only_due_date_has_no_time(self, cli_service, capsys):
        cli_service.create_reminder.return_value = _reminder()

        rc, out, _ = _run(capsys, "create", "--title", "t", "--due-date", "2026-03-15")

        assert rc == 0
        assert json.loads(out) == create_reminder("t", due_date="2026-03-15")
        call = cli_service.create_reminder.call_args_list[0]
        assert call.kwargs["include_time"] is False
        assert call.kwargs["due_date"].date() == date(2026, 3, 15)

    def test_update_append_notes(self, cli_service, capsys):
        cli_service.update_reminder.return_value = _reminder(
            title="CCM-42 Fix drift", notes="n1\nTicket: u"
        )

        rc, out, _ = _run(
            capsys, "update", "rem-7", "--title", "CCM-42 Fix drift", "--append-notes", "Ticket: u"
        )

        assert rc == 0
        assert json.loads(out) == update_reminder(
            "rem-7", title="CCM-42 Fix drift", append_notes="Ticket: u"
        )
        cli_service.update_reminder.assert_any_call(
            "rem-7", title="CCM-42 Fix drift", notes=None, append_notes="Ticket: u"
        )

    def test_lists(self, cli_service, capsys):
        projects = MockCalendar("Projects", "cal-1", source=MockSource("iCloud", 2))
        twin = MockCalendar("Projects", "cal-2")
        cli_service.get_all_lists.return_value = [projects, twin]
        cli_service.get_all_incomplete_reminders.return_value = [_reminder(calendar=projects)]
        cli_service.calendar_color_hex.return_value = "#ff0000"

        rc, out, _ = _run(capsys, "lists")

        assert rc == 0
        assert json.loads(out) == list_reminder_lists()
        assert [row["id"] for row in json.loads(out)] == ["cal-1", "cal-2"]
        assert json.loads(out)[0]["color"] == "#ff0000"

    def test_create_list(self, cli_service, capsys):
        cli_service.create_list.return_value = MockCalendar("Inbox")

        rc, out, _ = _run(capsys, "create-list", "--name", "Inbox")

        assert rc == 0
        assert json.loads(out) == create_list("Inbox") == {"name": "Inbox", "created": True}
        cli_service.create_list.assert_any_call("Inbox")

    def test_incomplete_by_name(self, cli_service, capsys):
        cli_service.get_incomplete_reminders.return_value = [_reminder()]

        rc, out, _ = _run(capsys, "incomplete", "--list-name", "Projects")

        assert rc == 0
        assert json.loads(out) == show_incomplete_reminders(list_name="Projects")
        cli_service.get_incomplete_reminders.assert_any_call("Projects", None)

    def test_incomplete_by_id(self, cli_service, capsys):
        cli_service.get_incomplete_reminders.return_value = [_reminder()]

        rc, out, _ = _run(capsys, "incomplete", "--list-id", "cal-1")

        assert rc == 0
        assert json.loads(out) == show_incomplete_reminders(list_id="cal-1")
        cli_service.get_incomplete_reminders.assert_any_call(None, "cal-1")

    def test_all_incomplete_groups_and_keeps_unknown_bucket(self, cli_service, capsys):
        cli_service.get_all_incomplete_reminders.return_value = [
            _reminder(),
            _reminder(identifier="rem-8", calendar=None),
        ]

        rc, out, _ = _run(capsys, "all-incomplete")

        assert rc == 0
        assert json.loads(out) == show_all_incomplete_reminders()
        assert set(json.loads(out)) == {"Projects", "Unknown"}

    def test_all_incomplete_empty_is_empty_object(self, cli_service, capsys):
        cli_service.get_all_incomplete_reminders.return_value = []

        rc, out, _ = _run(capsys, "all-incomplete")

        assert (rc, json.loads(out)) == (0, {})

    def test_completed_today_with_day(self, cli_service, capsys):
        cli_service.get_completed_reminders_for_day.return_value = [
            _reminder(completion_date=MockNSDate(1773570600.0))
        ]

        rc, out, _ = _run(capsys, "completed-today", "--day", "2026-03-15")

        assert rc == 0
        assert json.loads(out) == show_completed_reminders_today("2026-03-15")
        assert "completion_date" in json.loads(out)[0]
        cli_service.get_completed_reminders_for_day.assert_any_call(date(2026, 3, 15))

    def test_completed_today_defaults_to_today(self, cli_service, capsys):
        cli_service.get_completed_reminders_for_day.return_value = []

        rc, out, _ = _run(capsys, "completed-today")

        assert (rc, json.loads(out)) == (0, [])
        cli_service.get_completed_reminders_for_day.assert_called_once_with(None)

    def test_complete(self, cli_service, capsys):
        cli_service.complete_reminder.return_value = _reminder()

        rc, out, _ = _run(capsys, "complete", "--reminder-id", "rem-7")

        assert rc == 0
        assert json.loads(out) == complete_reminder("rem-7") == {"id": "rem-7", "completed": True}
        cli_service.complete_reminder.assert_any_call("rem-7")

    def test_delete(self, cli_service, capsys):
        rc, out, _ = _run(capsys, "delete", "--reminder-id", "rem-7")

        assert rc == 0
        assert json.loads(out) == delete_reminder("rem-7") == {"id": "rem-7", "deleted": True}
        cli_service.delete_reminder.assert_any_call("rem-7")

    def test_move_by_name(self, cli_service, capsys):
        cli_service.move_reminder.return_value = _reminder()

        rc, out, _ = _run(
            capsys, "move", "--reminder-id", "rem-7", "--target-list-name", "Inbox"
        )

        assert rc == 0
        assert json.loads(out) == move_reminder("rem-7", target_list_name="Inbox")
        cli_service.move_reminder.assert_any_call("rem-7", "Inbox", None)

    def test_move_by_id(self, cli_service, capsys):
        cli_service.move_reminder.return_value = _reminder()

        rc, out, _ = _run(capsys, "move", "--reminder-id", "rem-7", "--target-list-id", "cal-9")

        assert rc == 0
        assert json.loads(out) == move_reminder("rem-7", target_list_id="cal-9")
        cli_service.move_reminder.assert_any_call("rem-7", None, "cal-9")

    def test_quick_capture_with_notes(self, cli_service, capsys):
        cli_service.create_reminder.return_value = _reminder(notes="n")

        rc, out, _ = _run(capsys, "quick-capture", "--title", "Idea", "--notes", "n")

        assert rc == 0
        assert json.loads(out) == quick_capture("Idea", notes="n")
        cli_service.create_reminder.assert_any_call(title="Idea", notes="n")

    def test_quick_capture_without_notes(self, cli_service, capsys):
        cli_service.create_reminder.return_value = _reminder()

        rc, out, _ = _run(capsys, "quick-capture", "--title", "Idea")

        assert rc == 0
        assert json.loads(out) == quick_capture("Idea")
        cli_service.create_reminder.assert_any_call(title="Idea", notes=None)


class TestStdout:
    @pytest.mark.parametrize("verb", list(_CASES))
    def test_one_json_line_and_quiet_stderr(self, cli_service, capsys, verb):
        argv, _ = _arm(cli_service, verb)

        rc, out, err = _run(capsys, *argv)

        assert rc == 0
        assert out.endswith("\n")
        assert out.count("\n") == 1
        json.loads(out)
        assert err == ""

    @pytest.mark.parametrize("verb", ["find", "incomplete", "completed-today", "lists"])
    def test_empty_list_result_is_an_array(self, cli_service, capsys, verb):
        argv, _ = _arm(cli_service, verb)

        _, out, _ = _run(capsys, *argv)

        assert out == "[]\n"

    def test_error_leaves_stdout_empty(self, cli_service, capsys):
        with patch.object(cli, "_run", return_value=object()):
            with pytest.raises(TypeError):
                cli.main(["lists"])

        assert capsys.readouterr().out == ""


class TestExitCodes:
    def test_notes_and_append_notes_are_exclusive(self, cli_service, capsys):
        with pytest.raises(SystemExit) as exc:
            cli.main(["update", "rem-7", "--notes", "a", "--append-notes", "b"])

        assert exc.value.code == 1
        cli_service.update_reminder.assert_not_called()

    def test_usage_error_is_1_not_2(self, cli_service, capsys):
        with pytest.raises(SystemExit) as exc:
            cli.main(["create"])

        assert exc.value.code == 1

    @pytest.mark.parametrize(
        "argv",
        [
            ["create-list"],
            ["complete"],
            ["delete"],
            ["move"],
            ["quick-capture"],
            ["create", "--list", "Projects"],
            ["update"],
        ],
    )
    def test_missing_required_flag_is_1(self, cli_service, capsys, argv):
        with pytest.raises(SystemExit) as exc:
            cli.main(argv)

        assert exc.value.code == 1

    def test_unknown_id_is_1(self, cli_service, capsys):
        cli_service.update_reminder.side_effect = ValueError("Reminder 'bad' not found")

        rc, out, err = _run(capsys, "update", "bad", "--title", "x")

        assert (rc, out) == (1, "")
        assert "not found" in err

    def test_unknown_list_is_1(self, cli_service, capsys):
        cli_service.find_reminders.side_effect = ValueError("List 'Missing' not found")

        rc, out, _ = _run(capsys, "find", "--list", "Missing")

        assert (rc, out) == (1, "")

    @pytest.mark.parametrize("verb", list(_CASES))
    @pytest.mark.parametrize("error", [PermissionError("denied"), TimeoutError("timed out")])
    def test_access_failure_at_init_is_2(self, capsys, verb, error):
        with patch.object(cli, "EventKitService", side_effect=error):
            rc, out, err = _run(capsys, *_CASES[verb][0])

        assert (rc, out) == (2, "")
        assert str(error) in err

    @pytest.mark.parametrize("verb", list(_CASES))
    def test_timeout_from_the_service_call_is_2(self, cli_service, capsys, verb):
        argv, method = _arm(cli_service, verb)
        getattr(cli_service, method).side_effect = TimeoutError("Timed out")

        rc, out, err = _run(capsys, *argv)

        assert (rc, out) == (2, "")
        assert "Timed out" in err

    @pytest.mark.parametrize("verb", list(_CASES))
    @pytest.mark.parametrize("error", [ValueError("bad input"), RuntimeError("EventKit failed")])
    def test_bad_input_and_failed_operation_are_1(self, cli_service, capsys, verb, error):
        argv, method = _arm(cli_service, verb)
        getattr(cli_service, method).side_effect = error

        rc, out, err = _run(capsys, *argv)

        assert (rc, out) == (1, "")
        assert str(error) in err

    def test_bad_day_is_1(self, cli_service, capsys):
        rc, out, err = _run(capsys, "completed-today", "--day", "not-a-date")

        assert (rc, out) == (1, "")
        assert "not-a-date" in err
        cli_service.get_completed_reminders_for_day.assert_not_called()

    def test_bad_due_date_is_1(self, cli_service, capsys):
        rc, out, _ = _run(capsys, "create", "--title", "t", "--due-date", "not-a-date")

        assert (rc, out) == (1, "")
        cli_service.create_reminder.assert_not_called()

    def test_bad_priority_is_1(self, cli_service, capsys):
        rc, out, err = _run(capsys, "create", "--title", "t", "--priority", "urgent")

        assert (rc, out) == (1, "")
        assert "Invalid priority 'urgent'" in err
        cli_service.create_reminder.assert_not_called()

    def test_service_rejected_recurrence_is_1(self, cli_service, capsys):
        cli_service.create_reminder.side_effect = ValueError("Invalid recurrence 'hourly'")

        rc, out, err = _run(capsys, "create", "--title", "t", "--recurrence", "hourly")

        assert (rc, out) == (1, "")
        assert "hourly" in err

    def test_incomplete_without_a_list_is_1(self, cli_service, capsys):
        cli_service.get_incomplete_reminders.side_effect = ValueError(
            "Provide list_name or list_id"
        )

        rc, out, err = _run(capsys, "incomplete")

        assert (rc, out) == (1, "")
        assert "Provide list_name or list_id" in err

    def test_find_needs_no_list(self, cli_service, capsys):
        cli_service.find_reminders.return_value = []

        rc, _, _ = _run(capsys, "find")

        assert rc == 0
        cli_service.find_reminders.assert_called_once_with(
            list_name=None, list_id=None, query=None
        )

    def test_create_needs_no_list(self, cli_service, capsys):
        cli_service.create_reminder.return_value = _reminder()

        rc, _, _ = _run(capsys, "create", "--title", "t")

        assert rc == 0
        cli_service.create_reminder.assert_called_once_with(
            title="t",
            list_name=None,
            list_id=None,
            due_date=None,
            priority=0,
            recurrence=None,
            notes=None,
            include_time=False,
        )


def _subparsers(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    return {}


def _options(parser):
    return {
        opt
        for action in parser._actions
        for opt in action.option_strings
        if opt not in ("-h", "--help")
    }


def _tool_names():
    tools = server.mcp.list_tools()
    if inspect.iscoroutine(tools):
        tools = asyncio.run(tools)
    return {tool.name for tool in tools}


class TestVerbContract:
    def test_verb_set_is_the_twelve_of_c5(self):
        verbs = set(_subparsers(cli._build_parser()))

        assert verbs == set(_VERB_TOOL_NAMES)
        assert "ping" not in verbs

    def test_every_tool_exists_on_the_server(self):
        assert set(_VERB_TOOL_NAMES.values()) <= _tool_names()

    def test_table_functions_are_the_named_tools(self):
        assert {v: fn.__name__ for v, fn in _VERB_TOOLS.items()} == _VERB_TOOL_NAMES

    @pytest.mark.parametrize("verb", list(_VERB_TOOLS))
    def test_flags_are_the_tool_parameters_in_kebab_case(self, verb):
        parser = _subparsers(cli._build_parser())[verb]
        params = set(inspect.signature(_VERB_TOOLS[verb]).parameters)
        expected = set()
        for param in params:
            if verb == "update" and param == "reminder_id":
                continue
            if verb in ("find", "create") and param == "list_name":
                expected.add("--list")
            else:
                expected.add("--" + param.replace("_", "-"))

        assert _options(parser) == expected

    def test_update_keeps_the_positional_id(self):
        parser = _subparsers(cli._build_parser())["update"]

        positionals = [a.dest for a in parser._actions if not a.option_strings and a.dest != "help"]
        assert positionals == ["reminder_id"]

    def test_kept_verbs_keep_their_flags(self):
        subs = _subparsers(cli._build_parser())

        assert {"--list", "--query"} <= _options(subs["find"])
        assert {"--list", "--title", "--notes"} <= _options(subs["create"])
        assert {"--title", "--notes", "--append-notes"} <= _options(subs["update"])

    def test_kept_verbs_leave_the_list_optional(self):
        subs = _subparsers(cli._build_parser())

        for verb in ("find", "create"):
            by_flag = {o: a for a in subs[verb]._actions for o in a.option_strings}
            assert by_flag["--list"].required is False
            assert by_flag["--list-id"].required is False


_FILE_TOKENS = {
    "file",
    "filename",
    "path",
    "dir",
    "directory",
    "attachment",
    "attachments",
    "import",
    "export",
    "output",
    "input",
}


def _walk(parser):
    yield parser
    for child in _subparsers(parser).values():
        yield from _walk(child)


def _file_violations(parser):
    found = []
    for p in _walk(parser):
        if p.fromfile_prefix_chars is not None:
            found.append(f"{p.prog}: fromfile_prefix_chars")
        for action in p._actions:
            for opt in action.option_strings:
                if _FILE_TOKENS & set(opt.lstrip("-").split("-")):
                    found.append(f"{p.prog}: {opt}")
            if isinstance(action.type, argparse.FileType):
                found.append(f"{p.prog}: {action.dest} type FileType")
            names = [action.dest, *(action.metavar if isinstance(action.metavar, tuple) else [action.metavar])]
            if any(n and ("file" in n.lower() or "path" in n.lower()) for n in names):
                found.append(f"{p.prog}: {action.dest} names a file")
    return found


class TestNoFileFlag:
    def test_no_verb_takes_a_file(self):
        assert _file_violations(cli._build_parser()) == []

    def test_walk_reaches_every_verb(self):
        assert len(list(_walk(cli._build_parser()))) == 1 + len(_VERB_TOOL_NAMES)

    def test_control_option_named_file(self):
        parser = argparse.ArgumentParser(prog="x")
        parser.add_argument("--notes-file")

        assert _file_violations(parser)

    def test_control_file_type(self):
        parser = argparse.ArgumentParser(prog="x")
        parser.add_argument("--notes", type=argparse.FileType("r"))

        assert _file_violations(parser)

    def test_control_fromfile_prefix(self):
        parser = argparse.ArgumentParser(prog="x", fromfile_prefix_chars="@")
        parser.add_argument("--notes")

        assert _file_violations(parser)

    def test_control_walk_descends_into_subparsers(self):
        parser = argparse.ArgumentParser(prog="x")
        sub = parser.add_subparsers(dest="command")
        sub.add_parser("deep").add_argument("--attachment")

        assert _file_violations(parser)


_ISOLATION = (
    "import sys, apple_reminders_mcp.cli{extra}; "
    "assert 'apple_reminders_mcp.server' not in sys.modules; "
    "assert 'mcp' not in sys.modules"
)


def test_cli_does_not_import_server():
    result = subprocess.run([sys.executable, "-c", _ISOLATION.format(extra="")])

    assert result.returncode == 0


def test_isolation_check_detects_server_import():
    result = subprocess.run(
        [sys.executable, "-c", _ISOLATION.format(extra=", apple_reminders_mcp.server")],
        capture_output=True,
    )

    assert result.returncode != 0
