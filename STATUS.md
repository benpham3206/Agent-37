# Status

Keep this file current and short. It is the fastest way for a new contributor or architect agent to understand project state.

## Current goal

Name the capability currently being advanced and link to `GOAL.md` when useful.

## Current capability quality

Record the active capability and its current/required level:

- `absent`
- `works`
- `reliable`
- `observable`
- `efficient`
- `resilient`

Not every capability needs the highest level. The goal and risk determine the requirement.

## Working

List capabilities demonstrated by current evidence.

## Failing or missing

List known failures, regressions, unreliable paths, or required capabilities that do not exist.

## Current bottleneck

Name one limiting constraint that most directly blocks the current goal.

## Current constraint pressure

Record only pressure that could change the next decision: user friction, accessibility, queue/backlog, latency, cost, memory/compute, rate limits, vendor limits, operational toil, distribution limits, legal/compliance pressure, team/time limits, or other active constraints. Write `None observed` when there is no meaningful pressure.

## Security and trust risks

Record active trust-boundary, privilege, secret, dependency, destructive-action, or data-handling risks. Write `None known` only when reviewed.

## Manual toil worth automating

Record repeated manual work only after it has become a stable pattern. Do not automate speculative process.

## Active migration

Describe any old → new path migration, validation method, and rollback point. Otherwise write `None`.

## Maintenance concerns

Record stale dependencies, docs, tests/evals, credentials, operational assumptions, or cleanup that now threatens correctness or velocity.

## Evidence snapshot

Record only the evidence that matters for the current goal and risk. Delete irrelevant rows and add project-specific ones when needed.

| Acceptance criterion or risk | Evidence | Result |
| --- | --- | --- |
| Repository structure is valid | `scripts/verify-repo.sh` | Not run |
| Current capability criterion | Project-defined | Not recorded |

## Known regressions

Record intentionally accepted regressions with an owner and exit condition.

## Next smallest step

Describe one implementation-sized step that reduces the current bottleneck and has a clear verification method.
