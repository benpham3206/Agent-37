# Research task

Fill this out before assigning research that should inform a project decision.

## Decision question

State the decision the research must help make.

## Research scope

- List the topics, systems, time range, sources, or alternatives in scope.

## Allowed capabilities

- Filesystem: state the allowed scope or `none`.
- Network: state the allowed scope or `none`.
- Secrets: `none` unless explicitly required.
- Tools: list allowed research or inspection tools.
- Deployment: `none`.
- Destructive actions: `none`.

Anything not listed is denied.

## Must preserve

- Keep facts, inferences, unknowns, and recommendations distinct.
- Preserve material contradictory evidence and uncertainty.

## Do not

- Do not implement the proposed fix.
- Do not change code, tests, architecture, or production state unless reassigned to another role.
- Do not treat source count, reading volume, or tool calls as research quality.
- Do not hide uncertainty to make a recommendation sound stronger.

## Quality bar

- State what makes the result decision-ready: directness, source quality, material uncertainty, and a useful proposal when supported.

## Output

Return the answer to the decision question, the evidence that changes the decision, material uncertainty, and a proposed fix when the evidence supports one.

## Handoff

The researcher proposes; the architect reviews; the user decides whether implementation proceeds. After approval, the architect chooses the implementation path and assigns bounded worker tasks.

## Evidence

Use traceable evidence that directly supports the decision. Prefer primary or authoritative sources when they materially improve confidence.

## Escalate when

Stop and report the gap when available evidence cannot support the requested decision, required access is missing, or research would cross an ungranted boundary.
