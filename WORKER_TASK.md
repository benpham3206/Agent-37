# Worker task

Complete this before assigning implementation work to a worker.

## Goal

State one observable outcome.

## Allowed scope

- List the files or subsystem the worker may change.

## Allowed capabilities

- Filesystem: state scope or `none`.
- Network: state scope or `none`.
- Secrets: state scope or `none`.
- Tools: list allowed tools or commands.
- Deployment: state scope or `none`.
- Destructive actions: state scope or `none`.

Deny anything not listed.

## Must preserve

- List interfaces, invariants, compatibility requirements, and security boundaries that must not change.

## Do not

- Write or modify tests.
- Change architecture unless the architect expands the task.
- Refactor unrelated code.
- Add dependencies unless the architect approves them.
- Broaden the task to adjacent improvements.

## Quality bar

- State concrete properties required for work worth keeping.

## Acceptance criteria

- List observable conditions that define success.

## Evidence

Prove acceptance with the simplest reliable evidence and applicable existing checks. Do not create or modify tests.

## Escalate when

Stop and report the constraint when the task requires work outside the allowed scope, needs an unlisted capability, conflicts with an invariant, or requires an architecture change.
