# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: MIT

"""Fake MCP server for validating Claude Desktop's handling of large toolsets.

Exposes 101+ themed "fake" tools in two selectable modes:

- ``full``    — a plain large MCP server: ``tools/list`` returns all 101+ tools under
  their natural names, with no search tool.
- ``gateway`` — a faithful Amazon Bedrock AgentCore gateway: ``tools/list`` returns
  every tool (namespaced ``target___tool``) with the ``x_amz_bedrock_agentcore_search``
  tool listed first; the search tool returns matching definitions under
  ``structuredContent.tools``.

See ``build_server`` for the entrypoint used by both the console script and tests.
"""

from claude_desktop_mcp.server import build_server

__all__ = ["build_server"]
