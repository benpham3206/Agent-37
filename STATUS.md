# Status

Keep this file current and short. It is the fastest way for a new contributor or architect agent to understand project state.

## Current goal

Jev (TypeSafe System One) tactical fast brain in `projects/fast-brain` — a
`tactical` reflex skill plus `/v1/tactic` TTL seam in `bridge.mjs`, driven
by `harness/jev.py` at ~8 Hz. See `projects/fast-brain/docs/jev-tactical.md`.

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

- Offline unit tests: `python -m unittest tests.test_situations tests.test_skills tests.test_jev` (17 tests) in `projects/fast-brain`.
- `node --check projects/fast-brain/bridge.mjs`; `python -m harness jev --help`.
- Consolidated projects registry and provenance verifier (`bash scripts/project/check`).

## Failing or missing

- No live Minecraft or live Jev run yet — no `TYPESAFE_API_KEY` on this machine; only `--mock` is exercised.
- fast-brain `vendor/` (ROCKET-2) excluded pending license review.

## Current bottleneck

Live validation: the Jev loop needs a running fast-brain bridge plus a
`TYPESAFE_API_KEY` to prove the end-to-end path.

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
