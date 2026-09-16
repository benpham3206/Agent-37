# Worker task

Fill this out before assigning implementation work to a worker.

## Goal

State one observable outcome.

## Allowed scope

- List the files or subsystem the worker may change.

## Allowed capabilities

- Filesystem: state the allowed scope or `none`.
- Network: state the allowed scope or `none`.
- Secrets: state the allowed scope or `none`.
- Tools: list allowed tools or commands.
- Deployment: state the allowed scope or `none`.
- Destructive actions: state the allowed scope or `none`.

Anything not listed is denied.

## Must preserve

- List interfaces, invariants, compatibility requirements, and security boundaries that must not change.

## Do not

- Write or modify tests.
- Change architecture unless the architect expands the task.
- Refactor unrelated code.
- Add dependencies unless the architect approves them.
- Broaden the task to adjacent improvements.

## Quality bar

- State the concrete properties that separate merely functional work from work worth keeping.

## Acceptance criteria

- List observable conditions that define success.

## Evidence

Prove the acceptance criteria with the simplest reliable evidence. Run existing checks that apply. Do not create or modify tests.

## Escalate when

Stop and report the constraint when the task requires work outside the allowed scope, needs an unlisted capability, conflicts with an invariant, or requires an architecture change.
