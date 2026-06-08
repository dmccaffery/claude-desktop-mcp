# claude-desktop-mcp

A deliberately fake MCP server for **validating how Claude Desktop handles large toolsets** — and how it behaves against
the Amazon Bedrock AgentCore Gateway semantic-search pattern.

It exposes **108 themed "fake" tools** (orders, users, files, GitHub, Slack, weather, calendar, database, email,
payments, Jira, analytics, notifications, storage). None of them do real work — each returns a canned echo response —
but they have realistic names, descriptions, and input schemas so the server is a faithful stand-in for a big
multi-service MCP setup.

## Two modes

The mode is chosen at startup via the `MCP_MODE` environment variable:

| Mode             | `tools/list` returns                                | `tools/call` accepts                                              | What it validates                                                                                 |
| ---------------- | --------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `full` (default) | **all 108** catalog tools                           | any catalog tool                                                  | What Desktop does when an MCP server dumps a large toolset into context.                          |
| `search`         | **only one** tool: `x_amz_bedrock_agentcore_search` | **any** catalog tool — even though only the search tool is listed | Whether Desktop can discover a tool via search and then call a tool it never saw in `tools/list`. |

The `search` mode is **AgentCore-faithful**: like a real gateway, `tools/list` advertises only the search tool, but
`tools/call` still works for any of the hidden 108 tools. The search tool takes a `{ "query": "..." }` argument, runs a
cheap keyword (BM25-lite) ranking over the catalog, and returns the matching tool **definitions** (`name`,
`description`, `inputSchema`, `score`) as JSON — which the client can then call directly by name.

> This is _not_ full natural-language semantic search. It is a small, dependency-free ranker that is "good enough" to
> mimic discovery behaviour.

## Requirements

