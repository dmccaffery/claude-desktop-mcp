# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: MIT

"""Runtime configuration, sourced from environment variables.

Claude Desktop launches MCP servers via ``command``/``args`` and can pass an ``env``
block, so environment variables are the natural way to select the mode and tune the
server per-config-entry.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

#: The default name of the AgentCore-style search tool (matches the AWS docs).
DEFAULT_SEARCH_TOOL_NAME = "x_amz_bedrock_agentcore_search"

_VALID_MODES = ("full", "gateway")


@dataclass(frozen=True)
class Config:
    """Resolved server configuration."""

    mode: str = "full"  # "full" | "gateway"
    search_tool_name: str = DEFAULT_SEARCH_TOOL_NAME
    search_top_k: int = 5
    server_name: str = "claude-desktop-mcp"
    log_file: str | None = None
    log_level: str = "info"  # "info" | "debug"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        env = env if env is not None else dict(os.environ)

        mode = env.get("MCP_MODE", "full").strip().lower()
        if mode not in _VALID_MODES:
            raise ValueError(f"MCP_MODE must be one of {_VALID_MODES}, got {mode!r}")

        top_k_raw = env.get("MCP_SEARCH_TOP_K", "5").strip()
        try:
            top_k = int(top_k_raw)
        except ValueError as exc:
            raise ValueError(
                f"MCP_SEARCH_TOP_K must be an integer, got {top_k_raw!r}"
            ) from exc
        if top_k < 1:
            raise ValueError(f"MCP_SEARCH_TOP_K must be >= 1, got {top_k}")

        log_file = env.get("MCP_LOG_FILE", "").strip() or None
        level = env.get("MCP_LOG_LEVEL", "info").strip().lower()

        return cls(
            mode=mode,
            search_tool_name=env.get(
                "MCP_SEARCH_TOOL_NAME", DEFAULT_SEARCH_TOOL_NAME
            ).strip()
            or DEFAULT_SEARCH_TOOL_NAME,
            search_top_k=top_k,
            server_name=env.get("MCP_SERVER_NAME", "claude-desktop-mcp").strip()
            or "claude-desktop-mcp",
            log_file=log_file,
            log_level=level,
        )
