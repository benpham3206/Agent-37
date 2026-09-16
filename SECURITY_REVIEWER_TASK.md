# Security reviewer task

Fill this out before assigning a focused security review.

## Goal

State the trust, authority, or security property the reviewer must evaluate.

## Review scope

- List the changed trust boundaries, identities, privileges, secrets, external inputs, dependencies, deployment paths, or destructive capabilities in scope.

## Allowed capabilities

- Filesystem: read project files; write only the designated review output.
- Network: state the allowed scope or `none`.
- Secrets: `none` unless access is required for inspection and explicitly granted.
- Tools: list allowed inspection or security commands.
- Deployment: `none` unless explicitly required.
- Destructive actions: `none`.

Anything not listed is denied.

## Must check

- Whether authority expanded and whether the expansion is necessary.
- Whether untrusted data can cross a boundary without validation.
- Whether one compromised agent, tool, integration, or service can move laterally beyond its required scope.
- Whether credentials and destructive capabilities remain narrowly scoped.
- Whether recovery or higher authority stays outside ordinary agent reach when practical.

## Do not

- Do not write or modify code or tests.
- Do not broaden the review into unrelated security work.
- Do not approve risk because an agent or service is trusted by name.
- Do not propose controls that cost more complexity than the risk justifies.

## Quality bar

- State the security properties that must hold and the complexity budget the controls must respect.

## Findings

Return only material security findings. State the affected boundary, the authority or data at risk, the consequence, and the smallest constraint that would close the gap. If there are no material findings, return a clean review.

## Evidence

Support each finding with direct repository, configuration, runtime, or interface evidence.

## Escalate when

Return the issue to the architect when the fix changes trust architecture, identity design, deployment authority, external dependencies, or recovery strategy.
