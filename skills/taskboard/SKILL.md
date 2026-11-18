---
name: taskboard
description: A shared task ledger for coordinating multi-step, parallel, or cross-session coding-agent work. (MANDATORY) ALWAYS use this skill before starting or resuming work (check `list`/`status`, verify assignment, start with `doing`), when adding dependencies or waiting for task states/events (`dep add` / `wait` / `watch-next`), when recording progress notes or blockers (`note` / `block`), when handing off or completing tasks (`handoff` / `done`), or when searching past task history (`search`).
---

# Taskboard

> CLI entrypoint: `python <skill_dir>/scripts/taskboard` (abbreviated as `taskboard` below). The default Board is selected automatically; `--board NAME` is optional and only needed when working with a named Board. It is a global option and must appear before the subcommand.

## Task statuses

- `READY`: no unfinished dependencies; available to be assigned or self-assigned with `taskboard doing`.
- `IN_PROGRESS`: marked in progress via `taskboard doing`.
- `WAITING`: has unfinished `depends_on` prerequisites; automatically becomes `READY` once all prerequisites are `DONE`.
- `BLOCKED`: explicitly blocked via `taskboard block`; restore with `taskboard unblock`.
- `DONE`: completed.

## Core workflow

Use the default Board for ordinary task tracking. You do not need to specify a Board on every command.

1. **Inspect & create**: Run `taskboard list`, `taskboard status`, or `taskboard search` to inspect existing work. Create a task with `taskboard add "Short title" [--desc "Scope or context"] [--self]`.
2. **Start & record progress**: Start a ready task with `taskboard doing TASK_ID`. `doing` atomically assigns an unassigned task to the current Harness + Session and starts it. If it is assigned to another Session, the command refuses. Record progress with `taskboard note TASK_ID "What was done"`; inspect details with `taskboard show TASK_ID`.
3. **Dependencies, task wait, and Board watch**:
   - `taskboard dep add TASK_ID --needs OTHER_TASK_ID`: add a prerequisite dependency.
   - `taskboard wait TASK_ID [--until done|doing|ready|waiting|blocked] [--timeout SECONDS]`: wait for one task to reach a state. The default target is `done`; already-satisfied conditions return immediately.
   - `taskboard watch-next [--event task.created] [--timeout SECONDS]`: listen to events across the selected Board. With no `--board`, this means the default Board. `watch-next` waits for one matching Board event and then exits; it has no task-ID or state-condition mode. Event watches start at invocation time; `--since CURSOR` resumes from a returned JSON cursor.
   - `taskboard dep add TASK_ID --needs OTHER_TASK_ID --wait [--timeout SECONDS]`: add the dependency, then wait for the prerequisite to become done.
4. **Block, finish & hand off**:
   - Record a blocker with `taskboard block TASK_ID --reason "Reason"`; clear it with `taskboard unblock TASK_ID`.
   - Complete a task with `taskboard done TASK_ID [--note "Summary"]`.
   - Assign a task with `taskboard assign TASK_ID --self`, or assign it to another session with `taskboard assign TASK_ID --to REAL_SID --to-harness HARNESS`. Reassignment requires `--force`.
   - Clear an assignment with `taskboard unassign TASK_ID`. An in-progress task returns to `READY`/`WAITING`.
   - Hand off a task with `taskboard handoff TASK_ID --to REAL_SID [--to-harness NAME] [--note "Handoff context"]`.

For a named Board, add `--board NAME` before the subcommand, for example `taskboard --board frontend list`. Do this only when the task belongs to that named Board; otherwise omit it and use the default.

## Search syntax (`taskboard search`)

Powered by zero-dependency multi-field BM25F scoring (`id` > `title` > `blocked_reason` > Markdown body > metadata), with automatic `camelCase`/`snake_case` splitting, CJK bigrams, and fuzzy fallback (`--exact` disables fuzzy matching):

- **Boolean & phrases**: space-separated terms use `AND`; supports `OR`, quoted phrases `"exact match"`, and `-exclude` (e.g. `taskboard search oauth login -legacy`). Add `--board NAME` before `search` only when searching a named Board.
- **Inline filters**: `status:READY,IN_PROGRESS`, `harness:opencode`, `sid:xxx`, `task:t-xxxx`, `type:task|event`, `since:YYYY-MM-DD`, `before:YYYY-MM-DD` (usable with or without keywords).
- **Flags**: `--tasks-only`, `--events-only`, `--status`, `--harness`, `--sid`, `--since`, `--limit N` (default `20`, `0` for all), `--json`.

