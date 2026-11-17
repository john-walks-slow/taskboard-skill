---
name: taskboard
description: A shared task ledger for coordinating multi-step, parallel, or cross-session coding-agent work. (MANDATORY) ALWAYS use this skill before starting or resuming work (check `list`/`status`, verify assignment, start with `doing`), when adding dependencies or waiting for task states/events (`dep add` / `wait` / `watch`), when recording progress notes or blockers (`note` / `block`), when handing off or completing tasks (`handoff` / `done`), or when searching past task history (`search`).
---

# Taskboard

> CLI entrypoint: `python <skill_dir>/scripts/taskboard` (abbreviated as `taskboard` in examples below). Use `taskboard --board NAME <command>` to select a non-default Board; the global option goes before the command.

## Task statuses

- `READY`: no unfinished dependencies; available for Coordinator assignment or self-assignment with `taskboard doing`.
- `IN_PROGRESS`: marked in progress via `taskboard doing`.
- `WAITING`: has unfinished `depends_on` prerequisites; automatically becomes `READY` once all prerequisites are `DONE`.
- `BLOCKED`: explicitly blocked via `taskboard block`; restore with `taskboard unblock`.
- `DONE`: completed.

## Core workflow

1. **Inspect & search**: Run `taskboard --board BOARD list`, `taskboard --board BOARD status`, or `taskboard --board BOARD search` to check existing work; create a new task with `taskboard --board BOARD add "Short title" [--desc "Scope or context"] [--claim]`.
2. **Take & record progress**: Start the assigned ready task with `taskboard --board BOARD doing TASK_ID`. If it has no assignee, `doing` atomically assigns it to the current Harness + Session and starts it. If it is assigned to another Session, the command refuses. Record concise progress summaries or key findings with `taskboard --board BOARD note TASK_ID "What was done"`; inspect them anytime via `taskboard --board BOARD show TASK_ID`.
3. **Dependencies, task wait, and Board watch**:
   - `taskboard --board BOARD dep add TASK_ID --needs OTHER_TASK_ID`: add a prerequisite dependency.
   - `taskboard --board BOARD wait TASK_ID [--until done|doing|ready|waiting|blocked] [--timeout SECONDS]`: wait for one specific task to reach a state. The default target is `done`; already-satisfied conditions return immediately.
   - `taskboard --board BOARD watch [--event task.created] [--timeout SECONDS]`: listen to events across the entire selected Board. `watch` has no task-ID or state-condition mode. Event watches start at invocation time; `--since CURSOR` resumes from a returned JSON cursor.
   - `taskboard --board BOARD dep add TASK_ID --needs OTHER_TASK_ID --wait [--timeout SECONDS]` adds the dependency, then uses `wait OTHER_TASK_ID --until done`.
4. **Block, finish & hand off**:
   - Record a blocker: `taskboard --board BOARD block TASK_ID --reason "Reason"`; clear it with `taskboard --board BOARD unblock TASK_ID`.
   - Complete a task: `taskboard --board BOARD done TASK_ID [--note "Summary"]`.
   - Assign a task: `taskboard --board BOARD assign TASK_ID --claim`, or `taskboard --board BOARD assign TASK_ID --to REAL_SID --to-harness HARNESS`. Reassignment requires `--force`; use it only when acting as Coordinator.
   - Clear an assignment: `taskboard --board BOARD unassign TASK_ID`; only the current assignee can do this without `--force`. The Coordinator may use `--force`. An in-progress task returns to `READY`/`WAITING`.
   - Hand off a task: `taskboard --board BOARD handoff TASK_ID --to REAL_SID [--to-harness NAME] [--note "Handoff context"]`; this changes the assignee directly and returns it to `READY`/`WAITING` for the recipient.

## Search syntax (`taskboard search`)

Powered by zero-dependency multi-field BM25F scoring (`id` > `title` > `blocked_reason` > Markdown body > metadata), with automatic `camelCase`/`snake_case` splitting, CJK bigrams, and fuzzy fallback (`--exact` disables fuzzy matching):

- **Boolean & phrases**: space-separated terms use `AND`; supports `OR`, quoted phrases `"exact match"`, and `-exclude` (e.g. `taskboard --board BOARD search oauth login -legacy`).
- **Inline filters**: `status:READY,IN_PROGRESS`, `harness:opencode`, `sid:xxx`, `task:t-xxxx`, `type:task|event`, `since:YYYY-MM-DD`, `before:YYYY-MM-DD` (usable with or without keywords).
- **Flags**: `--tasks-only`, `--events-only`, `--status`, `--harness`, `--sid`, `--since`, `--limit N` (default `20`, `0` for all), `--json`.

## Multi-agent coordination

Replace `BOARD` with the Board name supplied by the Coordinator (or omit it only when using the project default). The global `--board` option must precede the subcommand.

Taskboard is the shared coordination ledger, not an Agent runtime. It does not launch Workers or guarantee that a Session is alive. It stores one current assignee per task and enforces assignment changes atomically under the Board lock. This is not a lease: assignments do not expire automatically when a Worker crashes. The Coordinator is responsible for assigning each task to one Worker and passing the exact Board and Task ID.

### Coordinator

Before starting or delegating parallel work:

