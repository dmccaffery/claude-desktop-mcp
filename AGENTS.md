# Agent instructions

Repo-specific conventions for AI agents working in this repository. These layer on top of the global agent instructions
in `~/.claude/CLAUDE.md`. `CLAUDE.md` is a symlink to this file, so Claude Code and any other `AGENTS.md`-aware tool
read the same guidance.

## Before preparing commits

Run `make pr` before preparing any commit. It runs the full pre-commit gate — `license`, `fmt`, `lint`, and `test` — so
the working tree is license-headed, formatted, lint-clean, and green before anything is staged.

Then author the commit per the global commit convention: write `commit.sh` at the repo root (or re-sign inside a
worktree) and hand it to the user to run. `make commit` depends on `pr`, so it runs the same gate first and then
executes `./commit.sh` when that script is present — making `make commit` the one-shot path once `commit.sh` exists.

Never run `git commit` directly from inside the sandbox: commit signing runs through `ssh-agent`, which the sandbox
blocks, so any commit made there lands unsigned.
