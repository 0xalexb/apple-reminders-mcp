class AppleRemindersMcp < Formula
  desc "MCP server for Apple Reminders via EventKit"
  homepage "https://github.com/0xalexb/apple-reminders-mcp"
  version "0.1.0"
  license "MIT"

  depends_on :macos
  depends_on "uv"

  def install
    (bin/"apple-reminders-mcp").write <<~EOS
      #!/bin/bash
      VERSION="#{version}"
      CACHE_MARKER="${HOME}/.cache/apple-reminders-mcp-version"

      # Clean old uvx cache if version changed
      if [ -f "$CACHE_MARKER" ]; then
          OLD_VERSION=$(cat "$CACHE_MARKER")
          if [ "$OLD_VERSION" != "$VERSION" ]; then
              uv cache prune --quiet 2>/dev/null
          fi
      fi
      mkdir -p "$(dirname "$CACHE_MARKER")"
      echo "$VERSION" > "$CACHE_MARKER"

      exec uvx --from "git+https://github.com/0xalexb/apple-reminders-mcp@v${VERSION}" apple-reminders-mcp "$@"
    EOS
  end

  test do
    assert_match "apple-reminders-mcp", shell_output("#{bin}/apple-reminders-mcp --version 2>&1")
  end
end

