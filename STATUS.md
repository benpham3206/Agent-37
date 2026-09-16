# Status

## Current goal

Prove Jev-driven combat in the local Minecraft server. The Python actor
asks Jev for tactics at 5 Hz; the bridge applies them in its 20 ms motor
loop. See `projects/fast-brain/docs/jev-tactical.md`.

## Current capability quality

`works`. The live Jev-to-motor path killed a zombie in the 2026-09-16
18:04 UTC run: 70 turns at 5 Hz, 68 tactics accepted, 24 tactical swings,
zombie #1791 despawned at bridge tick 13189, FastBrain finished at 20 hp.
Earlier runs on uneven terrain were not reliable (FastBrain died twice).

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

One kill is `works`, not `reliable`. Repeat the encounter across several
zombies and a skeleton, and count kills, deaths, and damage taken, before
tuning thresholds or adding the slow-brain escalation handler.

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
| Target dies in the live encounter | 18:04 UTC run: 24 tactical swings then `entity despawn id=1791` in `logs/trajectory-2026-09-16T18-04-28-618Z.jsonl`; actor reported `target_alive: false`, final health 20 | Pass |
| Offline behavior | `python -m unittest` Jev, situations, skills | 25/25 pass |

## Known regressions

None recorded.

## Next smallest step

Run five consecutive `python -m harness jev` encounters and record
kill/death/damage per run in `provenance/verification.md`.
