# taskboard

A lightweight, filesystem-native task ledger for managing and tracing all work, from personal todos to multi-agent coding work across sessions. Zero database, zero daemon, zero third-party dependencies (Python 3.9+).

一个基于本地文件系统的轻量多 Agent 共享任务看板，支持任务状态流转、条件与事件阻塞监听、纯标准库 BM25F 检索，以及多上下文文件（`AGENTS.md` / `CLAUDE.md` 等）自动同步。

- **Markdown + YAML frontmatter** per task under the selected Board’s `tasks/` directory, paired with an append-only `events.jsonl` history.
- **Explicit task assignment**: one current assignee per task; `assign --self` and `add --self` support explicit self-assignment; `doing` also atomically self-assigns an unassigned task when starting it. Assignment writes are atomic under the Board lock.
- **DAG dependencies, task wait & event watch**: `wait` blocks on one task's state; `watch-next` can observe the whole Board or filter events for one task.
- **BM25F multi-field search**: supports boolean queries, inline filters, camelCase/snake_case splitting, CJK bigrams, and fuzzy fallback.
- **Automatic board sync**: refreshes configured context files on every task state change.

## Quick start

Initialize once from the project root:

```bash
python .agents/skills/taskboard/scripts/taskboard init --context-file AGENTS.md
```

Inside any supported Harness shell:

```bash
taskboard add "Normalize URL identity" --desc "Align canonical host/path rules" --self
taskboard list
taskboard doing t-xxxxxxxx
taskboard note t-xxxxxxxx "Added host normalization tests"
taskboard status
taskboard done t-xxxxxxxx --note "All unit tests passing"
```

`doing`, `note`, `done`, `block`, `handoff`, `assign`, and `unassign` automatically detect the active Harness and session ID. `doing` atomically assigns an unassigned task to the current session and starts it. It refuses to start a task assigned to another session. `--board NAME` must appear before the command. If auto-detection is unavailable, pass them explicitly:

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
taskboard board create NAME | list | show NAME | use NAME | rename OLD NEW | delete NAME [--force]
taskboard [--board NAME] add TITLE [--desc TEXT] [--self | --to SID --to-harness HARNESS]
taskboard [--board NAME] edit TASK_ID [--title TEXT] [--desc TEXT]
taskboard [--board NAME] list [--all]
taskboard [--board NAME] show TASK_ID
taskboard [--board NAME] assign TASK_ID (--self | --to SID --to-harness HARNESS) [--force]
taskboard [--board NAME] unassign TASK_ID [--force]
taskboard [--board NAME] doing TASK_ID
taskboard [--board NAME] note TASK_ID MESSAGE
taskboard [--board NAME] done TASK_ID [--note TEXT]
taskboard [--board NAME] block TASK_ID --reason TEXT
taskboard [--board NAME] unblock TASK_ID
taskboard [--board NAME] dep add TASK_ID --needs OTHER_TASK_ID [--wait] [--timeout SECONDS]
taskboard [--board NAME] wait TASK_ID [--until done|doing|ready|waiting|blocked] [--timeout SECONDS] [--json]
taskboard [--board NAME] watch-next [--task TASK_ID] [--event TYPE] [--since CURSOR] [--timeout SECONDS] [--json]
taskboard [--board NAME] handoff TASK_ID --to REAL_SID [--to-harness NAME] [--note TEXT]
taskboard [--board NAME] status
taskboard [--board NAME] search [QUERY ...] [--status STATUS] [--harness NAME] [--sid SID] [--tasks-only | --events-only] [--since ISO_DATE] [--limit N] [--exact] [--json]
taskboard [--board NAME] sync [--dry-run]
taskboard [--board NAME] context
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

## Boards

Every task belongs to exactly one Board. The existing `.taskboard/tasks/` and `.taskboard/events.jsonl` remain the `default` Board, so existing projects need no migration. Named Boards live under `.taskboard/boards/NAME/`. Task IDs are scoped to a Board; dependencies cannot cross Board boundaries.

```bash
taskboard board create frontend
taskboard board create research
taskboard board list
taskboard board show frontend

# --board is a global option and goes before the command
taskboard --board frontend add "Implement login"
taskboard --board frontend list

# Set the project default; explicit --board always overrides it
taskboard board use frontend
taskboard add "Use the selected board"

# Deleting a non-empty board requires an explicit --force
taskboard board delete research --force

# Rename a named Board without losing its tasks or event history
taskboard board rename frontend web
```

