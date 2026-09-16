# Phase 2 — harness design (System 2 over the event stream)

Owner: Devin (design). Implementation: sidekick. Language: Python 3 (venv already used by runner.py). Deps: `httpx` or stdlib `urllib` + `sseclient`-free manual SSE parse; `openai` package only if already installed — otherwise raw HTTP to an OpenAI-compatible `/v1/chat/completions`. No other deps.

## Boundary

Bridge (`bridge.mjs`, Node) = System 1: 20 ms motor, reflexes, sensor, cockpit, op commands.
Harness (`harness/`, Python) = System 2: reads the event stream, keeps state, asks a model for one tool call at a time (1-10 s cadence), issues coarse actions to the bridge, mines skills from the trajectory. It never sends raw WASD.

## Modules

- `stream.py` — SSE client for `GET /v1/events` + `GET /v1/keyframe` on start; keeps a ring of the last N events and a `World` snapshot (self pose/health/food/inventory/hotbar, entities, teacher, active situations). Reconnects.
- `situations.py` — predicates over the ring, evaluated on every keyframe/event, edge-triggered: `falling`, `incoming_projectile`, `hostile_near(d<8)`, `low_health(<8)`, `hungry(<8)`, `on_fire`, `in_lava_adjacent`, `night`. Emits `situation {name, active, t_ms, tick}` into a local `harness.jsonl` (same tick stamps). No Minecraft-specific *plans* here — only detectors.
- `tools.py` — the model's tool surface, all mapped to existing bridge endpoints:
  - `observe()` → compact text: pose, HP/food, hotbar, nearby entities with dist, active situations, last 20 non-self events (deltas), open advancements count.
  - `run_skill(name, target_id|block_name, timeout_s)` → `POST /v1/skill` (approach/mine/attack/flee/block already exist).
  - `equip(item, hand)` → `/v1/equip`; `stop()` → `/v1/stop`.
  - `command(slash)` → `/v1/command` **only if `HARNESS_ALLOW_COMMANDS=1`** (demo convenience, off by default; log it).
  - `recall(situation)` → skill store lookup; `note(text)` → memory append; `label(encounter, good|bad)` → `/control` label message equivalent (POST `/v1/label`, add to bridge if missing).
- `actor.py` — OpenAI-compatible chat loop. Env: `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `HARNESS_MODEL`. System prompt: role, tool schema, the *standing goal* ("survive; unlock advancements; prefer skills from recall; label outcomes"). One tool call per turn; the harness executes it, waits for completion or a situation edge (whichever first), then feeds back the delta window. Every turn is logged to `harness.jsonl` as `{kind:'llm', prompt_tokens, tool, args, latency_ms}`.
- `skills.py` — situation-indexed store `skills.json`: `{situation: [{id, action_seq:[key/look/skill events], preconditions:{inventory:{item:min}}, outcomes:{success:n, fail:n}, source:'teacher'|'self', encounter_id}]}`. `mine(trajectory_path)` = for each labeled encounter, find situation onset → outcome, slice the key/look/skill/inventory events between, derive preconditions from items consumed, store with the label as outcome. `recall(situation, inventory)` = entries whose preconditions are satisfied, sorted by success rate.
- `advancements.py` — reads `{kind:'advancement'}` events, keeps `unlocked.json`, exposes count + last 5 for `observe()`. Nothing else — no tree.
- `eval.py` — `python -m harness.eval --minutes 10` runs the actor, reports: advancements gained, deaths, damage taken, situations encountered vs. skills recalled vs. succeeded, LLM calls, mean latency. Writes `eval-<ts>.json`. This is the frozen scoreboard; no gameplay logic.
- `__main__.py` — `python -m harness run|mine|eval|encounters`.

## Non-goals

No hard-coded tech tree, Nether plan, dragon script. No LLM-authored skill code. No pixels (ROCKET-2 stays a bridge-side opt-in motor).

## Verification

- `tests/test_situations.py`: synthetic event sequences → `falling` onset/end edges exact ticks.
- `tests/test_skills.py`: a synthetic labeled water-clutch encounter mines into one `falling` skill with precondition `water_bucket>=1` and outcome success=1; `recall('falling', {bucket:1})` returns nothing, `recall('falling', {water_bucket:1})` returns it.
- Live smoke: `python -m harness run --turns 3` against a mock actor (`HARNESS_MODEL=mock` returns `observe` then `run_skill approach nearest`) — bot moves, `harness.jsonl` has 3 llm entries.
