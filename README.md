# claude-desktop-mcp

A deliberately fake MCP server for **validating how Claude Desktop handles large toolsets** — and how it behaves against
the Amazon Bedrock AgentCore Gateway semantic-search pattern.

It exposes **108 themed "fake" tools** (orders, users, files, GitHub, Slack, weather, calendar, database, email,
payments, Jira, analytics, notifications, storage). None of them do real work — each returns a canned echo response —
but they have realistic names, descriptions, and input schemas so the server is a faithful stand-in for a big
multi-service MCP setup.

## Two modes

The mode is chosen at startup via the `MCP_MODE` environment variable:

| Mode             | `tools/list` returns                                                                                          | What it validates                                                      |
| ---------------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `full` (default) | **all 108** catalog tools, natural names, **no** search tool                                                  | What Desktop does when a plain MCP server dumps a large toolset.       |
| `gateway`        | **all 109** tools — `x_amz_bedrock_agentcore_search` **first**, then the 108 catalog tools as `target___tool` | What Desktop does against a faithful Amazon Bedrock AgentCore Gateway. |

### `gateway` mode is a faithful AgentCore gateway

A real
[AgentCore Gateway with semantic search](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-semantic-search.html)
does **not** hide your tools. Its `tools/list` returns the entire catalog with the built-in search tool
[listed first](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-list.html). This mode
mirrors that exactly:

- **Naming** — every catalog tool is namespaced by its target with a triple-underscore delimiter
  ([`target___tool`](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-tool-naming.html)), e.g.
  `payments___refund_charge`.
- **Search tool** — `x_amz_bedrock_agentcore_search` takes a single `{ "query": "..." }` argument and returns matching
  tool **definitions** (`name`, `description`, `inputSchema`), ranked most-relevant first, under
  **`result.structuredContent.tools`** — the exact shape the AWS samples read.
- **Ranking** — a cheap, dependency-free BM25-lite ranker with a substring fallback stands in for real vector search.
  Not natural-language semantic search; just "good enough" to mimic discovery.

> **The catch this server is built to surface.** Because the gateway lists _everything_, semantic search saves no
> context **on its own**. In the AWS reference agents (Strands, LangGraph) the _agent runtime_ exposes only the search
> tool to the model and then **dynamically re-injects** the discovered tools into the model's tool list before the next
> turn. A passive MCP client — like Claude Desktop / Cowork — just loads `tools/list` and never performs that
> re-injection step. So pointed at a real gateway it sees the full 109-tool footprint, and a discovered tool's schema
> _returned as data_ is **not** something it can promote into a callable tool. (There is no `search` mode that hides the
> catalog: that would misrepresent what AgentCore does — the hiding happens agent-side, not at the gateway.)

## Requirements

- Python ≥ 3.10
- [`uv`](https://docs.astral.sh/uv/) (recommended) — or any PEP 517 installer
- Built on [FastMCP](https://gofastmcp.com)

## Install & run

```sh
uv sync --extra dev          # create the venv and install deps
uv run claude-desktop-mcp    # run over stdio (MCP_MODE defaults to "full")
MCP_MODE=gateway uv run claude-desktop-mcp
```

### Turnkey local run: `make run`

`make run` (a thin wrapper over [`hack/run.sh`](hack/run.sh)) builds and health-checks both modes, **backs up** your
`claude_desktop_config.json`, swaps in a config wired to this working copy (`fake-mcp-full` + `fake-mcp-gateway`,
logging to `logs/`), restarts Claude Desktop, and tails the event logs. Press **Ctrl-C** and a trap restores your
original config. Set `NO_RESTART=1` to skip the automatic Claude Desktop restart.

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
    "fake-mcp-gateway": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/dmccaffery/claude-desktop-mcp", "claude-desktop-mcp"],
      "env": { "MCP_MODE": "gateway" }
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
  "env": { "MCP_MODE": "gateway" }
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

> **Enable one server at a time.** Both modes advertise the whole catalog, so running `fake-mcp-full` and
> `fake-mcp-gateway` together just doubles the tools the model sees and muddies the per-server footprint in the logs.

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

- **`fake-mcp-full` (108 tools, no search):** tool-selection accuracy when the whole catalog is dumped into context.
  Watch whether the model picks the right `orders_*` / `payments_*` / `jira_*` tools, and check the footprint in
  `logs/full.jsonl`.
- **`fake-mcp-gateway` (109 tools, search first):** a faithful AgentCore gateway. The model sees the search tool _and_
  all 108 `target___tool` tools. The question is behavioural: does it lean on `x_amz_bedrock_agentcore_search` to narrow
  down, or just scan the full catalog like any other large toolset? And does it correctly call tools by their
  `target___tool` names? Check the footprint and `call_tool` sequence in `logs/gateway.jsonl`.

To probe the discovery behaviour explicitly:

```text
I don't know what tools you have. Search your tool gateway to discover
capabilities for: orders, refunds, Slack messaging, and analytics events.
For each area, tell me which tools you found, then call one of them with
sample arguments and show me the result.
```

In `gateway` mode the discovered tools are already in `tools/list`, so a well-behaved client can call them straight
away. The interesting failure mode is a client that treats the search result as a hint about tools it _doesn't_ have —
calling search, getting schemas back, and then not knowing how to invoke them. That's the "schemas returned as data
aren't callable tools" gap that only an agent runtime with dynamic re-injection closes.

After a run, compare the logs (see [Observability](#observability-measuring-the-context-footprint)):

```sh
# Footprint per listing: full = 108 tools vs gateway = 109 tools (catalog + search).
# A faithful gateway is NOT smaller — that's the point.
jq -c 'select(.event=="list_tools") | {mode, tool_count, est_tokens}' logs/full.jsonl logs/gateway.jsonl

# Did the model actually use the search tool, and in what order did it call things?
jq -c 'select(.event=="call_tool") | {tool, hidden}' logs/gateway.jsonl
```

## Environment variables

| Variable               | Default                          | Meaning                                              |
| ---------------------- | -------------------------------- | ---------------------------------------------------- |
| `MCP_MODE`             | `full`                           | `full` or `gateway`.                                 |
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
  `gateway`:

  ```text
  full:    {"event":"list_tools","mode":"full",   "tool_count":108,"bytes":...,"est_tokens":~9100}
  gateway: {"event":"list_tools","mode":"gateway","tool_count":109,"bytes":...,"est_tokens":~9400}
  ```

  The faithful gateway is _slightly larger_ (the whole catalog under longer `target___tool` names, plus the search
  tool). The lesson: a gateway's semantic search reduces context only when the **consuming agent** uses it to expose a
  subset to its model — not at the `tools/list` boundary a passive client reads.

- **`call_tool`** — records the `tool`, its `arguments`, and a **`hidden`** flag that is `true` when the called tool was
  _not_ in the listing the client last saw. In `gateway` mode everything is listed, so this is `false`; in `full` mode
  the only hidden-but-callable tool is `x_amz_bedrock_agentcore_search` itself.

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

In `gateway` mode: list tools (the search tool is first, then all 108 `target___tool` tools), call
`x_amz_bedrock_agentcore_search` with a query, read the ranked definitions under `structuredContent.tools`, then call
one of them by its full `target___tool` name and confirm it succeeds.

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