`board rename OLD NEW` renames a named Board directory while preserving its tasks, dependencies, local config, and event history; it also updates the project default if that Board was selected. The `default` Board cannot be renamed.

The project config is shared by all Boards. A named Board may optionally have its own `config.json` overrides. Automatic context sync reflects the Board selected for the command; it does not merge task summaries from every Board.

## Task wait and Board watch

These commands have deliberately separate scopes:

- `wait` observes **one task** and returns when its current state reaches the requested condition.
- `watch-next` observes the selected Board's event stream and returns when a matching event arrives. Use `--task TASK_ID` to watch only events belonging to one task, and combine it with `--event task.updated` to wait specifically for metadata edits. `--event` alone filters by event type across the Board.

```bash
# Wait for one task to finish (returns immediately if already DONE)
taskboard wait t-aaaaaaaa
taskboard wait t-bbbbbbbb --until ready --timeout 120

# Add a dependency, then wait for its prerequisite to finish
taskboard dep add t-bbbbbbbb --needs t-aaaaaaaa --wait

# Listen for the next event anywhere on the selected Board
taskboard --board frontend watch-next --event task.created --json

# Watch only one task for edits to its title or description
taskboard --board frontend watch-next --task t-123 --event task.updated --json

# Resume from a previously returned event cursor
taskboard --board frontend watch-next --since 1234 --json
```

- Both commands poll every 250 ms and release the Board lock between polls.
- `wait` checks current state first, so already-satisfied conditions return immediately. It fails fast if the task or one of its prerequisites is blocked and the requested condition cannot be reached.
- `watch-next` starts at the current event-log offset by default. `--json` returns a machine-readable event and byte-offset `cursor`; pass it to `--since CURSOR` to resume without replaying the matched event.
- Dotted event names are accepted (`task.created` maps to the stored `task_created` type). `--timeout` is optional.

### Background watcher for Agent Harnesses

In supported Harnesses, run `taskboard watch-next` using the Harness's **background execution mode**. Do not occupy the foreground Agent call with a long-running watcher. The Agent should retain the background process handle, consume the event when it exits, handle the resulting work, and only after that work is finished invoke `watch-next` again to wait for the next event. The exact background mechanism is Harness-specific; do not assume shell `&` is sufficient.

Tasks created with `taskboard add` automatically append a `task_created` event, and metadata edits append `task_updated` with both the previous and new values, so the event log can explain what changed and Board- or task-scoped watchers can react to it. Manually editing a task Markdown file does not emit an event; use the CLI for tasks that should trigger automatic dispatch. `watch-next` only reports one event per invocation: it does not launch Workers. The CLI enforces one current assignee per task through atomic Board-locked assignment updates; it does not monitor whether a session is alive or automatically recover abandoned assignments.

## Files and task statuses

```text
.taskboard/
├── config.json
├── tasks/       # default Board tasks
├── events.jsonl # default Board append-only activity history
└── boards/
    ├── frontend/
    │   ├── tasks/
    │   └── events.jsonl
    └── research/
        ├── tasks/
        └── events.jsonl
```

Computed task statuses:

- `DONE`: explicitly completed.
- `BLOCKED`: explicitly blocked via `block`.
- `IN_PROGRESS`: marked in progress via `doing`.
- `WAITING`: has an unfinished dependency.
- `READY`: available for assignment or self-assignment.

An `assign` sets the task’s single current assignee without changing its state. `add --self` and `assign --self` explicitly assign a task to the current session. `doing` atomically assigns an unassigned task to the current session and starts it; it refuses if another session is assigned. If a task has an assignee, only that assignee may start or update it. `handoff` changes the assignee to the recipient and returns the task to `READY` (or `WAITING` if dependencies remain). `unassign` clears the assignee and returns an in-progress task to `READY`/`WAITING`; only the current assignee may do this normally, while the Coordinator can use `--force`. Reassignment requires `--force`.

## Configuration & automatic context sync

Every task change (`add`, `assign`, `unassign`, `doing`, `done`, `block`, `unblock`, `note`, `dep add`, `handoff`) automatically updates the configured context files between `<!-- TASKBOARD:START -->` and `<!-- TASKBOARD:END -->`, preserving all surrounding content.

Configuration is loaded in three layers (project overrides global, optional Board config overrides project; `harness_env` maps are merged):
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

- Atomic file replacement and an OS-level lock per Board serialize CLI writers on a local filesystem.
- Handoffs and SIDs are coordination records, not process control; Taskboard does not start, stop, or message external Agent processes.
- Human edits to task Markdown are supported; manual edits to `events.jsonl` are not recommended.
