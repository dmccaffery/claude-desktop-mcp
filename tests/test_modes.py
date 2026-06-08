# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: Apache-2.0

"""The two modes, exercised through the real MCP protocol via the in-memory client."""

from __future__ import annotations

from fastmcp import Client

from claude_desktop_mcp.catalog import CATALOG
from claude_desktop_mcp.config import DEFAULT_SEARCH_TOOL_NAME, Config
from claude_desktop_mcp.server import build_server


async def test_full_mode_lists_entire_catalog_and_hides_search_tool() -> None:
    server = build_server(Config(mode="full"))
    async with Client(server) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools}
    assert len(tools) == len(CATALOG)
    assert len(tools) >= 101
    assert DEFAULT_SEARCH_TOOL_NAME not in names


async def test_search_mode_lists_only_the_search_tool() -> None:
    server = build_server(Config(mode="search"))
    async with Client(server) as client:
        tools = await client.list_tools()
    assert [t.name for t in tools] == [DEFAULT_SEARCH_TOOL_NAME]


async def test_hidden_tool_is_callable_in_search_mode() -> None:
    """The crux: a tool absent from tools/list must still be callable."""
    server = build_server(Config(mode="search"))
    async with Client(server) as client:
        listed = {t.name for t in await client.list_tools()}
        assert "orders_get_order" not in listed  # hidden from listing

        result = await client.call_tool("orders_get_order", {"order_id": "A-123"})
    payload = result.structured_content
    assert payload["ok"] is True
    assert payload["tool"] == "orders_get_order"
    assert payload["arguments"] == {"order_id": "A-123"}


async def test_search_tool_returns_agentcore_faithful_definitions() -> None:
    server = build_server(Config(mode="search", search_top_k=5))
    async with Client(server) as client:
        result = await client.call_tool(
            DEFAULT_SEARCH_TOOL_NAME, {"query": "find a customer purchase order"}
        )
    payload = result.structured_content
    assert payload["query"]
    assert 1 <= payload["count"] <= 5
    first = payload["tools"][0]
    assert set(first) >= {"name", "description", "inputSchema", "score"}
    assert first["name"].startswith("orders_")
    assert first["inputSchema"]["type"] == "object"
