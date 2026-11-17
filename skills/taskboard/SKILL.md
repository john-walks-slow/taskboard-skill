---
name: taskboard
description: A shared task ledger for coordinating multi-step, parallel, or cross-session coding-agent work. MANDATORY: ALWAYS use this skill before starting or resuming work (check `list`/`status`, claim with `doing`), when adding or waiting on prerequisite dependencies (`dep add --wait` / `wait`), when recording progress notes or blockers (`note` / `block`), when handing off or completing tasks (`handoff` / `done`), or when searching past task history (`search`).
---

# Taskboard

> CLI entrypoint: `python <skill_dir>/scripts/taskboard` (abbreviated as `taskboard` in examples below).

## Task statuses

- `READY`: no unfinished dependencies; available to claim with `taskboard doing`.
- `IN_PROGRESS`: actively claimed via `taskboard doing`.
- `WAITING`: has unfinished `depends_on` prerequisites; automatically becomes `READY` once all prerequisites are `DONE`.
- `BLOCKED`: explicitly blocked via `taskboard block`; restore with `taskboard unblock`.
- `DONE`: completed.

## Core workflow

1. **Inspect & search**: Run `taskboard list`, `taskboard status`, or `taskboard search` to check existing work; create a new task with `taskboard add "Short title" [--desc "Scope or context"]`.
2. **Claim & record progress**: Claim a ready task with `taskboard doing TASK_ID` (one session may work on multiple tasks). Record concise progress summaries or key findings with `taskboard note TASK_ID "What was done"`; inspect them anytime via `taskboard show TASK_ID`.
3. **Dependencies & blocking wait**:
   - `taskboard dep add TASK_ID --needs OTHER_TASK_ID`: add a prerequisite dependency.
   - `taskboard dep add TASK_ID --needs OTHER_TASK_ID --wait [--timeout SECONDS]`: add a dependency and block until `OTHER_TASK_ID` is `DONE`.
   - `taskboard wait TASK_ID [...] [--ready] [--timeout SECONDS]`: block until target tasks are `DONE` (or pass `--ready` to wait until all dependencies of `TASK_ID` are `DONE`). Fails immediately if a waited-on task or prerequisite becomes `BLOCKED`.
4. **Block, finish & hand off**:
   - Record a blocker: `taskboard block TASK_ID --reason "Reason"`; clear it with `taskboard unblock TASK_ID`.
   - Complete a task: `taskboard done TASK_ID [--note "Summary"]`.
   - Hand off a task: `taskboard handoff TASK_ID --to REAL_SID [--to-harness NAME] [--note "Handoff context"]`, returning it to `READY`/`WAITING` for the receiving session to claim.

## Search syntax (`taskboard search`)

Powered by zero-dependency multi-field BM25F scoring (`id` > `title` > `blocked_reason` > Markdown body > metadata), with automatic `camelCase`/`snake_case` splitting, CJK bigrams, and fuzzy fallback (`--exact` disables fuzzy matching):

- **Boolean & phrases**: space-separated terms use `AND`; supports `OR`, quoted phrases `"exact match"`, and `-exclude` (e.g. `taskboard search oauth login -legacy`).
- **Inline filters**: `status:READY,IN_PROGRESS`, `harness:opencode`, `sid:xxx`, `task:t-xxxx`, `type:task|event`, `since:YYYY-MM-DD`, `before:YYYY-MM-DD` (usable with or without keywords).
- **Flags**: `--tasks-only`, `--events-only`, `--status`, `--harness`, `--sid`, `--since`, `--limit N` (default `20`, `0` for all), `--json`.

## Automatic context board sync

- Every task state change (`add`, `doing`, `done`, `block`, `unblock`, `dep add`, `handoff`) automatically updates the configured context files—no manual `taskboard sync` needed.
- Target files are configured as an array in `.taskboard/config.json (or global `scripts/config.json`)` under `context_file` (default `["AGENTS.md"]`, e.g. `["AGENTS.md", "CLAUDE.md"]`). Edits to `config.json` take effect immediately without re-running `init`; set `"auto_sync": false` or `"context_file": []` to disable.
- Only the region between `<!-- TASKBOARD:START -->` and `<!-- TASKBOARD:END -->` is replaced, preserving all surrounding content. Use `taskboard sync --dry-run` or `taskboard context` to preview.

## Session identity

`doing`, `done`, `block`, and `handoff` automatically detect both the active Harness type and session ID:

Supported out of the box: Codex, Claude Code, OpenCode, DeepSeek Harness, Pi, Antigravity / Gemini CLI, Hermes Agent, Goose, OpenClaw, Qoder, Cursor, and Kiro.

You can also customize `harness_env` in `.taskboard/config.json (or global `scripts/config.json`)` or pass `--harness NAME --sid REAL_SID` explicitly.
