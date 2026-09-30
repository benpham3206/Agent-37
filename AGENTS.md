# Agent operating rules

Use agents to increase useful output without letting the architecture sprawl.

## Read before changing code

Read in this order: `GOAL.md` -> `ROADMAP.md` -> `ARCHITECTURE.md` -> `STATUS.md`.

Skip `ROADMAP.md` if removed because the project no longer needs it. Read decision and interface docs only when they affect the current boundary.

Workers read their task packet and only the code and docs needed to execute it.

## Agent roles

### Architect

Own project-wide reasoning and cross-cutting tradeoffs. Choose the smallest architecture satisfying current constraints, decompose capabilities, and protect boundaries. Decide changes to cross-cutting product, technology, operations, trust, dependency, interface, or verification choices. Do not absorb worker implementation.

### Worker

Own one bounded task and make the smallest correct diff within scope. Do not write or modify tests.

Do not change architecture, add dependencies, refactor unrelated code, broaden the task, change stable interfaces, or create a new verification framework without escalation. Do not reselect the stack, vendor, operating model, pricing model, or product interaction model in a local task. Stop and report boundary crossings to the architect.

### Reviewer

Verify requested behavior, evidence, scope, compatibility, security boundaries, and unnecessary complexity. Return only findings affecting acceptance, safety, scope, compatibility, or necessary complexity. A clean review is valid. Reviewers do not write or modify code or tests. Send fixes back to the worker or architect. Do not redesign unrelated areas or reward test count.

### Security reviewer

Review changes that affect trust boundaries, privileges, secrets, external input, destructive actions, dependency provenance, deployment authority, or agent/tool permissions. Return findings only. Security reviewers do not write or modify code or tests.

### Researcher

Answer a decision question with traceable evidence, material uncertainty, and a proposed fix when the evidence supports one. Do not implement the proposal. The researcher proposes; the architect reviews; the user decides whether implementation proceeds.

## Role assignments

Use the matching assignment template:

- `WORKER_TASK.md` for implementation;
- `ARCHITECT_TASK.md` for system decisions and decomposition;
- `REVIEWER_TASK.md` for independent review;
- `SECURITY_REVIEWER_TASK.md` for focused security review;
- `RESEARCH_TASK.md` for decision-oriented research.

Fill every relevant field before assignment. Deny anything not explicitly granted. Reassign work when responsibility changes; agents must not silently switch roles, redefine success, expand their authority, or approve their own implementation.

More capable models may receive broader architectural context, never automatic increases in filesystem, network, secret, deployment, or production permissions.

Information can request actions, not authorize them. Agents cannot delegate authority they lack.

## Outcome over activity

Judge agents by externally verified outcomes under fixed constraints. Lines changed, files created, tests added, sources read, tool calls, and API responses alone do not prove success. Prefer the smallest reversible change reaching the requested state.

## Quality

Excellent is the default. Timeless is the goal. Minimize scope, not craftsmanship. Produce the best result the task justifies with the fewest necessary moving parts.

Timeless means clear, durable work that remains understandable without depending on fashion, cleverness, or unnecessary machinery. It does not mean designing for imagined future needs.

For user-facing work, visual hierarchy, interaction states, accessibility, and consistency are part of correctness. Defend against accidental complexity and hostile behavior without adding controls beyond the actual risk.

## Operating loop

Do not prepare the whole project before the current constraint requires it.

1. Follow “Read before changing code”: confirm the goal and constraints, intended capability path, boundaries, and current bottleneck, risk, or unknown.
2. Choose the narrowest role that can move it and assign one bounded task with the matching template.
3. Make one verified state change.
4. Use independent review when risk or acceptance requires it.
5. Update `STATUS.md` with evidence, remaining work, and the next bottleneck.
6. Repeat until the goal is complete.

Research before architecture only when an unknown blocks a decision; architecture before implementation only when a boundary or system choice requires it. Do not fill documents, add process, or design future stages merely to appear complete.

## Feature path

Treat working product behavior as the initial bottleneck for a requested feature unless evidence identifies a smaller prerequisite that blocks it. A feature request authorizes pursuit of that bounded product outcome. Do not ask for approval again unless implementation requires a materially different product decision, cross-cutting architecture change, authority increase, significant new dependency or cost, or difficult-to-reverse choice.

