#!/usr/bin/env bash
# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: Apache-2.0

#
# Spin up the fake MCP servers locally and point Claude Desktop at them.
#
# What it does:
#   1. Builds the local server (`uv sync`) and health-checks both modes.
#   2. Backs up your existing claude_desktop_config.json.
#   3. Swaps in a config with `fake-mcp-full` and `fake-mcp-gateway` entries that
#      run *this* working copy over stdio.
#   4. Restarts Claude Desktop so it connects, then tails the JSONL event logs.
#   5. On exit (Ctrl-C / Enter / error) a trap restores your original config.
#
# Env overrides:
#   NO_RESTART=1   Don't quit/relaunch Claude Desktop automatically (do it yourself).
#
set -euo pipefail

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_BIN="$REPO_ROOT/.venv/bin/claude-desktop-mcp"
LOG_DIR="$REPO_ROOT/logs"

case "$(uname -s)" in
Darwin) CONFIG_DIR="$HOME/Library/Application Support/Claude" ;;
Linux) CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/Claude" ;;
*)
  echo "Unsupported OS: $(uname -s)" >&2
  exit 1
  ;;
esac
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

log() { printf '==> %s\n' "$*"; }

# --------------------------------------------------------------------------- #
# Claude Desktop restart helpers (macOS only; elsewhere we just print a hint)
# --------------------------------------------------------------------------- #
restart_claude() { # $1: human description of why
  if [ "${NO_RESTART:-0}" = "1" ]; then
    log "Restart Claude Desktop manually to $1 (NO_RESTART=1)."
    return
  fi
  if [ "$(uname -s)" != "Darwin" ]; then
    log "Restart Claude Desktop manually to $1."
    return
  fi
  if osascript -e 'application "Claude" is running' 2>/dev/null | grep -qi true; then
    osascript -e 'quit app "Claude"' >/dev/null 2>&1 || true
    sleep 1
  fi
  open -a "Claude" >/dev/null 2>&1 && log "Restarted Claude Desktop to $1." ||
    log "Could not auto-launch Claude Desktop; start it manually to $1."
}

# --------------------------------------------------------------------------- #
# Cleanup / restore (runs on any exit)
# --------------------------------------------------------------------------- #
BACKUP=""
SWAPPED=0
cleanup() {
  if [ "$SWAPPED" = "1" ]; then
    if [ -n "$BACKUP" ] && [ -f "$BACKUP" ]; then
      mv -f "$BACKUP" "$CONFIG_FILE"
      log "Restored your original Claude Desktop config."
    else
      rm -f "$CONFIG_FILE"
      log "Removed the temporary config (you had none before)."
    fi
    restart_claude "load your original config"
  fi
}
trap 'exit 130' INT
trap 'exit 143' TERM
trap cleanup EXIT

# --------------------------------------------------------------------------- #
# 1. Build + health-check the local servers
# --------------------------------------------------------------------------- #
command -v uv >/dev/null 2>&1 || {
  echo "uv is required: https://docs.astral.sh/uv/" >&2
  exit 1
}

log "Syncing dependencies (uv sync)…"
(cd "$REPO_ROOT" && uv sync --extra dev)

[ -x "$SERVER_BIN" ] || {
  echo "server binary missing after uv sync: $SERVER_BIN" >&2
  exit 1
}
log "Health-checking both modes…"
"$REPO_ROOT/.venv/bin/python" - <<'PY'
import asyncio
from fastmcp import Client
from claude_desktop_mcp.config import Config
from claude_desktop_mcp.server import build_server

async def main():
    for mode in ("full", "gateway"):
        async with Client(build_server(Config(mode=mode))) as client:
            tools = await client.list_tools()
            print(f"    {mode}: {len(tools)} tool(s) listed")

asyncio.run(main())
PY

# --------------------------------------------------------------------------- #
# 2. Back up the existing config, then swap in ours
# --------------------------------------------------------------------------- #
mkdir -p "$CONFIG_DIR" "$LOG_DIR"
if [ -f "$CONFIG_FILE" ]; then
  BACKUP="$(mktemp "$CONFIG_DIR/claude_desktop_config.json.orig.XXXXXX")"
  cp -p "$CONFIG_FILE" "$BACKUP"
  log "Backed up your config to: $BACKUP"
else
  log "No existing config found; will create a temporary one."
fi

"$REPO_ROOT/.venv/bin/python" - "$SERVER_BIN" "$LOG_DIR" >"$CONFIG_FILE" <<'PY'
import json, sys

server_bin, log_dir = sys.argv[1], sys.argv[2]
config = {
    "mcpServers": {
        "fake-mcp-full": {
            "command": server_bin,
            "args": [],
            "env": {"MCP_MODE": "full", "MCP_LOG_FILE": f"{log_dir}/full.jsonl"},
        },
        "fake-mcp-gateway": {
            "command": server_bin,
            "args": [],
            "env": {"MCP_MODE": "gateway", "MCP_LOG_FILE": f"{log_dir}/gateway.jsonl"},
        },
    }
}
print(json.dumps(config, indent=2))
PY
SWAPPED=1
log "Swapped in fake MCP config -> $CONFIG_FILE"

# --------------------------------------------------------------------------- #
# 3. Restart Claude Desktop and tail the logs until interrupted
# --------------------------------------------------------------------------- #
restart_claude "connect to the fake MCP servers"

touch "$LOG_DIR/full.jsonl" "$LOG_DIR/gateway.jsonl"
cat <<EOF

  Claude Desktop is now wired to:
    • fake-mcp-full     (108 tools, no search)        -> $LOG_DIR/full.jsonl
    • fake-mcp-gateway  (108 tools + search, first)   -> $LOG_DIR/gateway.jsonl

  Watching the event logs. Press Ctrl-C to stop and restore your original config.

EOF
# NOT `exec` — the shell must stay alive so the EXIT trap restores the config.
tail -f "$LOG_DIR/full.jsonl" "$LOG_DIR/gateway.jsonl"
