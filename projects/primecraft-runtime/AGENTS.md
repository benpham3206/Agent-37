# Project session continuity

For every new session working in this project, use the per-session pad under
`D:\Codex\2026-08-26\prime-agent\pads`. The canonical helper is
`D:\Codex\2026-08-26\plea\tools\session_pad.py`.

- Read the current session pad before substantive work.
- If `PRIME_PROJECT_PAD` is absent, create a Codex-owned pad with
  `python D:\Codex\2026-08-26\plea\tools\session_pad.py new --root D:\Codex\2026-08-26\prime-agent\pads --actor codex` and use the returned path.
- Use `list` and `read` to inspect other sessions' pads when coordinating.
- Write only the current session's pad and only after a non-trivial task
  completion, pivot, verified result, checkpoint, blocker, or handoff.
- Never update a pad for ordinary conversation.
- Keep the Grok-style sections: Intent, 5W1H, Constraints, Goal, Todo, State,
  Checkpoint, Definition of Done, Open, Decisions, Notes, and Turn log.
- Put the rigid session invariants under `Constraints` as an explicit
  `- **Must not break:**` group.
- Keep project, Prime, telemetry, and temporary artifacts on D:.

The pad system separates concurrent writers. Each session owns its own pad;
the directory listing is the shared read view.
