# Status

## Current goal

Prove Jev-driven combat in the local Minecraft server. The Python actor
asks Jev for tactics at 5 Hz; the bridge applies them in its 20 ms motor
loop. See `projects/fast-brain/docs/jev-tactical.md`.

## Current capability quality

The live Jev-to-motor path works while FastBrain is alive. Combat success
is not yet reliable: the 2026-09-16 encounter logged two swings, but the
zombie remained alive and FastBrain died twice.

## Working

- Jev's configured key in the gitignored `.env` authenticated live calls.
  No key value is logged or tracked.
- With `/v1/events` as its SSE source, the Python world reader received
  200 recent events in a one-second check and kept a current self state.
- The second 12-second Jev run posted 53 of 53 tactics, with zero stale
  decisions and zero `no_tactical_skill` errors. The bridge logged two
  sword swings. Posts after FastBrain's death did not move the stopped bot;
  the bridge now rejects tactics while stopped.
- A controlled death check left the respawned bot connected and stopped.
  `/v1/tactic` returned 409 `not_ready`; explicit `/v1/resume` restored
  ready state. The server's `keep_inventory` rule was restored to false.
- Offline Jev tests pass 23/23; situation and skill tests pass 1/1 each.
  `node --check projects/fast-brain/bridge.mjs` passes.

## Failing or missing

- The zombie was still alive after the second run. FastBrain died twice;
  its post-respawn position differed from the original fight location.
  Use level terrain to isolate combat behavior from terrain.
- The imported `start-bridge.ps1` points to the older fast-brain checkout.
  Launch `bridge.mjs` from this checkout with Node 22 for live testing.
- fast-brain `vendor/` (ROCKET-2) excluded pending license review.

## Current bottleneck

Run an encounter on safe, level terrain and verify target damage or death
from fresh bridge events. Accepted tactics alone are insufficient.

## Current constraint pressure

Jev latency averaged 214 ms with a 275 ms p95 in the second live run.
The 5 Hz loop tolerated that latency without dropping decisions.

## Security and trust risks

Keep `projects/fast-brain/.env` untracked. The bridge uses an existing
Mindcraft CE dependency tree on the D: drive and Node 22.

## Manual toil worth automating

The checked-in launch scripts still name the older fast-brain path.

## Active migration

None.

## Maintenance concerns

The earlier Python reader used `/v1/stream`, the bridge's video endpoint.
It now uses `/v1/events`; the old endpoint caused stale target state and
repeated skill restarts after a zombie despawned.

## Evidence snapshot

| Acceptance criterion or risk | Evidence | Result |
| --- | --- | --- |
| Live Jev tactics reach the bridge | 2026-09-16 run: 53/53 posted, zero post errors; bot died mid-run | Pass before death |
| Death stops tactics until resume | Controlled `/kill FastBrain`, 409 `not_ready`, explicit resume | Pass |
| Target dies in the live encounter | Zombie still present after 12 seconds | Open |
| Offline behavior | `python -m unittest` Jev, situations, skills | 25/25 pass |

## Known regressions

None recorded.

## Next smallest step

Use a flat local test area to isolate combat behavior from terrain. Check
the bridge's target events and FastBrain's health after the encounter.
