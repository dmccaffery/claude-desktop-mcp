# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: Apache-2.0

"""Fake MCP server for validating Claude Desktop's handling of large toolsets.

Exposes 101+ themed "fake" tools in two selectable modes:

- ``full``   — ``tools/list`` returns all 101+ tools.
- ``search`` — ``tools/list`` returns only an AgentCore-style semantic search tool
  (``x_amz_bedrock_agentcore_search``); the rest stay hidden but remain callable.

See ``build_server`` for the entrypoint used by both the console script and tests.
"""

from claude_desktop_mcp.server import build_server

__all__ = ["build_server"]
