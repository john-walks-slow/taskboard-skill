# taskboard

A lightweight, filesystem-native task board for coordinating multi-agent coding work across sessions. Zero database, zero daemon, zero third-party dependencies (Python 3.9+).

一个基于本地文件系统的轻量多 Agent 共享任务看板，支持任务状态流转、依赖阻塞等待、纯标准库 BM25F 检索，以及多上下文文件（`AGENTS.md` / `CLAUDE.md` 等）自动同步。

- **Markdown + YAML frontmatter** per task under `.taskboard/tasks/`, paired with an append-only `events.jsonl` history.
- **Automatic actor attribution**: detects the active Harness type and real session ID automatically on state changes.
- **DAG dependencies & blocking wait**: `dep add --wait` and `wait` block until prerequisites finish, failing fast on blockers.
- **BM25F multi-field search**: supports boolean queries, inline filters, camelCase/snake_case splitting, CJK bigrams, and fuzzy fallback.
- **Automatic board sync**: refreshes configured context files on every task state change.

## Quick start

Inside any supported Harness shell:

```bash
taskboard add "Normalize URL identity" --desc "Align canonical host/path rules"
taskboard list
taskboard doing t-xxxxxxxx
taskboard note t-xxxxxxxx "Added host normalization tests"
taskboard status
taskboard done t-xxxxxxxx --note "All unit tests passing"
```

`doing`, `note`, `done`, `block`, and `handoff` automatically detect the active Harness and session ID. If auto-detection is unavailable, pass them explicitly:

```bash
taskboard doing t-xxxxxxxx --harness codex --sid REAL_THREAD_ID
```

## Supported Harnesses

| Harness | Environment variable(s) |
|---|---|
| Codex | `CODEX_THREAD_ID` |
| Claude Code | `CLAUDE_CODE_SESSION_ID` |
| OpenCode | `OPENCODE_SESSION_ID` |
| DeepSeek Harness (`dsh`) | `DSH_SESSION_ID` |
| Pi (`pi-coding-agent`) | `PI_SESSION_ID` |
| Antigravity (`agy`) / Gemini CLI | `ANTIGRAVITY_SESSION_ID`, `GEMINI_SESSION_ID` |
| Hermes Agent | `HERMES_SESSION_ID` |
| Goose | `GOOSE_SESSION_ID` |
| OpenClaw | `OPENCLAW_SESSION_ID`, `OPENCLAW_SESSION_KEY` |
| Qoder | `QODER_SESSION_ID` |
| Cursor | `CURSOR_SESSION_ID`, `CURSOR_TRACE_ID` |
| Kiro | `KIRO_SESSION_ID` |

## Skill installation paths

Copy or symlink `skills/taskboard` into the skill directory for your Harness:

| Harness | Project path | User / global path |
|---|---|---|
| Codex / DeepSeek Harness | `.agents/skills/taskboard` | `~/.agents/skills/taskboard` |
| Claude Code | `.claude/skills/taskboard` | `~/.claude/skills/taskboard` |
| OpenCode | `.opencode/skills/taskboard` | `~/.config/opencode/skills/taskboard` |
| Pi | `.pi/skills/taskboard` | `~/.pi/agent/skills/taskboard` |
| Antigravity | `.agents/skills/taskboard` | `~/.gemini/antigravity/skills/taskboard` |

## Commands

```text
taskboard init [--context-file FILE ...]
taskboard add TITLE [--desc TEXT]
taskboard list [--all]
taskboard show TASK_ID
taskboard doing TASK_ID
taskboard note TASK_ID MESSAGE
taskboard done TASK_ID [--note TEXT]
taskboard block TASK_ID --reason TEXT
taskboard unblock TASK_ID
taskboard dep add TASK_ID --needs OTHER_TASK_ID [--wait] [--timeout SECONDS]
taskboard wait TASK_ID [TASK_ID ...] [--ready] [--timeout SECONDS]
taskboard handoff TASK_ID --to REAL_SID [--to-harness NAME] [--note TEXT]
taskboard status
taskboard search [QUERY ...] [--status STATUS] [--harness NAME] [--sid SID] [--tasks-only | --events-only] [--since ISO_DATE] [--limit N] [--exact] [--json]
taskboard sync [--dry-run]
taskboard context
```

## Search

`taskboard search` ranks tasks and events with zero-dependency multi-field BM25F scoring (`id` > `title` > `blocked_reason` > Markdown body > metadata; event values only, ignoring JSON keys):

```bash
# Multi-word AND, OR, negation, and quoted phrases
taskboard search auth login -legacy
taskboard search '"OAuth login"' OR callback

# Inline or flag filters
taskboard search status:READY,IN_PROGRESS harness:opencode --tasks-only
taskboard search --since 2026-11-01 --limit 10 --json
```

- Automatically splits `camelCase`, `snake_case`, `kebab-case`, and CJK bigrams.
- Falls back to fuzzy matching on typos unless `--exact` is passed.

## Blocking wait

Use `taskboard wait` or `taskboard dep add ... --wait` to block until prerequisite tasks finish:

```bash
# Add dependency and wait for OTHER_TASK_ID to become DONE
taskboard dep add t-bbbbbbbb --needs t-aaaaaaaa --wait

# Wait for one or more tasks to become DONE
taskboard wait t-aaaaaaaa t-cccccccc

# Wait until all dependencies of a task are DONE (no longer WAITING)
taskboard wait t-bbbbbbbb --ready --timeout 120
```

- Polls every 1 second and releases the project lock between polls so other sessions can run `done` or `block` without deadlocking.
- `--timeout` is optional; if a waited-on task or prerequisite becomes `BLOCKED`, `wait` exits immediately with an error.

## Files and task statuses

```text
.taskboard/
├── config.json
├── tasks/       # one Markdown record per task
└── events.jsonl # append-only activity history
```

Computed task statuses:

- `DONE`: explicitly completed.
- `BLOCKED`: explicitly blocked via `block`.
- `IN_PROGRESS`: actively claimed via `doing`.
- `WAITING`: has an unfinished dependency.
- `READY`: available to claim.

A `handoff` records the sender, recipient, and optional note, then returns the task to `READY` (or `WAITING` if dependencies remain) for the receiving session to claim.

## Configuration & automatic context sync

Every task state change (`add`, `doing`, `done`, `block`, `unblock`, `note`, `dep add`, `handoff`) automatically updates the configured context files between `<!-- TASKBOARD:START -->` and `<!-- TASKBOARD:END -->`, preserving all surrounding content.

Configuration is loaded in two layers (project overrides global; `harness_env` maps are merged):
- **Global**: `skills/taskboard/scripts/config.json`
- **Project**: `.taskboard/config.json`

```json
{
  "context_file": ["AGENTS.md", "CLAUDE.md"],
  "auto_sync": true,
  "harness_env": {
    "my-harness": ["MY_AGENT_SESSION_ID"]
  }
}
```

Set `"auto_sync": false` or `"context_file": []` to disable automatic sync. `TASKBOARD_HARNESS` and `TASKBOARD_SID` can also provide identity explicitly via environment variables.

## Reliability boundaries

- Atomic file replacement and an OS-level project lock serialize CLI writers on a local filesystem.
- Handoffs and SIDs are coordination records, not process control; Taskboard does not start, stop, or message external Agent processes.
- Human edits to task Markdown are supported; manual edits to `events.jsonl` are not recommended.
