# Security reviewer task

Complete this before assigning a focused security review.

## Goal

State the trust, authority, or security property the reviewer must evaluate.

## Review scope

- List the changed trust boundaries, identities, privileges, secrets, external inputs, dependencies, deployment paths, or destructive capabilities in scope.

## Allowed capabilities

- Filesystem: read project files; write only the designated review output.
- Network: state scope or `none`.
- Secrets: `none` unless access is required for inspection and explicitly granted.
- Tools: list allowed inspection or security commands.
- Deployment: `none` unless explicitly required.
- Destructive actions: `none`.

Deny anything not listed.

## Must check

- Whether authority expanded and whether the expansion is necessary.
- Whether untrusted data can cross a boundary without validation.
- Whether one compromised agent, tool, integration, or service can move laterally beyond its required scope.
- Whether credentials and destructive capabilities remain narrowly scoped.
- Whether recovery or higher authority stays outside ordinary agent reach when practical.

## Do not

- write or modify code or tests.
- broaden the review into unrelated security work.
- approve risk because an agent or service is trusted by name.
- propose controls that cost more complexity than the risk justifies.

## Quality bar

- State the security properties that must hold and the complexity budget the controls must respect.

## Findings

Return only material security findings: affected boundary, authority or data at risk, consequence, and smallest constraint closing the gap. Return a clean review if none.

## Evidence

Support each finding with direct repository, configuration, runtime, or interface evidence.

## Escalate when

Return the issue to the architect when the fix changes trust architecture, identity design, deployment authority, external dependencies, or recovery strategy.
