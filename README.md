# taskboard 0.4

A tiny, filesystem-native task ledger for coordinating coding-agent work. It tracks task state and records which real Harness session performed each action. **Session identity is retained; Session lifecycle is not modeled.**

- Tasks are the primary objects.
- The real Harness SID is attached to task events as the actor.
- There are no Session records, active/inactive flags, or start/stop lifecycle commands.
- Dependencies form a directed acyclic graph.
- `events.jsonl` is the append-only activity history.
- Context injection maintains a compact task-board snapshot in `AGENTS.md` or another configured file.

No database server, daemon, MCP server, or third-party Python packages. Requires Python 3.9+.

## Run

```bash
python skills/taskboard/scripts/taskboard init
# Put bin/taskboard on PATH, or create a shell alias:
alias taskboard="python /absolute/path/to/taskboard-skill/skills/taskboard/scripts/taskboard"
```

To use another context file (for example `CLAUDE.md` or `GEMINI.md`):

```bash
taskboard init --context-file AGENTS.md CLAUDE.md
```

## Quick start

Inside a supported Harness Bash tool:

```bash
taskboard add "Normalize URL identity"
taskboard list
# Use the task ID printed by add
taskboard doing t-xxxxxxxx
taskboard status
taskboard done t-xxxxxxxx
```

No `start-session` or `conclude-session` is required. `doing`, `done`, `block`, and `handoff` detect the current real SID automatically and record it as the actor. Creating and listing tasks do not require a Harness identity.

Default real-SID mappings:

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

If auto-detection is unavailable, explicitly pass the real identity:

```bash
taskboard doing t-xxxxxxxx --harness codex --sid REAL_THREAD_ID
```

Taskboard never fabricates a Session ID. If multiple Harness IDs are present, specify `--harness` rather than letting Taskboard guess.

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

`taskboard search` ranks tasks and events using zero-dependency multi-field BM25F scoring (`id` > `title` > `blocked_reason` > Markdown body > `participants`/`depends_on`; event values only, ignoring JSON keys):

```bash
# Multi-word AND, OR, negation, and quoted phrases
taskboard search auth login -legacy
taskboard search '"OAuth login"' OR callback

# Inline or flag filters
taskboard search status:READY,IN_PROGRESS harness:opencode --tasks-only
taskboard search --since 2026-11-01 --limit 10 --json
```

- Splits `camelCase`, `snake_case`, `kebab-case`, and CJK bigrams automatically.
- Falls back to fuzzy matching on typos unless `--exact` is passed.

## Blocking wait

Use `taskboard wait` or `taskboard dep add ... --wait` to block until prerequisite tasks finish:

```bash
# Add dependency and wait for OTHER_TASK_ID to become DONE
taskboard dep add t-bbbbbbbb --needs t-aaaaaaaa --wait

# Wait for one or more tasks to become DONE
taskboard wait t-aaaaaaaa t-cccccccc

# Wait until a task's dependencies are all DONE (no longer WAITING)
taskboard wait t-bbbbbbbb --ready --timeout 120
```

- Waiting polls every 1 second and releases the project lock between polls so other sessions can run `taskboard done` or `taskboard block` without deadlocking.
- `--timeout` is optional.
- If a waited-on task (or a prerequisite under `--ready`) becomes `BLOCKED`, `wait` exits immediately with an error.

## Files and source of truth

```text
.taskboard/
├── config.json
├── tasks/       # one short Markdown record per task
└── events.jsonl # append-only activity history, including actor Harness/SID
```

Task Markdown frontmatter is the canonical current state. The event log records who performed each transition. Task status is computed:

- `DONE`: explicitly completed.
- `BLOCKED`: explicitly blocked.
- `IN_PROGRESS`: explicitly claimed with `taskboard doing`.
- `WAITING`: has an unfinished dependency.
- `READY`: otherwise available.

A handoff records the sender and intended recipient, then returns the task to `READY` (or `WAITING` if dependencies remain). The receiving session claims it with `taskboard doing TASK_ID`.

## Context injection

Every task state change (`add`, `doing`, `done`, `block`, `unblock`, `dep add`, `handoff`) automatically syncs the board snapshot into the configured context file. Only the content between `<!-- TASKBOARD:START -->` and `<!-- TASKBOARD:END -->` is replaced (or appended if missing). Configure the target in project `.taskboard/config.json` or global `skills/taskboard/scripts/config.json` (project overrides global) without re-running `init`:

```json
{ "context_file": ["AGENTS.md", "CLAUDE.md"], "auto_sync": true }
```

Set `"auto_sync": false` (or `"context_file": []`) to disable automatic sync. `taskboard sync [--dry-run]` and `taskboard context` remain available for manual sync or preview.

## Custom Harness

Edit `.taskboard/config.json`:

```json
{
  "harness_env": {
    "codex": ["CODEX_THREAD_ID"],
    "claude-code": ["CLAUDE_CODE_SESSION_ID"],
    "opencode": ["OPENCODE_SESSION_ID"],
    "deepseek-harness": ["DSH_SESSION_ID"],
    "pi": ["PI_SESSION_ID"],
    "antigravity": ["ANTIGRAVITY_SESSION_ID", "GEMINI_SESSION_ID"],
    "hermes": ["HERMES_SESSION_ID"],
    "goose": ["GOOSE_SESSION_ID"],
    "openclaw": ["OPENCLAW_SESSION_ID", "OPENCLAW_SESSION_KEY"],
    "qoder": ["QODER_SESSION_ID"],
    "cursor": ["CURSOR_SESSION_ID", "CURSOR_TRACE_ID"],
    "kiro": ["KIRO_SESSION_ID"],
    "my-harness": ["MY_AGENT_SESSION_ID"]
  }
}
```

`TASKBOARD_HARNESS` plus `TASKBOARD_SID` can also explicitly provide identity to child processes.

## Reliability boundaries

- Atomic file replacement and an OS-level project lock serialize CLI writers.
- Use a local filesystem. Do not assume NFS or cross-machine coordination is safe.
- A real SID identifies an actor; it does not prove that the corresponding Harness process is currently alive.
- Handoffs are events, not process control. Taskboard cannot start, stop, or notify another Agent.
- Search uses pure-Python BM25F ranking over task records and event values, with `difflib` fuzzy fallback.
- Human edits to task Markdown are supported. Manually editing `events.jsonl` is not recommended.
- The event log is append-only by convention, not a tamper-proof audit log.

Taskboard does not store requirements, acceptance criteria, implementation plans, source diffs, or full transcripts. Keep those in the project's existing systems.