- Python ≥ 3.10
- [`uv`](https://docs.astral.sh/uv/) (recommended) — or any PEP 517 installer
- Built on [FastMCP](https://gofastmcp.com)

## Install & run

```sh
uv sync --extra dev          # create the venv and install deps
uv run claude-desktop-mcp    # run over stdio (MCP_MODE defaults to "full")
MCP_MODE=search uv run claude-desktop-mcp
```

### Turnkey local run: `make run`

`make run` (a thin wrapper over [`hack/run.sh`](hack/run.sh)) builds and health-checks both modes, **backs up** your
`claude_desktop_config.json`, swaps in a config wired to this working copy (`fake-mcp-full` + `fake-mcp-search`, logging
to `logs/`), restarts Claude Desktop, and tails the event logs. Press **Ctrl-C** and a trap restores your original
config. Set `NO_RESTART=1` to skip the automatic Claude Desktop restart.

```sh
make run        # or: ./hack/run.sh
make test       # run the test suite
make help       # list targets
```

## Wiring into Claude Desktop

Edit `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`) and add one
or both entries. Register both to A/B test the two modes side by side. The example below runs straight from this public
repo — `uvx` clones and builds it on demand, so **no local path is required**:

```json
{
  "mcpServers": {
    "fake-mcp-full": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/dmccaffery/claude-desktop-mcp", "claude-desktop-mcp"],
      "env": { "MCP_MODE": "full" }
    },
    "fake-mcp-search": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/dmccaffery/claude-desktop-mcp", "claude-desktop-mcp"],
      "env": { "MCP_MODE": "search" }
    }
  }
}
```

Pin a tag or branch by appending `@<ref>`, e.g. `git+https://github.com/dmccaffery/claude-desktop-mcp@v0.1.0`. The first
launch builds the package (a few seconds); `uvx` caches it for subsequent launches. Restart Claude Desktop after editing
the config.

### Running from a local clone instead

If you've cloned the repo and want to run your working copy, point `--from` at the checkout. **The path must be
absolute** — Claude Desktop launches the server without a shell and with an unpredictable working directory, so relative
paths, `~`, and `$HOME` are not expanded:

```json
{
  "command": "uvx",
  "args": ["--from", "/absolute/path/to/claude-desktop-mcp", "claude-desktop-mcp"],
  "env": { "MCP_MODE": "search" }
}
```

### Optional: write a JSONL log

Add `MCP_LOG_FILE` to the `env` block to capture the structured event log (see
[Observability](#observability-measuring-the-context-footprint)). It too must be an **absolute** path to a writable
location, for the same reason:

```json
"env": { "MCP_MODE": "full", "MCP_LOG_FILE": "/absolute/path/to/logs/full.jsonl" }
```

## Example prompts

Once a server is connected, drive it from any MCP client (Claude Desktop, Claude Code, or the cowork agent) with a task
that naturally spans several domains. Every tool returns a canned echo, so the _outcome_ is irrelevant — what you're
validating is how the model **selects, discovers, and calls** tools, and what the toolset costs in context.

> **Enable one server at a time.** If both `fake-mcp-full` and `fake-mcp-search` are active at once, the full catalog is
> already visible and the search test is meaningless.

Paste this multi-domain prompt (it typically chains 8–12 tool calls across users → orders → payments → Jira → Slack →
email):

```text
A customer (email jordan@example.com) says their order never arrived and they
think they were charged twice. Please:

1. Look up the customer and their recent orders.
2. Find the problem order, its shipment tracking, and its payment charges.
3. Refund the duplicate charge.
4. Open a Jira ticket in the SUPPORT project summarizing the issue.
5. Post a heads-up in the #customer-ops Slack channel.
6. Email the customer to confirm the refund and the new ETA.

Narrate each step and show me which tool you used for it.
```

What each mode validates:

- **`fake-mcp-full` (108 tools):** tool-selection accuracy when the whole catalog is dumped into context. Watch whether
  the model picks the right `orders_*` / `payments_*` / `jira_*` tools, and check the footprint in `logs/full.jsonl`.
- **`fake-mcp-search` (search only):** the model sees only `x_amz_bedrock_agentcore_search`, so it must search the
  gateway for each capability, discover the hidden tools, and call them. In `logs/search.jsonl` you'll see `call_tool`
  events with `"hidden": true` — the model calling tools that were never in `tools/list`.

To force the discovery loop explicitly (nice for the search server):

```text
I don't know what tools you have. Search your tool gateway to discover
capabilities for: orders, refunds, Slack messaging, and analytics events.
For each area, tell me which tools you found, then call one of them with
sample arguments and show me the result.
```

After a run, compare the logs — this is the concrete "how does the context window handle a large toolset" answer (see
[Observability](#observability-measuring-the-context-footprint)):

```sh
# Footprint per listing: full ≈ 108 tools / ~9k tokens vs search = 1 tool / ~150 tokens
jq -c 'select(.event=="list_tools") | {mode, tool_count, est_tokens}' logs/full.jsonl logs/search.jsonl

# Tools the model discovered via search and then called (never listed)
jq -c 'select(.event=="call_tool" and .hidden==true) | .tool' logs/search.jsonl
```

## Environment variables

| Variable               | Default                          | Meaning                                              |
| ---------------------- | -------------------------------- | ---------------------------------------------------- |
| `MCP_MODE`             | `full`                           | `full` or `search`.                                  |
| `MCP_SEARCH_TOP_K`     | `5`                              | How many tools the search tool returns.              |
| `MCP_SEARCH_TOOL_NAME` | `x_amz_bedrock_agentcore_search` | Name of the search tool.                             |
| `MCP_LOG_FILE`         | _(unset)_                        | If set, append structured JSONL events to this file. |
| `MCP_LOG_LEVEL`        | `info`                           | `info` or `debug`.                                   |
| `MCP_SERVER_NAME`      | `claude-desktop-mcp`             | Server name reported to the client.                  |

## Observability: measuring the context footprint

The server **cannot read Claude's internally-assembled context window**. What it _can_ do is record everything Desktop
loads/requests at the MCP protocol boundary — a faithful proxy for "how the context window handles the toolset". Every
event is written to **stderr** (which Claude Desktop captures) and, when `MCP_LOG_FILE` is set, appended as JSON Lines.

Key events:

- **`list_tools`** — the headline metric. Records the **`tool_count`**, the serialized **`bytes`**, and an estimated
  **`est_tokens`** of the returned tool definitions. This is the toolset's context footprint. Comparing `full` vs
  `search`:

  ```text
  full:   {"event":"list_tools","mode":"full",  "tool_count":108,"bytes":...,"est_tokens":~9100}
  search: {"event":"list_tools","mode":"search","tool_count":1,  "bytes":592,"est_tokens":148}
  ```

  That ~60× footprint difference is the concrete answer to "how does the context window handle the large toolset."

- **`call_tool`** — records the `tool`, its `arguments`, and a **`hidden`** flag that is `true` when the called tool was
  _not_ in the listing the client last saw (the payoff of search mode — Desktop calling a discovered, never-listed
  tool).

- **`initialize`** — client name/version and protocol version (which Desktop build).

- **`startup`** — mode, catalog size, and search settings, emitted once at boot.

### Reading the logs

- **Your JSONL file** (`MCP_LOG_FILE`): durable, one JSON object per line. Inspect with e.g.
  `jq -c 'select(.event=="list_tools")' logs/full.jsonl`.
- **Claude Desktop's own MCP logs** (macOS): `~/Library/Logs/Claude/mcp*.log` — the server's stderr is interleaved here
  next to Desktop's view of the connection.

> Token counts use a documented `ceil(len(json)/4)` heuristic and are approximate.

## Verifying without Claude Desktop

Run the test suite:

```sh
uv run pytest
```

Or drive it manually with the MCP Inspector:

```sh
npx @modelcontextprotocol/inspector \
  uvx --from git+https://github.com/dmccaffery/claude-desktop-mcp claude-desktop-mcp
```

In `search` mode: list tools (you'll see one), call `x_amz_bedrock_agentcore_search` with a query, then call one of the
discovered tools by name and confirm it succeeds.

## Project layout

```text
src/claude_desktop_mcp/
  catalog.py        # 108 themed fake tools (pure data)
  search.py         # cheap BM25-lite ranking + substring fallback
  observability.py  # JSONL/stderr event logger + footprint estimation
  middleware.py     # ModeMiddleware (list filter) + ObservabilityMiddleware
  config.py         # environment-variable configuration
  server.py         # build_server(): registers tools + middleware
  __main__.py       # stdio entrypoint
tests/              # catalog, search, modes, observability
```
