# tools

A standalone Go [tool module](https://go.dev/doc/modules/managing-dependencies#tools) that pins the developer CLIs this
repo uses, so their versions are tracked in `go.mod` / `go.sum` without leaking into the rest of the project. There is
no Go application here — only `tool` directives.

## Pinned tools

| Tool                           | Purpose                                           |
| ------------------------------ | ------------------------------------------------- |
| `github.com/google/addlicense` | Add / verify license headers across source files. |

## Usage

Run a pinned tool from anywhere in the repo via `go tool` against this module:

```sh
# Add MIT headers (or --check in CI to verify presence)
go -C tools tool addlicense -l mit -c "Deavon McCaffery" -check ../...

```

## Maintenance

```sh
# Add another tool
go -C tools get -tool <module/path>@latest

# Upgrade pinned tools
go -C tools get -tool -u ./...
go -C tools mod tidy
```

Dependabot tracks this module under the `gomod` ecosystem (see `.github/dependabot.yaml`).
