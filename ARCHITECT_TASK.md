# Architect task

Fill this out before assigning project-wide reasoning or a cross-cutting decision to an architect.

## Goal

State the decision or system outcome the architect must produce.

## Decision scope

- List the systems, interfaces, constraints, or tradeoffs the architect may change or evaluate.

## Allowed capabilities

- Filesystem: state the allowed scope or `none`.
- Network: state the allowed scope or `none`.
- Secrets: state the allowed scope or `none`.
- Tools: list allowed tools or commands.
- Deployment: state the allowed scope or `none`.
- Destructive actions: state the allowed scope or `none`.

Anything not listed is denied.

## Must preserve

- List project goals, invariants, compatibility requirements, trust boundaries, and user constraints that must not change.

## Do not

- Do not absorb worker implementation.
- Do not change requirements to fit a preferred architecture.
- Do not add a subsystem, dependency, policy layer, or abstraction when the existing system can satisfy the constraints.
- Do not approve your own implementation.

## Quality bar

- State the architectural qualities the result must preserve, such as clarity, locality, replaceability, coherence, or visual/product quality when relevant.

## Decision criteria

- List the constraints and tradeoffs that must determine the decision.

## Output

Return the chosen direction, the alternatives rejected for material reasons, any boundary or interface changes, and the worker assignments needed to implement it.

## Implementation gate

When research proposes a fix, review the proposal and make a recommendation. Present the implementation decision to the user. After the user decides to proceed, choose the implementation path and assign bounded worker tasks.

## Evidence

Prove the recommendation satisfies the stated constraints with the simplest reliable evidence. Separate known facts from assumptions.

## Escalate when

Stop and report the conflict when the goal, constraints, authority, or available evidence do not support a safe decision.
