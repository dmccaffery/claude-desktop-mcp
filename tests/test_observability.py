# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: Apache-2.0

"""Observability records the toolset footprint and hidden-call events."""

from __future__ import annotations

import json
from pathlib import Path

from fastmcp import Client

from claude_desktop_mcp.catalog import CATALOG
from claude_desktop_mcp.config import DEFAULT_SEARCH_TOOL_NAME, Config
from claude_desktop_mcp.server import build_server


def _read_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_estimate_tokens_and_footprint_units() -> None:
    from claude_desktop_mcp.observability import estimate_tokens, listing_footprint

    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2  # ceil(5/4)
    byte_size, tokens = listing_footprint(
        [{"name": "x", "description": "y", "inputSchema": {}}]
    )
    assert byte_size > 0 and tokens > 0


async def test_list_and_hidden_call_are_logged(tmp_path: Path) -> None:
    log_file = tmp_path / "full.jsonl"
    server = build_server(Config(mode="full", log_file=str(log_file)))

    async with Client(server) as client:
        await client.list_tools()
        # The search tool is the one tool hidden from a ``full`` listing.
        await client.call_tool(DEFAULT_SEARCH_TOOL_NAME, {"query": "orders"})

    events = _read_events(log_file)
    by_type: dict[str, list[dict]] = {}
    for event in events:
        by_type.setdefault(event["event"], []).append(event)

    # A footprint event with the headline metrics.
    list_events = by_type["list_tools"]
    assert list_events
    footprint = list_events[-1]
    assert footprint["tool_count"] == len(CATALOG)
    assert footprint["bytes"] > 0
    assert footprint["est_tokens"] > 0
    assert DEFAULT_SEARCH_TOOL_NAME not in footprint["tools"]

    # The hidden tool call is recorded and flagged.
    hidden_calls = [
        e for e in by_type["call_tool"] if e["tool"] == DEFAULT_SEARCH_TOOL_NAME
    ]
    assert hidden_calls and hidden_calls[0]["hidden"] is True


async def test_gateway_footprint_is_not_smaller_than_full(tmp_path: Path) -> None:
    """The crux finding: a faithful gateway does NOT shrink the listing.

    It returns the whole catalog *plus* the search tool, so the listing footprint is
    if anything larger than a plain server. The token saving AgentCore advertises only
    happens when the consuming agent uses search to expose a subset to its model —
    something a passive client that just loads ``tools/list`` never does.
    """
    full_log = tmp_path / "full.jsonl"
    gateway_log = tmp_path / "gateway.jsonl"

    async with Client(
        build_server(Config(mode="full", log_file=str(full_log)))
    ) as client:
        await client.list_tools()
    async with Client(
        build_server(Config(mode="gateway", log_file=str(gateway_log)))
    ) as client:
        await client.list_tools()

    def footprint(path: Path) -> dict:
        return [e for e in _read_events(path) if e["event"] == "list_tools"][-1]

    full = footprint(full_log)
    gateway = footprint(gateway_log)
    assert full["tool_count"] == len(CATALOG)
    assert gateway["tool_count"] == len(CATALOG) + 1  # catalog + search tool
    assert gateway["est_tokens"] >= full["est_tokens"]
