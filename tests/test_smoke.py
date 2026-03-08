def test_import_server():
    from apple_reminders_mcp import server

    assert hasattr(server, "mcp")
    assert hasattr(server, "main")


def test_ping_tool():
    from apple_reminders_mcp.server import ping

    assert ping() == "pong"
