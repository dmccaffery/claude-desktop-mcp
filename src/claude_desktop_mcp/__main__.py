# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: MIT

"""Console-script / ``python -m claude_desktop_mcp`` entrypoint.

Runs the server over stdio — the transport Claude Desktop uses for local MCP servers.
The mode and other options come from environment variables (see :mod:`config`).
"""

from __future__ import annotations

from claude_desktop_mcp.server import build_server


def main() -> None:
    server = build_server()
    # stdio is the transport Claude Desktop spawns; suppress the banner so nothing
    # but JSON-RPC ever touches stdout.
    server.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
