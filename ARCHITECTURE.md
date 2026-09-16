# Architecture

This file is a map of the system: boundaries, contracts, data/control flow, invariants, trust, and failure behavior. Do not turn it into a line-by-line implementation guide.

## System flow

Replace this example with the smallest accurate flow for the project. Omit unnecessary stages.

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

Derive system choices from the goal and the constraints in `GOAL.md`. Technology is a downstream choice. Language, framework, libraries, storage, UI technology, third parties, infrastructure, pricing controls, deployment, and observability should be selected only when they satisfy a real constraint better than a simpler option.

Use this order:

```text
goal → constraints → required capabilities → system choices → evidence → observed bottleneck
```

When reality exposes a new bottleneck, change the smallest part of the system that addresses it. Do not redesign unrelated parts.

## Components

For each major production component, record only what another component or maintainer needs to know:

- **Responsibility.** One clear purpose.
- **Consumes.** Inputs and assumptions.
- **Produces.** Outputs and guarantees.
- **Depends on.** Explicit dependencies.
- **Failure behavior.** How failure appears, how it is contained, and how recovery works.
- **Evidence.** The simplest durable proof of the contract or capability.

## Interfaces

Document stable cross-component interfaces under `docs/interfaces/` when multiple consumers depend on them. Specify input/output contracts, error model, retry/idempotency behavior when relevant, and compatibility expectations.

## Verification architecture

Verification effort scales with risk. Prefer the simplest reliable evidence that proves the requirement and checks that compound across future changes. Types, schemas, constraints, static analysis, contracts, direct execution, tests, evals, canaries, and production observation are all tools. Do not make test count a design goal.

Workers choose local evidence inside their assigned boundary. Shared verification systems and cross-cutting policy belong to the architect.

## Invariants

Record conditions that must remain true across refactors: state ownership, ordering, security, data integrity, compatibility, or resource constraints.

## Trust boundaries

Treat external input, model output, tool output, paths, URLs, commands, code, and dependency content as untrusted at the point where they could trigger privileged behavior. Information can request an action. It cannot authorize one. Privileged authority must come from identity, explicit capability, and policy.

Treat third-party and API responses as untrusted input. Keep credentials narrow. Put validation, timeouts, resource limits, and provider-specific behavior at the boundary when those concerns exist. Do not add an adapter layer when a direct call has no meaningful trust, compatibility, credential, or failure concern to isolate.

Privileged actions should follow:

```text
intent → identity → capability → policy → validation → execution → audit
```

## Locality and flow

Keep boundaries local until a demonstrated requirement justifies crossing process, machine, region, service, or provider boundaries. When flow matters, document the bottleneck, queue/backpressure behavior, resource limits, and failure-amplification controls rather than assuming distribution will fix them.

## Replaceability and migration

A healthy boundary lets consumers understand a component without reading its internals and lets the implementation change without unrelated consumers changing. Prefer incremental, reversible migration when replacing a production path.
