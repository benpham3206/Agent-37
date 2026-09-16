# Jev tactical fast brain

TypeSafe's Jev (System One model) answers tactical judgments at ~5 Hz;
code does all geometry, aiming, and timing. Jev never answers what code
already knows.

```text
harness/jev.py (Python, ~5 Hz)              bridge.mjs (Node, 50 Hz motor)
 World (keyframe + /v1/events SSE) --------> state JSON
 QUESTIONS fan-out ---------------------->  Jev --> answers
 decide(answers) --> tactic -- POST /v1/tactic {seq, ttl_ms, ...} -->
                                            reflex skill 'tactical'
                                            step(): faceToward(target)
                                            + movement->controls,
                                            attack cadence (12 ticks)
```

## Tactic schema (`POST /v1/tactic`)

```json
{"seq": 1, "ttl_ms": 600,
 "movement": "advance|back_off|strafe_left|strafe_right|hold|disengage",
 "attack": false, "sprint": false, "jump": false, "block": false,
 "meta": {"state_id": 0, "mode": "engage", "danger": 1.0}}
```

Fail closed: the tactic expires after `ttl_ms` (default 600, clamped
100-2000); on expiry the tactical step clears movement/attack but stays
alive holding until a new tactic or `DELETE /v1/skill`. `seq` must
strictly increase (409 `stale_tactic` returns `latest_seq` for resync).
`POST /v1/tactic` requires the `tactical` skill to be running
(`POST /v1/skill {"name":"tactical","args":{"entity_id":N}}`, default
6000-tick timeout); otherwise 409 `no_tactical_skill`. `GET /v1/tactic`
reports `{active, seq, tactic, deadline_ms, target_id}`.
The actor restarts a tactical skill and retries once if it ends during a run.

## Question vocabulary (one state, parallel answers)

- `mode` (choice): engage / hold / create_distance / disengage / recover
- `movement` (choice): advance / back_off / strafe_left / strafe_right /
  hold — relative to facing the target
- `attack`, `block`, `jump`, `sprint`, `disengage`, `tactic_working`,
  `needs_slow_brain` (noul, 0-1)
- `danger` (score, 0-4): none -> likely death within seconds

`decide()` thresholds (defaults): `min_confidence 0.3` (below this with a
previous tactic: hold last tactic), `attack 0.5`, `block 0.6`,
`jump 0.6`, `sprint 0.5`, `disengage 0.7`, `danger_disengage 3.0`.
`recover` forces `back_off`+`block`; `create_distance` rewrites
`advance` to `back_off`; `attack` only in `engage`/`hold` modes.
`needs_slow_brain >= 0.8` calls the `escalate` hook (default: logs an
`escalation` row; no slow-brain implementation yet).

## Running

```bash
# offline, against a running bridge (mock Jev, no API key needed):
python -m harness jev --mock --seconds 20

# real Jev:
TYPESAFE_API_KEY=... python -m harness jev --target-name zombie --seconds 60
```

Env: `TYPESAFE_API_KEY` (required unless `--mock`), `TYPESAFE_MODEL`
(default `jev-latest`), `FAST_BRAIN_URL` (default
`http://127.0.0.1:8876`). If the env var is unset the client falls back
to `TYPESAFE_API_KEY=` in `projects/fast-brain/.env` (gitignored — paste
the key there, never commit it).

## Remembered state (Doom-demo inspired)

`encode_state` emits a `remembered` list modeled on the Doom OPS demo:
`{label, last_seen, distance "12.0 (medium)", bearing "-34 deg (ahead right)", status}`.
Two sources: `--waypoints "name:x,y,z;name2:x,y,z"` (or
`actor.remember(label, x, y, z)`) pins navigation memory, and the actor
automatically keeps the last position/time of entities that leave view
(`status: "out of view"`, `last_seen` bucketed: "just now" / "a few
seconds ago" / "N seconds ago" / "over a minute ago", 2-minute horizon).
`measurement_context` in the state documents units, distance bands
(contact <3.5, close <8, medium <24, far >=24), and the bearing
convention (negative = right) so the model never has to infer them.

Each turn appends one `{"kind":"jev", ...}` row to `harness.jsonl` with
state id, latency, tactic, mode, confidence, danger, and the staleness
flag. Turns whose Jev latency exceeds 1.5x the loop period are logged as
stale and never posted.

The Python `Stream` reads game events from `/v1/events`. `/v1/stream`
serves video frames. The actor stops when its target despawns; a successful
attack decision or accepted tactic alone does not prove the target died.
On bot death, the bridge clears the tactical skill and stops its motor.
After respawn it reports `connected: true, stopped: true`; tactics return
409 `not_ready` until an explicit `POST /v1/resume`.
