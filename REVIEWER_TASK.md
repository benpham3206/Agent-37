# Reviewer task

Complete this before assigning an independent review.

## Goal

State the change or decision under review.

## Review scope

- List the diff, artifact, subsystem, task contract, or evidence the reviewer may inspect.

## Allowed capabilities

- Filesystem: read project files; write only the designated review output.
- Network: state scope or `none`.
- Secrets: `none` unless explicitly required.
- Tools: list allowed inspection or verification commands.
- Deployment: `none` unless explicitly required.
- Destructive actions: `none`.

Deny anything not listed.

## Must check

- Acceptance criteria and observed behavior.
- Scope discipline and preserved invariants.
- Interface and compatibility risks.
- Security or authority changes relevant to the diff.
- Unnecessary complexity that materially affects acceptance or maintenance.

## Do not

- write or modify code or tests.
- change the acceptance criteria.
- redesign unrelated areas.
- create findings to make the review look thorough.

## Quality bar

- State the concrete craft, restraint, and boundary properties the artifact must meet.

## Findings

Return only findings affecting acceptance, safety, scope, compatibility, or necessary complexity. Cite the location or evidence and consequence. Return a clean review if none.

## Evidence

Support each finding with the smallest reliable evidence.

## Escalate when

Return the issue to the architect when resolving it would require a boundary, interface, dependency, trust, or architecture decision.
