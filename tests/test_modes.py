# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: MIT

"""The two modes, exercised through the real MCP protocol via the in-memory client."""

from __future__ import annotations

from fastmcp import Client

from claude_desktop_mcp.catalog import CATALOG
from claude_desktop_mcp.config import DEFAULT_SEARCH_TOOL_NAME, Config
from claude_desktop_mcp.server import build_server


async def test_full_mode_lists_entire_catalog_under_natural_names() -> None:
    server = build_server(Config(mode="full"))
    async with Client(server) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools}
    assert len(tools) == len(CATALOG)
    assert len(tools) >= 101
    assert DEFAULT_SEARCH_TOOL_NAME not in names
    # Plain server: natural catalog names, no AgentCore namespacing.
    assert "orders_get_order" in names
    assert not any("___" in n for n in names)


async def test_gateway_mode_lists_everything_with_search_first() -> None:
    """A faithful AgentCore gateway advertises every tool, search tool first."""
    server = build_server(Config(mode="gateway"))
    async with Client(server) as client:
        tools = await client.list_tools()
    names = [t.name for t in tools]
    assert len(names) == len(CATALOG) + 1
    assert names[0] == DEFAULT_SEARCH_TOOL_NAME  # listed first, per the AWS docs
    # Catalog tools carry the ``target___tool`` namespacing.
    assert "orders___get_order" in names
    assert all("___" in n for n in names if n != DEFAULT_SEARCH_TOOL_NAME)


async def test_gateway_prefixed_tool_is_callable_by_full_name() -> None:
    server = build_server(Config(mode="gateway"))
    async with Client(server) as client:
        result = await client.call_tool("orders___get_order", {"order_id": "A-123"})
    payload = result.structured_content
    assert payload["ok"] is True
    assert payload["tool"] == "orders___get_order"
    assert payload["arguments"] == {"order_id": "A-123"}


async def test_gateway_search_returns_agentcore_faithful_definitions() -> None:
    server = build_server(Config(mode="gateway", search_top_k=5))
    async with Client(server) as client:
        result = await client.call_tool(
            DEFAULT_SEARCH_TOOL_NAME, {"query": "find a customer purchase order"}
        )
    # Mirrors AgentCore: result.structuredContent.tools[] of tool definitions.
    payload = result.structured_content
    tools = payload["tools"]
    assert 1 <= len(tools) <= 5
    first = tools[0]
    assert set(first) == {"name", "description", "inputSchema"}
    assert first["name"].startswith("orders___")
    assert first["inputSchema"]["type"] == "object"
