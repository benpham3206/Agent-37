# Session scratchpad — fast-brain harness

- project: fast-brain (events-first Minecraft agent harness, System 1 + System 2)
- cwd: C:\Users\hotdo\Documents\Codex\2026-09-11\crea\outputs\fast-brain
- started: 2026-09-11
- updated: 2026-09-13T03:45Z
- canonical: THIS FILE. Read before task work; update on checkpoint/pivot/verified result/blocker. Not for chatter.

## Intent

Ben wants a harness any strong model can plug into to play Minecraft, learn skills from labeled change-events (its own play + Ben's demonstrations), generalize, and unlock advancements — with a tick-rate System 1 (reflexes, motor) under a slow System 2 (LLM strategy). No hard-coded progression scripts.

## 5W1H

- What — `bridge.mjs` (Mineflayer bridge: event sensor, 20 ms motor, cockpit, op commands, teacher tracking) + Python harness (OpenAI-compatible actor, tools, skill store, advancement tracker, eval). ROCKET-2 runner opt-in.
- Why — every prior attempt (plea, primecraft, Agent-37) built System 2 and never closed a fast loop; pixels can't do depth (blaze charge), events can.
- Who — Ben decides one-way doors (world changes, server restarts, pushes). Devin owns writes under `outputs/fast-brain`. Sidekick implements; Devin reviews.
- When — now, iterative; live demo before harness polish.
- Where — server `wood-gate-server-26.1.2` @ 127.0.0.1:25566 (dir `D:\Codex\2026-08-26\plea\work\wood-gate-server-26.1.2`); bridge :8876, viewer :8877; Ben plays as `6ento` in Lunar Client; bot `FastBrain` (OP).
- How — Node 22 binary `D:\Codex\2026-08-26\plea\work\node-v22.23.2-win-x64\node.exe` (system Node 24 breaks `gl`); CE `node_modules` reused read-only; verify via /healthz, trajectory JSONL, server latest.log, WS check script.

## Constraints

- **Must not break:**
  - Do not modify `D:\Codex\2026-08-26\plea\work\mindcraft-ce` (dirty checkout). Only exception already done: restored `gl` Node-22 prebuild binary.
  - Do not restart the Minecraft server without Ben. Never kill java; only the node.exe whose cmdline has `bridge.mjs`.
  - Bridge must be launched DETACHED (PowerShell Start-Process) — it died twice with the launching shell.
  - Fail-closed motor: TTL, seq, STOP, human precedence, release-on-disconnect stay.
  - No hard-coded Minecraft walkthrough/tech tree in the harness. Skills are mined from the stream, not authored.
  - Event volume must stay < ~150 events/s (was 8k/s → crashed server watchdog in Zombie.tick).
  - Ben's own inputs are only observable via the bot's view of `6ento` (inferred), or exact when he drives FastBrain through the cockpit.
  - **Optimize for latency in every edit/creation** (Ben, 09-12). Measure it; never add a hop, poll, or render that isn't consumed.
  - **Never interrupt a working sidekick** (Ben, 09-12). User messages arriving mid-handoff are read-only for the lead; queue them in Todo and hand off after the current pass reports.
  - Update this pad on non-trivial events only (checkpoint / pivot / verified result / blocker / handoff).

## Goal

[Ben · now · fast-brain] Ben can drive FastBrain from the cockpit (or play as 6ento, tracked) and perform a labeled water-clutch demo that lands as one encounter in the trajectory; then Phase 2 harness mines it into a situation-indexed skill store.

## Todo

- [x] Survey D:\Codex + Codex sessions vs Agent-37 plan (`crea/work/prior-attempts-inventory.md`)
- [x] Event sensor: tick-stamped stream, SSE, keyframes, JSONL, key/look echo, projectile tti/will_hit
- [x] Dead-reckoning sensor (corrections not state; `category` not `kind`) — 8k/s → ~30/s
- [x] Cockpit (Agent-37 layout) on prismarine-viewer browser renderer, WS `/control`, labels into trajectory
- [x] `/v1/command` op path; zombie helmeted, rotten flesh killed (40 82 -21 is NOT a spawner — natural spawns)
- [x] teacher tracking of `6ento`: pose corrections, look, flags, inferred inputs, `falling` situation, `/data get` per-path poll for health/food/air/dimension/inventory (full dump truncated before Health → rotate one path per poll); cockpit Teacher block; `GET /v1/encounters`
- [x] lag: `objectType` Trace spam gone (0 lines), lazy headless capture (+`/v1/frame/subscribe`), viewDistance 3 (browser + headless WorldView), 16 ms mouse throttle; idle CPU 63%→5.3% core, control→state 46 ms
- [x] auto-launch bridge: `start-bridge.ps1` + hook in `D:\Codex\2026-08-26\plea\tools\start-wood-gate-server.ps1` (the script `primecraft.ps1` runs, not the `work/` path)
- [x] loadout: shield offhand + water bucket always (verbatim: "Replaced a slot on FastBrain with [Shield]", "Gave 1 [Water Bucket] to FastBrain"; zero spam when satisfied); auto-sprint forward&&!sneak (verified both directions)
- [x] cockpit inventory HUD: hotbar+selected+offhand, HP/food/armor bars, XP, air bubbles, FALLING badge, held-item flash, coords+facing, chat pane, damage flash
- [x] right-click bug fixed: `use_item` for bucket/shield/food etc., direct `block_place` with real face/cursor, `use_entity` direct — no lookAt; dpitch 0.0000 verified, water placed+removed
- [x] yaw cut-out fixed: absolute `lookTarget` via `queueLookDelta`+`applyLook()` (one call/motor tick, 1.2 rad/tick cap); `player_rotation`/`position` packets resync target. 200×0.0008 rad → 0.1597 applied (before: 0.0000); 3 rad spin in 99 ms
- [x] 60 fps cockpit: viewer served same-origin `/viewer/` (socket.io tunneled to :8877, bundle patched at serve-time → `window.viewer` + `window.fbCam`); cockpit drives `viewer.camera` per rAF. ~119 fps, rAF→camera 5.5 ms
- [x] Cockpit Join bot / Leave bot: idempotent `/v1/bot/join` and `/v1/bot/leave`, lifecycle shown in UI, held controls released on leave, old viewer closed, same-port viewer reloaded on join. Verified with live page and `/healthz` on 2026-09-13.
- [ ] **QUEUED:** FSD-style unification — every change is an event, internal or external: LLM decisions, skill start/stop, reflex triggers, motor merges (which source won each key), loadout actions, harness situations, cockpit clicks — all `{tick, kind, ...}` in the one stream
- [ ] Review sidekick diffs (bridge.mjs, public/, tests/) — not yet reviewed line-by-line
- [ ] Reduce natural zombie spawns near base if piles return (light the area / `doMobSpawning`) — Ben's call
- [x] Phase 2 v0 landed (Codex CLI worker, `harness/`, 288 lines, stdlib only): `python -m harness run|mine|eval|encounters`; mock actor smoke moved bot; 2 unit tests pass. Spec: `harness/DESIGN.md`
- [ ] Review Phase 2 harness (Devin): situation detectors vs stream schema, mine() on a real labeled clutch, actor prompt/tool loop against a real OpenAI-compatible endpoint
- [ ] Bridge autostart test with a real `primecraft start` (Ben's call — restarts server)
- [ ] Bridge DoD line 81-82 met (CPU 5%, rtt 46 ms) — awaiting Ben's live clutch for 79-80
- [ ] ROCKET-2 runner latency benchmark on 1660 SUPER (raw vs CFG), keep opt-in

## State

- Server 26.1.2 up on 25566 (java pid 14232 at 2026-09-13T03:45Z); it was not restarted for the Join/Leave change.
- Bridge detached Node 22 pid 12840 on 8876; bot `FastBrain` joined after a live Leave/Join round trip. `/healthz`: `connected:true`, `bot_lifecycle.state:joined`, generation 3, viewer_generation 1. Leave freed 8877 while 8876 and 25566 stayed listening; Join restored 8877 and reloaded the iframe at `/viewer/?generation=1`.
- Trajectory: `logs/trajectory-<ts>.jsonl`; labels `{kind:'label', encounter_id, action}`; `/v1/encounters` verified (`enc-mty7eqzq` start→good→stop).
- Cockpit renders 26.1.2 with 1.21.4 assets; entity mesh TypeError tolerated. Viewer now same-origin `/viewer/` + local camera drive (~119 fps, input→camera ~5 ms).
- Screenshot: `logs/cockpit-hud.png`. Tests: teacher-check.mjs 16/16, look-check.cjs PASS (0.16→0.1597), use-bucket-check.cjs PASS (dpitch 0), ws-control-check.cjs PASS (control_to_state_ms 46).

## Checkpoint

- 2026-09-12T01:13 expected: live sensor demo. actual: server watchdog crash in Zombie.tick; cause = 8k events/s + zombie crowd. Fixed by dead reckoning.
- 2026-09-12T08:30 expected: bridge starts with system node. actual: `gl` ABI mismatch (Node 24). Fixed: Node-22 binary + restored prebuild.
- 2026-09-12T08:55 expected: cockpit live. actual: verified (screenshot `logs/cockpit.png`, WS forward moved bot 6.2 blocks). Then bridge died with shell → relaunched detached.
- 2026-09-12T09:20 Ben: cockpit laggy; can't see inventory; wants teacher tracking, autostart, loadout, sprint. → sidekick pass in flight.
- 2026-09-12T09:55 expected: yaw deltas lost under 0.15°, 60 fps viewer, full HUD. actual: all landed — yaw 0.16→0.1597 (was 0.0), viewer ~119 fps same-origin, input→cam 5.5 ms, CPU 63%→5.3%, all tests green.
- 2026-09-13T03:45Z expected: Join/Leave from the cockpit without restarting the world. actual: browser button changed Joined→Left→Joining→Joined; viewer port 8877 closed/reopened and iframe URL generation advanced 0→1; duplicate Join kept bot generation 3; Java server stayed pid 14232. Existing prismarine-viewer entity-mesh TypeError remains visible in bridge logs.

## Definition of Done (current goal)

- [ ] Ben opens http://127.0.0.1:8876/, sees smooth view + his hotbar/offhand/HP, drives FastBrain, Start → fall → bucket clutch → Stop → Good
- [ ] `GET /v1/encounters` lists that encounter with a `falling` onset, `key use`, `block → water`, no `damage`
- [ ] Bridge autostarts with `primecraft start`; survives shell exit
- [ ] Idle CPU of bridge < 15% of one core; control→state round trip < 100 ms

## Open

- Does prismarine-viewer browser renderer handle 26.1.2 entities well enough, or fall back to MJPEG in-layout?
- Player health/food of 6ento is NOT in entity packets → `/data get entity` poll (1 Hz) is the only source; acceptable?
- Whether to light the spawn area vs `doMobSpawning false` for demos (Ben decides).

## Decisions

- Events-first over pixels-first; ROCKET-2 opt-in motor, not the core. (Ben agreed.)
- Dead reckoning: emit causes (keys/look) + residuals (corrections), not state. (Ben's call.)
- Skill store keyed by *situation* predicate (e.g. `falling`) → list of skills with preconditions (inventory consumed) + outcome stats; water/hay/boat clutch are entries, not separate skills.
- Cockpit = Agent-37 layout on browser renderer (Ben: "that's the one I want").
- Trajectory is the recording; labels are events. No separate recording files.
- Use `/item replace` + `/give` via op bot for loadout; no plugins/datapacks.
- Model everything as Tesla-FSD-style event sensing: a *change* — external (world, entities, teacher) or internal (decision, reflex trigger, motor merge, skill state, LLM call) — is one tick-stamped event in one stream. State is reconstructed from keyframe + changes; nothing is polled that can be diffed. (Ben, 09-12)
- Imitation first: Ben is the teacher (`6ento`); bot recalls teacher skills per situation, then its own labeled outcomes gradually outweigh teacher entries (`source: teacher|self` in the skill store). (Ben, 09-12)

## Notes

- Agent-37 cockpit source: `C:\Users\hotdo\Documents\Codex\2026-09-07\i-wa\outputs\Agent-37\bridge\public`.
- Prior-attempt inventory: `C:\Users\hotdo\Documents\Codex\2026-09-11\crea\work\prior-attempts-inventory.md`; policy research: `crea\work\policy-research.md`.
- Blocking heuristic: shield raise 5 ticks; `use` on `will_hit && tti_ticks <= 7`; unverified in-game.
- Sidekick workers are Devin sidekick (not SWE-2); earlier research workers were delegated Codex/GPT-5.x agents.

## Turn log

- 09-12 01:xx server crash → restart; evidence review.
- 09-12 08:xx helmet request; Node-22 fix; bridge live; cockpit port; commands run.
- 09-12 09:xx teacher tracking + lag + autostart + loadout + sprint handed off (in flight); pad created.
- 09-12 10:xx yaw cut-out fix (absolute lookTarget seam), /viewer/ same-origin + 60fps camera, full HUD, poll_error dedup, WorldView radius 6→3; all verified; pad updated.
