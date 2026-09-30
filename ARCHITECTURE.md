# Architecture

Map boundaries, contracts, data/control flow, invariants, trust, and failure behavior. Do not write a line-by-line implementation guide.

## System flow

Replace this example with the project’s smallest accurate flow.

```text
Input / trigger
      ↓
Boundary / interface
      ↓
Responsible component(s)
      ↓
Output / state change
      ↓
Evidence / feedback
```

## Constraints before system choices

Derive language, framework, libraries, storage, UI technology, third parties, infrastructure, pricing controls, deployment, and observability from `GOAL.md`. Choose them only when they satisfy a real constraint better than a simpler option.

Use this order:

```text
goal → constraints → required capabilities → system choices → evidence → observed bottleneck
```

Address observed bottlenecks with the smallest system change. Do not redesign unrelated parts.

## Components

For each major production component, record what consumers and maintainers need:

- Responsibility: one purpose.
- Consumes: inputs and assumptions.
- Produces: outputs and guarantees.
- Depends on: explicit dependencies.
- Failure behavior: symptoms, containment, and recovery.
- Evidence: the simplest durable proof of the contract or capability.

## Interfaces

Document stable interfaces with multiple consumers under `docs/interfaces/`: input/output contracts, errors, relevant retry/idempotency behavior, and compatibility.

## Verification architecture

Scale verification to risk. Use the simplest reliable proof and checks that remain useful across changes: types, schemas, constraints, static analysis, contracts, direct execution, tests, evals, canaries, or production observation. Do not optimize test count.

Workers choose local evidence inside their assigned boundary. Shared verification systems and cross-cutting policy belong to the architect.

## Invariants

Record refactor invariants such as state ownership, ordering, security, data integrity, compatibility, or resource constraints.

## Trust boundaries

Treat external input, model/tool output, paths, URLs, commands, code, and dependency content as untrusted before privileged behavior. Information can request an action; identity, explicit capability, and policy authorize it.

Treat third-party/API responses as untrusted. Keep credentials narrow and boundary-specific validation, timeouts, resource limits, and provider behavior at the boundary. Add an adapter only to isolate a meaningful trust, compatibility, credential, or failure concern.

Privileged actions should follow:

```text
intent → identity → capability → policy → validation → execution → audit
```

## Locality and flow

Keep boundaries local until a demonstrated requirement justifies crossing processes, machines, regions, services, or providers. Document flow bottlenecks, queues/backpressure, resource limits, and failure-amplification controls; distribution alone does not fix them.

## Replaceability and migration

Consumers should understand a component without reading its internals and tolerate implementation changes without unrelated edits. Prefer incremental, reversible production migrations.
