from __future__ import annotations

from unittest.mock import create_autospec, patch

import pytest

from apple_reminders_mcp.eventkit_service import EventKitService


@pytest.fixture()
def mock_service():
    service = create_autospec(EventKitService, instance=True)
    service.calendar_color_hex.return_value = None
    with patch(
        "apple_reminders_mcp.server._get_service", return_value=service
    ):
        yield service
