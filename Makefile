.DEFAULT_GOAL := help

# Run Node CLIs straight from node_modules so package-lock.json is the source of
# truth. Do not use npx or global developer-installed tools.
NPMBIN := ./node_modules/.bin

# Go developer CLIs are pinned in tools/go.mod and run via `go tool` (see
# tools/README.md). addlicense injects license headers. Ignores use absolute
# globs because `go -C tools` runs addlicense with the working directory set to
# tools/.
LICENSE_FILE   := '$(CURDIR)/LICENSE'
LICENSE_HOLDER := 'Deavon M. McCaffery'
LICENSE_IGNORE := -ignore '$(CURDIR)/.git/**' \
									-ignore '$(CURDIR)/.venv/**' \
									-ignore '$(CURDIR)/node_modules/**' \
									-ignore '$(CURDIR)/commit.sh'

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

.PHONY: fmt
fmt: node_modules ## Auto-format the repo: prettier (web/docs) + ruff (Python)
	@ $(NPMBIN)/prettier --write .
	@ uv run --extra dev ruff format .

.PHONY: lint
lint: fmt ## Format all files in the repository and lint markdown
	@ $(NPMBIN)/markdownlint-cli2 '**/*.md'

.PHONY: license
license: ## Inject license headers into source files (addlicense, pinned in tools/)
	@ go -C tools tool addlicense -c $(LICENSE_HOLDER) -s=only -f $(LICENSE_FILE) $(LICENSE_IGNORE) '$(CURDIR)'

.PHONY: licence
licence: license ## Alias for the license target

.PHONY: run
run: ## Swap Claude Desktop to the local fake servers and tail logs (Ctrl-C restores)
	./hack/run.sh

.PHONY: sync
sync: ## Install dependencies into .venv
	uv sync --extra dev

.PHONY: test
test: ## Run the test suite
	uv run pytest

.PHONY: inspector
inspector: node_modules ## Open the MCP Inspector (pinned in package.json) against the local server (MODE=full|gateway)
	MCP_MODE=$(or $(MODE),full) $(NPMBIN)/mcp-inspector uv run claude-desktop-mcp

# Install the pinned npm dev tools (mcp-inspector, prettier, markdownlint) exactly as
# locked in package-lock.json. Re-runs only when package.json / package-lock.json change.
node_modules: package.json package-lock.json
	npm ci
	@touch node_modules

.PHONY: upgrade
upgrade: ## Upgrade npm, uv, and Go tool deps (bypasses dependabot cooldown — confirms first)
	@ printf '\n'
	@ printf 'WARNING: `make upgrade` bypasses the 7-day dependabot cooldown configured\n'
	@ printf 'in .github/dependabot.yaml. Pulling fresh releases from the npm, PyPI,\n'
	@ printf 'and Go module registries before that window elapses can expose this repo\n'
	@ printf 'to supply-chain attacks (typosquat releases, hijacked packages, malicious\n'
	@ printf 'patch versions). Dependabot batches minor/patch updates into one PR after\n'
	@ printf 'the cooldown so the wider ecosystem has time to flag malicious releases.\n\n'
	@ printf 'Prefer merging the dependabot PR. Continue only if you have a reason.\n\n'
	@ printf 'Continue with upgrade? [y/N] '; read ans </dev/tty; \
		case "$$ans" in \
			y|Y|yes|Yes|YES) ;; \
			*) echo "Aborted."; exit 1 ;; \
		esac
	@ npm update
	@ uv sync --upgrade --all-extras
	@ go -C tools get -u tool
	@ go -C tools mod tidy
