class AppleRemindersMcp < Formula
  desc "MCP server for Apple Reminders via EventKit"
  homepage "https://github.com/0xalexb/apple-reminders-mcp"
  url "https://github.com/0xalexb/apple-reminders-mcp/releases/download/v0.1.0/apple-reminders-mcp"
  sha256 "placeholder"
  license "MIT"

  depends_on :macos
  depends_on "uv"

  def install
    bin.install "apple-reminders-mcp"
  end

  test do
    assert_match "apple-reminders-mcp", shell_output("#{bin}/apple-reminders-mcp --version 2>&1")
  end
end

