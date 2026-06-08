# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: MIT

"""Structured event logging for inspecting how Claude Desktop loads the toolset.

The server cannot read Claude's internally-assembled context window. What it *can*
do is record everything Desktop loads/requests at the MCP protocol boundary, which
is a faithful proxy for "how the context window handles the toolset":

* ``list_tools`` events carry the **footprint** — the tool count plus the serialized
  byte size and an estimated token count of the returned tool definitions. Comparing
  ``full`` vs ``gateway`` mode footprints answers the question — and reveals that a
  faithful AgentCore gateway is *not* smaller: it lists the whole catalog plus the
  search tool, so the token saving only materialises if the client uses search to
  avoid loading everything.
* ``call_tool`` events record which tool was invoked and whether it was ``hidden``
  (not advertised in the current listing).

Events are written to stderr (Claude Desktop captures MCP-server stderr into
``~/Library/Logs/Claude/``) and, when ``MCP_LOG_FILE`` is set, appended as JSONL.
We never write to stdout: that is the stdio transport channel and writing there
would corrupt the MCP protocol stream.
"""

from __future__ import annotations

import json
import math
import os
import sys
import threading
from typing import Any, TextIO


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token). Documented as approximate."""
    return math.ceil(len(text) / 4)


class EventLogger:
    """Thread-safe JSON event sink: always stderr, optionally a JSONL file."""

    def __init__(
        self,
        log_file: str | None = None,
        level: str = "info",
        stream: TextIO | None = None,
    ) -> None:
        self.log_file = log_file
        self.level = level
        self._stream = stream if stream is not None else sys.stderr
        self._lock = threading.Lock()
        if log_file:
            parent = os.path.dirname(os.path.abspath(log_file))
            os.makedirs(parent, exist_ok=True)

    def emit(self, event: str, **fields: Any) -> dict[str, Any]:
        """Write one event. Returns the assembled record (handy for tests)."""
        record: dict[str, Any] = {"event": event, **fields}
        line = json.dumps(record, default=str, ensure_ascii=False)
        with self._lock:
            print(line, file=self._stream, flush=True)
            if self.log_file:
                with open(self.log_file, "a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
        return record


def listing_footprint(wire_tools: list[dict[str, Any]]) -> tuple[int, int]:
    """Return (byte_size, estimated_tokens) for a list of wire tool definitions."""
    payload = json.dumps(wire_tools, ensure_ascii=False, separators=(",", ":"))
    return len(payload.encode("utf-8")), estimate_tokens(payload)