## Multi-agent patterns

Taskboard is a shared task ledger, not an Agent runtime. It does not launch Agents or guarantee that a Session is alive. Choose the coordination pattern that fits the work; these are patterns, not mandatory Coordinator/Worker roles.

### 1. Directed delegation

One Agent (or a human) creates scoped tasks, optionally records dependencies, and assigns tasks to specific Sessions. The receiving Sessions use the task IDs to inspect and update their work. Use `assign`, `handoff`, and `wait` when explicit ownership and completion tracking matter.

### 2. Shared task pool

Tasks are added to a common Board without pre-assigning every item. Available Agents inspect the Board and take suitable tasks with `doing` to atomically take an unassigned task, or explicitly use `assign TASK_ID --self` to claim it before starting. This is useful when the available Agents or their capacity are not known in advance.

### 3. Event-driven intake / standing watcher

An Agent can watch a Board for work that appears asynchronously: tasks added by a user, another Agent, or an external integration. Run `taskboard watch-next` without an event filter to observe all new Board events, or use `--event task.created` to focus on newly created tasks. When an event arrives, inspect the task and decide whether to take it, assign it, or leave it for another consumer. The watcher is not itself a scheduler and does not claim or execute tasks automatically.

For supported Harnesses, run `watch-next` in the Harness's **background execution mode**, not as a foreground tool call that occupies the Agent. Retain the process/session handle and after the event is handled and the resulting work is finished, invoke `watch-next` again to wait for the next event. Do not leave it running as a permanent loop inside a single foreground Agent call. Do not assume shell `&` works in every Harness.

Example (default Board):

```bash
taskboard watch-next --json
```

Example (a named Board):

```bash
taskboard --board intake watch-next --event task.created --json
```

A CLI `add` creates both the task Markdown and its `task_created` event, so no Markdown filesystem watcher is needed. External integrations should create tasks through the CLI (or otherwise emit compatible Board events) if they need to trigger a watcher; direct manual edits to task Markdown do not emit events. `watch-next` only reports one event per invocation. It does not launch Agents, monitor Session liveness, or automatically reassign abandoned work. Assignments do not expire; recovery from a crashed or unavailable assignee is an explicit reassignment decision.

### Board boundaries

- Every task belongs to exactly one Board. Task IDs are scoped to that Board.
- Dependencies are Board-local; use one Board for tasks that need dependency relationships.
- The default Board preserves the existing `.taskboard/tasks/` layout. Named Boards use `.taskboard/boards/NAME/`.
- `--board NAME` is optional. Omit it for the default Board; use it only when intentionally selecting a named Board. When sharing a task reference across Agents, include the Board name only if it is not the default Board.

## Automatic context board sync

- Every task change (`add`, `assign`, `unassign`, `doing`, `done`, `block`, `unblock`, `dep add`, `handoff`) automatically updates the configured context files for the selected Board—no manual `taskboard sync` needed. The generated heading names the Board. Commands without `--board` operate on the default Board.
- Target files are configured as an array in `.taskboard/config.json (or global `scripts/config.json`)` under `context_file` (default `["AGENTS.md"]`, e.g. `["AGENTS.md", "CLAUDE.md"]`). Edits to `config.json` take effect immediately without re-running `init`; set `"auto_sync": false` or `"context_file": []` to disable.
- Only the region between `<!-- TASKBOARD:START -->` and `<!-- TASKBOARD:END -->` is replaced, preserving all surrounding content. Use `taskboard sync --dry-run` or `taskboard context` to preview the default Board; add `--board NAME` before the command to preview a named Board.

## Session identity

`doing`, `done`, `block`, `handoff`, `assign`, and `unassign` automatically detect both the active Harness type and session ID:

Supported out of the box: Codex, Claude Code, OpenCode, DeepSeek Harness, Pi, Antigravity / Gemini CLI, Hermes Agent, Goose, OpenClaw, Qoder, Cursor, and Kiro.

You can also customize `harness_env` in `.taskboard/config.json` (or global `scripts/config.json`) or pass `--harness NAME --sid REAL_SID` explicitly. For `assign --to` and `add --to`, provide both `--to SID` and `--to-harness HARNESS`; assignees are identified by the pair, not by SID alone.