1. Inspect the selected Board with `taskboard --board BOARD list` and `taskboard --board BOARD status`; search existing tasks before creating duplicates.
2. Decompose the goal into independently verifiable tasks. Give each task a clear scope and acceptance criteria in `--desc`.
3. Create tasks **before** starting Workers. For example, run `taskboard --board BOARD add "Implement login API" --desc "Acceptance criteria: ..."`; capture the returned TID. Optionally assign at creation with `--to REAL_SID --to-harness HARNESS`, or let the Coordinator assign later. Record dependencies with `taskboard --board BOARD dep add CHILD --needs PARENT`.
4. Assign each task with `taskboard --board BOARD assign TID --to REAL_SID --to-harness HARNESS`, then pass the Worker the Board name and exact TID. Include the task description and relevant dependency context; do not ask Workers to recreate an already-created task.
5. Track progress with `taskboard --board BOARD wait TID --until done`; use Board-level `watch` for new events. Inspect the task and its notes before accepting the result.
6. Create follow-up tasks for newly discovered work rather than silently expanding another Worker’s assignment.

Example delegation brief:

```text
Board: frontend
Task ID: t-xxxxxxxx
This task has already been created. Do not create a duplicate.
Read it with `taskboard --board frontend show t-xxxxxxxx`, then follow this skill.
```

### Worker

When given a TID:

1. Use the specified Board explicitly and read the existing task with `taskboard --board BOARD show TID` before editing anything.
2. Check its status and dependencies. If `WAITING`, block on `taskboard --board BOARD wait TID --until ready`; if `BLOCKED`, stop and report the blocker to the Coordinator. Do not start either state.
3. Mark it `IN_PROGRESS` with `taskboard --board BOARD doing TID`, then record meaningful discoveries and progress with `taskboard --board BOARD note TID "..."`.
4. If blocked, use `taskboard --board BOARD block TID --reason "..."` with a concrete reason. Do not leave a blocked task looking active.
5. On completion, use `taskboard --board BOARD done TID --note "..."` with a concise summary and verification evidence.
6. If ownership must move to another Session, use `taskboard --board BOARD handoff TID --to REAL_SID --note "..."` and include enough context for the receiver.

Do not mark another Worker’s task done or modify unrelated tasks. If additional work is discovered, report it to the Coordinator or create a separately scoped task and link it with a dependency when appropriate. A `DONE` state records the Worker’s completion declaration; it is not independent Coordinator acceptance.

### Board boundaries

- Every task belongs to exactly one Board. Task IDs are scoped to that Board.
- Dependencies are Board-local; use one Board for tasks that need dependency relationships.
- Pass both Board name and TID when delegating. A bare TID is ambiguous when multiple Boards exist.
- The default Board preserves the existing `.taskboard/tasks/` layout. Named Boards use `.taskboard/boards/NAME/`.

### Background Board watcher and task pickup

For the supported Harnesses listed below, **always run `taskboard watch` in the Harness's background execution mode**, never as a foreground tool call that occupies the Agent. Keep a Board watcher running for the Coordinator; when it exits after receiving an event, process the event and restart the watcher. Use the Harness's background-process/task facility, retain its process/session handle, and check that it is still alive. Do not assume that merely appending `&` works in every Harness.

Example watcher command (run it through the Harness background facility):

```bash
taskboard --board BOARD watch --event task.created --json
```

The Coordinator consumes the returned event, reads the task with `show`, checks its status/dependencies, assigns it to a Worker with `assign`, then restarts the watcher. A CLI `add` creates both the task Markdown and its `task_created` event, so no Markdown filesystem watcher is needed. Direct manual edits to task Markdown do not emit events and therefore do not trigger automatic pickup; create dispatchable tasks through the CLI.

`watch` only reports Board events. It does not launch Agents or monitor Worker liveness. Assignment is exclusive at the Taskboard data level: a task has one current assignee, and concurrent assignment attempts are serialized by the Board lock. There are no leases, heartbeats, or automatic reassignment after a Worker crashes; the Coordinator must explicitly reassign abandoned work with `assign --force`. `wait` is a foreground, task-specific state wait and is not the Board watcher.

## Automatic context board sync

- Every task change (`add`, `assign`, `unassign`, `doing`, `done`, `block`, `unblock`, `dep add`, `handoff`) automatically updates the configured context files for the selected Board—no manual `taskboard sync` needed. The generated heading names the Board.
- Target files are configured as an array in `.taskboard/config.json (or global `scripts/config.json`)` under `context_file` (default `["AGENTS.md"]`, e.g. `["AGENTS.md", "CLAUDE.md"]`). Edits to `config.json` take effect immediately without re-running `init`; set `"auto_sync": false` or `"context_file": []` to disable.
- Only the region between `<!-- TASKBOARD:START -->` and `<!-- TASKBOARD:END -->` is replaced, preserving all surrounding content. Use `taskboard --board BOARD sync --dry-run` or `taskboard --board BOARD context` to preview.

## Session identity

`doing`, `done`, `block`, `handoff`, `assign`, and `unassign` automatically detect both the active Harness type and session ID:

Supported out of the box: Codex, Claude Code, OpenCode, DeepSeek Harness, Pi, Antigravity / Gemini CLI, Hermes Agent, Goose, OpenClaw, Qoder, Cursor, and Kiro.

You can also customize `harness_env` in `.taskboard/config.json` (or global `scripts/config.json`) or pass `--harness NAME --sid REAL_SID` explicitly. For `assign --to` and `add --to`, provide both `--to SID` and `--to-harness HARNESS`; assignees are identified by the pair, not by SID alone.