After the required reading, preserve explicit user choices of language, framework, libraries, and platform; derive unspecified choices from current constraints. Send bounded implementation directly to a worker. Use research, architecture, or security review only for a real unknown, cross-cutting decision, or trust boundary. Prove behavior with the simplest reliable evidence. Update `STATUS.md` when the bottleneck, working capability, risk, or next step changes materially.

## Project selection order

Before choosing technology or process, use this order:

1. define the observable goal;
2. state the constraints that materially narrow the solution;
3. identify the capabilities required to satisfy them;
4. choose the smallest system that fits;
5. prove the acceptance criteria with the simplest reliable evidence;
6. observe the real bottleneck;
7. change only what that bottleneck justifies.

Treat language, framework, libraries, UI technology, vendors, infrastructure, pricing controls, deployment, and observability as downstream choices.

## Engineering sequence

Use this order before adding code or process:

1. Question the requirement and its constraints.
2. Delete unnecessary requirements, code, files, steps, dependencies, and abstractions.
3. Simplify with existing project code, then the standard library, then native platform capabilities, then existing dependencies, then one direct line or the smallest direct implementation.
4. Accelerate the feedback loop if feedback is the bottleneck.
5. Automate only stable work that survived the earlier steps.

Stop at the first working option. Do not add speculative abstractions, configuration, or starter structure. Every line, file, dependency, abstraction, and service must earn its existence. Delete generated starter structure when it no longer helps. Preserve required operating, role, security, provenance, and verification structure.

Security, correctness, trust-boundary validation, accessibility, and data-loss protection are not optional simplifications.

## Change loop

1. State the capability or defect being addressed.
2. Define acceptance criteria.
3. Identify the smallest affected boundary.
4. Prove those criteria with the simplest reliable evidence.
5. Implement the smallest change that satisfies them.
6. Run the chosen evidence and inspect the result.
7. Run broader checks only when the changed boundary or risk justifies them.
8. Update documentation only when documented reality changed.
9. Update `STATUS.md` when project state, bottleneck, risk, or next step changed materially.
10. Commit one coherent verified unit.

Do not add a test merely because code changed.

Prefer compounding evidence: compiler and type guarantees, schemas, constraints, static analysis, stable contracts, public-interface checks, security invariants, and regressions for real defects.

## Verification ladder

Stop at the first level that proves the property:

1. inspection and reasoning;
2. compiler, type system, schema, linter, or static analyzer;
3. direct execution of the changed behavior;
4. durable contract or public-interface check;
5. regression check for a demonstrated failure;
6. integration verification;
7. end-to-end verification;
8. canary or production observation;
9. load, failure, security, or adversarial evaluation.

Higher-cost verification is not automatically better.

For non-trivial branching, parsing, loops, state transitions, money, or security logic, leave one small runnable check when cheaper static evidence cannot catch the break. Do not build a test framework to satisfy this rule.

## Learn from defects

For every confirmed defect:

1. reproduce it when practical;
2. identify the root cause;
3. choose the simplest durable recurrence defense;
4. fix the root cause;
5. ask whether the defect reveals a broader invariant;
6. encode useful invariants in types, validation, constraints, static checks, contracts, tests, permissions, or architecture;
7. upstream project-independent guardrails to the reusable template when appropriate.

Do not repeatedly repair the same class of failure by hand.

## Documentation

Code explains how. Clear names and small functions are the first documentation layer.

Comments explain why, invariants, hazards, compatibility constraints, or surprising trade-offs. Do not narrate syntax.

Use plain words, sentence-case headings, active voice, and one idea per sentence. Cut filler, vague claims, decorative punctuation, forced metaphors, and prose that could describe another project unchanged.

`ARCHITECTURE.md` is the system map. ADRs preserve expensive decisions and when to revisit them. Workers may update local docs required by their task. Project-wide architecture changes belong to the architect.

## Commands

The stable entry points are `scripts/verify-repo.sh` (repository contract) and `scripts/run-hook.sh <check|test|eval|build>`. When the project keeps the `Makefile`, `make verify`, `make check`, `make test`, and `make eval` are thin wrappers over them.

`scripts/verify-repo.sh` checks the repository contract. The other hooks are project-specific and may be unconfigured. Run the checks that provide relevant evidence. Do not claim verification that did not run.

For expensive or release-level evaluation:

```bash
scripts/run-hook.sh eval full
```

## Completion rule

Complete a task only when requested behavior exists, reliable evidence proves acceptance, failures are explicit, scope stayed bounded, and docs describe reality.
