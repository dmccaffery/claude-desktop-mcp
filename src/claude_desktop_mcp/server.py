# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: Apache-2.0

"""Assemble the FastMCP server: register the catalog, the search tool, and middleware.

``build_server`` is the single entrypoint used by both the console script
(``claude_desktop_mcp.__main__``) and the test suite (via the in-memory FastMCP
``Client``), so behaviour is identical in both.
"""

from __future__ import annotations

from typing import Any, Callable

from fastmcp import FastMCP
from fastmcp.tools.function_tool import FunctionTool

from claude_desktop_mcp.catalog import CATALOG, ToolSpec
from claude_desktop_mcp.config import Config
from claude_desktop_mcp.middleware import ModeMiddleware, ObservabilityMiddleware
from claude_desktop_mcp.observability import EventLogger
from claude_desktop_mcp.search import SearchIndex

def _search_tool_description() -> str:
    """Build the search tool's description, listing the domains it can reach.

    Naming the domains and telling the model to call this *first* makes it pick this
    gateway over a generic/built-in connector registry when a task needs order,
    payment, support, or messaging tools that aren't already loaded.
    """
    domains = ", ".join(sorted({spec.domain for spec in CATALOG}))
    return (
        "Discover and load tools available in THIS workspace's gateway. The gateway "
        f"exposes {len(CATALOG)}+ tools across these domains: {domains}. Call this "
        "tool FIRST to find the right tool for a task — before concluding that no "
        "connector exists or searching any external/public registry. Pass a natural "
        "language query (for example 'refund a payment charge' or 'create a jira "
        "ticket') and it returns the matching tool names, descriptions, and input "
        "schemas, which you can then call directly by name. Mirrors the Amazon "
        "Bedrock AgentCore Gateway semantic search tool."
    )


def _make_handler(spec: ToolSpec) -> Callable[..., dict[str, Any]]:
    """A generic canned-response handler that echoes its arguments (fake server)."""

    def handler(**kwargs: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "tool": spec.name,
            "domain": spec.domain,
            "arguments": kwargs,
            "result": {"id": f"{spec.domain}_fake_0001", "status": "ok"},
            "note": "This is a fake tool for validating Claude Desktop; no real action was taken.",
        }

    handler.__name__ = spec.name
    return handler


def _build_catalog_tool(spec: ToolSpec) -> FunctionTool:
    return FunctionTool(
        name=spec.name,
        description=spec.description,
        parameters=spec.input_schema(),
        fn=_make_handler(spec),
        tags=set(spec.tags),
    )


def _build_search_tool(config: Config, index: SearchIndex) -> FunctionTool:
    def search_handler(**kwargs: Any) -> dict[str, Any]:
        query = (kwargs.get("query") or "").strip()
        results = index.search(query, config.search_top_k)
        tools = [
            {
                "name": spec.name,
                "description": spec.description,
                "inputSchema": spec.input_schema(),
                "score": score,
            }
            for spec, score in results
        ]
        return {"query": query, "count": len(tools), "tools": tools}

    search_handler.__name__ = config.search_tool_name
    schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A natural language query describing the tool or capability you need.",
            }
        },
        "required": ["query"],
    }
    return FunctionTool(
        name=config.search_tool_name,
        description=_search_tool_description(),
        parameters=schema,
        fn=search_handler,
        tags={
            "search",
            "discovery",
            "agentcore",
            "gateway",
            "semantic",
            "find",
            "tools",
        },
    )


def build_server(config: Config | None = None) -> FastMCP:
    """Construct the configured FastMCP server (does not start it)."""
    config = config or Config.from_env()
    logger = EventLogger(config.log_file, config.log_level)
    index = SearchIndex(CATALOG)

    mcp: FastMCP = FastMCP(name=config.server_name)

    for spec in CATALOG:
        mcp.add_tool(_build_catalog_tool(spec))
    mcp.add_tool(_build_search_tool(config, index))

    # Order matters: observability is outermost so it logs the post-filter listing.
    mcp.add_middleware(
        ObservabilityMiddleware(logger, config.mode, config.search_tool_name)
    )
    mcp.add_middleware(ModeMiddleware(config.mode, config.search_tool_name))

    logger.emit(
        "startup",
        mode=config.mode,
        server_name=config.server_name,
        catalog_size=len(CATALOG),
        search_tool_name=config.search_tool_name,
        search_top_k=config.search_top_k,
        log_file=config.log_file,
    )
    return mcp
