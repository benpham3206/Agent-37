# Workspace routing

## Canonical locations

- Active project: `D:\Codex\2026-08-26\plea`
- Prime Agent session state: `D:\Codex\2026-08-26\prime-agent\sessions`
- Prime Agent temporary files: `D:\Codex\2026-08-26\prime-agent\temp`
- Prime Agent artifacts: `D:\Codex\2026-08-26\prime-agent\artifacts`
- Per-session pads: `D:\Codex\2026-08-26\prime-agent\pads\<session-id>\pad.md`
- Existing C: copy: rollback/reference only until it is manually retired

## Prime Agent

Launch new Prime sessions through:

```powershell
& 'D:\Codex\2026-08-26\plea\tools\prime-agent-on-d.ps1'
```

The wrapper supplies the D: project and session paths and routes child-process
temporary files to D:. It intentionally rejects attempts to override `--cwd`
or `--session-dir`, so a retry cannot silently put a new session back on C:.
It also creates a new owned pad for each new Prime session and exposes its path
through `PRIME_PROJECT_PAD`. Use `--project-pad <pad.md>` when deliberately
resuming a known pad; `--continue` selects the newest Prime pad.

The pad catalog is not a shared mutable index. `tools/session_pad.py list`
derives it from each session's metadata, so sessions can read one another
without racing to update one file. Writes require the pad owner and an
explicit non-conversational reason.

## Codex and delegated work

New Codex commands and delegated tasks should use the D: project root as their
working directory. Delegated artifacts belong below the D: project `work`
directory. Existing C: task worktrees are not moved during a running turn; they
are copied only when an explicit, recoverable migration is needed.

For a delegated Codex task, register a pad with the returned task/thread ID:

```powershell
python D:\Codex\2026-08-26\plea\tools\session_pad.py new `
  --root D:\Codex\2026-08-26\prime-agent\pads `
  --actor codex --session-id <task-or-thread-id>
```

Include the resulting `pad.md` path in the delegated prompt. The Codex task
API does not expose a project hook that can auto-create a file after task
creation, so the coordinator performs this one explicit registration step. If
the coordinator did not register it, the project `AGENTS.md` fallback creates
a Codex-owned pad on the task's first substantive turn.

## Boundary

This routing policy covers this project and Prime Agent's child process. It does
not claim that every Codex, Windows, Minecraft, or launcher cache has moved off
C:. Those global caches need separate inspection and an explicit migration plan.
