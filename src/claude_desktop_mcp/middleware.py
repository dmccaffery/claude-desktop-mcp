# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: MIT

"""FastMCP middleware implementing the two modes and the observability trace.

Two middlewares cooperate, and **order matters**. FastMCP runs the first-added
middleware as the outermost layer, so we add :class:`ObservabilityMiddleware` first
and :class:`ModeMiddleware` second. That way the observability hook for ``list_tools``
observes the *post-filter* listing — exactly what the client receives.
"""

from __future__ import annotations

from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from claude_desktop_mcp.observability import EventLogger, listing_footprint


class ModeMiddleware(Middleware):
    """Shapes what ``tools/list`` advertises, without touching call routing.

    * ``full``    — a plain large MCP server: advertise every catalog tool, hide the
      search tool.
    * ``gateway`` — a faithful Amazon Bedrock AgentCore gateway: advertise *every*
      tool, with the ``x_amz_bedrock_agentcore_search`` tool listed **first** (per the
      AWS docs). The gateway does not hide the catalog — semantic search is an
      optimisation the *consuming agent* may use to expose only a subset to its model.

    ``on_call_tool`` is intentionally *not* overridden: every registered tool stays
    callable, so a search-then-call flow resolves against the underlying tool.
    """

    def __init__(self, mode: str, search_tool_name: str) -> None:
        self.mode = mode
        self.search_tool_name = search_tool_name

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        tools = list(await call_next(context))
        if self.mode == "gateway":
            # AgentCore lists the search tool first, then every catalog tool.
            search = [t for t in tools if t.name == self.search_tool_name]
            others = [t for t in tools if t.name != self.search_tool_name]
            return search + others
        # full: a generic server with no gateway search surface.
        return [t for t in tools if t.name != self.search_tool_name]


class ObservabilityMiddleware(Middleware):
    """Records protocol traffic so we can see how Desktop loads the toolset."""

    def __init__(self, logger: EventLogger, mode: str, search_tool_name: str) -> None:
        self.logger = logger
        self.mode = mode
        self.search_tool_name = search_tool_name
        self._last_listed: set[str] = set()

    async def on_initialize(self, context: MiddlewareContext, call_next):
        result = await call_next(context)
        msg = context.message
        client = getattr(msg, "clientInfo", None)
        self.logger.emit(
            "initialize",
            mode=self.mode,
            client=getattr(client, "name", None),
            client_version=getattr(client, "version", None),
            protocol=getattr(msg, "protocolVersion", None),
            ts=getattr(context, "timestamp", None),
        )
        return result

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        # This middleware is outermost, so ``tools`` is already mode-filtered.
        tools = list(await call_next(context))
        wire: list[dict[str, Any]] = [
            {"name": t.name, "description": t.description, "inputSchema": t.parameters}
            for t in tools
        ]
        byte_size, est_tokens = listing_footprint(wire)
        names = [t.name for t in tools]
        self._last_listed = set(names)
        self.logger.emit(
            "list_tools",
            mode=self.mode,
            tool_count=len(tools),
            bytes=byte_size,
            est_tokens=est_tokens,
            tools=names,
            ts=getattr(context, "timestamp", None),
        )
        return tools

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        name = getattr(context.message, "name", None)
        arguments = getattr(context.message, "arguments", None)
        # "hidden" = the tool was not advertised in the listing the client last saw.
        if self._last_listed:
            hidden = name not in self._last_listed
        else:  # no listing observed yet — fall back to the structural definition
            # gateway advertises everything; full hides only the search tool.
            hidden = self.mode == "full" and name == self.search_tool_name
        self.logger.emit(
            "call_tool",
            mode=self.mode,
            tool=name,
            hidden=hidden,
            arguments=arguments,
            ts=getattr(context, "timestamp", None),
        )
        return await call_next(context)
