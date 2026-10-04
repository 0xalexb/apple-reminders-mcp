from __future__ import annotations

import json
import subprocess
import sys
from unittest.mock import patch

import pytest

from apple_reminders_mcp import cli
from apple_reminders_mcp.server import create_reminder, find_reminders, update_reminder
from tests.mocks import MockCalendar, MockReminder


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


class TestJsonMatchesTools:
    def test_find(self, cli_service, capsys):
        cli_service.find_reminders.return_value = [_reminder(), _reminder(identifier="rem-8")]

        rc, out, _ = _run(capsys, "find", "--list", "Projects", "--query", "drift")

        assert rc == 0
        assert json.loads(out) == find_reminders(list_name="Projects", query="drift")
        cli_service.find_reminders.assert_any_call(list_name="Projects", query="drift")

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
            title="Fix drift", list_name="Projects", notes="Ticket: u"
        )

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


class TestExitCodes:
    def test_notes_and_append_notes_are_exclusive(self, cli_service, capsys):
        with pytest.raises(SystemExit) as exc:
            cli.main(["update", "rem-7", "--notes", "a", "--append-notes", "b"])

        assert exc.value.code == 1
        cli_service.update_reminder.assert_not_called()

    def test_usage_error_is_1_not_2(self, cli_service, capsys):
        with pytest.raises(SystemExit) as exc:
            cli.main(["find"])

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

    @pytest.mark.parametrize("error", [PermissionError("denied"), TimeoutError("timed out")])
    def test_access_failure_at_init_is_2(self, capsys, error):
        with patch.object(cli, "EventKitService", side_effect=error):
            rc, out, err = _run(capsys, "find", "--list", "Projects")

        assert (rc, out) == (2, "")
        assert str(error) in err

    def test_fetch_timeout_is_2(self, cli_service, capsys):
        cli_service.find_reminders.side_effect = TimeoutError("Timed out fetching reminders")

        rc, out, _ = _run(capsys, "find", "--list", "Projects")

        assert (rc, out) == (2, "")


_ISOLATION = "import sys, apple_reminders_mcp.cli{extra}; assert 'apple_reminders_mcp.server' not in sys.modules"


def test_cli_does_not_import_server():
    result = subprocess.run([sys.executable, "-c", _ISOLATION.format(extra="")])

    assert result.returncode == 0


def test_isolation_check_detects_server_import():
    result = subprocess.run(
        [sys.executable, "-c", _ISOLATION.format(extra=", apple_reminders_mcp.server")],
        capture_output=True,
    )

    assert result.returncode != 0
