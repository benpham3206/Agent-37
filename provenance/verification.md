# Consolidation verification

Fresh offline results for branch `consolidate/agent-engineering-20260915`,
recorded 2026-09-15. No check starts Minecraft, a controller, or a model call.

Run everything with `bash scripts/project/check` (about 10 seconds).

## Results

| Check | Command | Result |
| --- | --- | --- |
| Provenance registry and manifests | `python scripts/verify-provenance.py` | PASS (6 projects, 3 comparison records) |
| Negative fixtures reject bad registries | `python scripts/verify-provenance.py --root tests/provenance/fixture-*` | all 3 fail as intended (unlabeled, overlap, forbidden) |
| Agent-37 bridge tests | `node --test bridge/*.test.js bridge/public/*.test.js` | PASS 20/20 |
| Agent-37 Python tests | `uv run --offline --no-sync pytest tests/` | SKIP: `pytest` not installed in the local `.venv`; run `uv sync --group dev` then rerun |
| primecraft-ce bridge syntax | `node --check projects/primecraft-ce/tools/prime-ce-bridge.mjs` | PASS |
| mindcraft-ce bridge syntax | `node --check projects/mindcraft-ce/tools/prime-ce-bridge.mjs` | PASS |
| CE Prime unit tests | `node --test src/agent/advancements.test.mjs src/agent/prime_controller.test.mjs` | SKIP: need `npm install` inside the project (`node_modules` is not vendored) |
| fast-brain bridge syntax | `node --check projects/fast-brain/bridge.mjs` | PASS |
| fast-brain unit tests | `python -m unittest tests.test_situations tests.test_skills` | PASS 2/2 |
| vision-loop compile | `python -m compileall -q projects/primecraft-vision-loop/primecraft` | PASS |
| vision-loop offline smoke | `python smoke_check.py` | PASS ("smoke boundaries ok (offline; no gameplay claim)") |
| vision-loop CLI | `python -m primecraft --help` | PASS |
| Agent Engineering repository contract | `bash scripts/verify-repo.sh` | PASS on a clean clone of the branch (50 s); see note below |
| Tracked secret-file policy | `bash scripts/security-check.sh` | PASS on a clean clone of the branch; see note below |
| Whitespace | `git diff --check main..HEAD` | only "new blank line at EOF" in imported fast-brain sources; original bytes kept on purpose |
| Secrets grep over tracked files | names: `keys.json`, `.env`, `token`, `secret`, `password`, `credential`; content: `api_key`/`secret`/`password`/`Bearer` assignments | no tracked secret files; content hits are upstream placeholder comments (`// password: 'your_bot_password'`) and one test literal (`secret="must-not-be-accepted"`) |
| Branch hygiene | `git rev-parse main` | `6893066`, unchanged; branch is 14 labeled commits on top |

## Notes

- `verify-repo.sh` scans every file in the working tree for unreplaced
  template tokens. On the original local checkout that includes an untracked
  `.venv/`, so it is slow there; on a clean clone it completes quickly.
- `security-check.sh` calls `git ls-files`. On the original local checkout the
  repository is owned by a different Windows account, so plain `git` reports
  "dubious ownership" and the script prints
  `tracked secret-file policy: SKIP (project Git metadata unavailable)`. Run
  it with `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
  GIT_CONFIG_VALUE_0='*'` there, or from a normal clone.
- The verifier enumerates git-tracked files when run inside a work tree, so
  build output such as `__pycache__` created by the offline checks cannot fail
  or pass it; only published bytes count.
- Manifest comparison is two-directional: every manifest entry must exist on
  disk with a matching SHA-256, and every tracked file under a project
  destination must be in its manifest.

## Known limitations recorded, not fixed

- `projects/primecraft-runtime` scripts hard-code D:-drive paths, ports, and
  local runtimes (see its `PROVENANCE.md`).
- `projects/fast-brain/vendor/` (ROCKET-2 upstream code) is excluded pending
  license review; hashes are in `manifests/fast-brain-vendor-excluded.sha256`.
- Agent-37 recording writes `environment_suite`/`environment_label` while the
  Python validator expects `environment` (pre-existing contract defect, out of
  scope).

## fast-brain-jev-tactical (2026-09-15, later commit)

| Check | Command | Result |
| --- | --- | --- |
| fast-brain Jev unit tests | `PYTHONDONTWRITEBYTECODE=1 python -m unittest tests.test_situations tests.test_skills tests.test_jev` (in `projects/fast-brain`) | PASS 17/17 |
| fast-brain bridge syntax | `node --check projects/fast-brain/bridge.mjs` | PASS |
| Jev CLI | `python -m harness jev --help` | PASS |
| Provenance verifier after manifest regen | `python scripts/verify-provenance.py` | PASS |

## fast-brain Jev live repair (2026-09-16)

| Check | Evidence | Result |
| --- | --- | --- |
| Jev unit tests | `python -m unittest tests.test_jev` | PASS 23/23 |
| Situation and skill tests | `python -m unittest discover` for each file | PASS 2/2 |
| Bridge syntax | `node --check projects/fast-brain/bridge.mjs` | PASS |
| Event reader | `Stream().start()` against local bridge; 200 SSE events in one second, self present | PASS |
| First live Jev run | 12 s, 48 decisions, 34 accepted; zombie despawned after three swings, then stale Python state retried a missing skill | Exposed wrong `/v1/stream` subscription |
| Second live Jev run | 12 s, 53/53 tactics posted, zero stale replies or post errors; two swings, zombie alive, FastBrain died twice | Tactical path works before death; combat outcome open |
| Death and respawn | Controlled `/kill FastBrain` with temporary inventory preservation; respawn `connected: true, stopped: true`, tactic 409 `not_ready`, explicit resume returned ready; original `keep_inventory=false` restored | PASS |
| Provenance | `python scripts/verify-provenance.py` after manifest refresh | PASS |

The final offline run covered 25 tests in total. It also checked that
spawn events provide the position in `to`, and that an unreachable bridge
stops the actor before a Jev request.

The second live run exposed a separate safety defect. Before the repair,
the bridge accepted tactics after death even though its motor remained
stopped. The bridge now clears the skill on death, reports the respawned
bot as connected but stopped, and requires `/v1/resume` before accepting
tactics. The Python actor checks bridge readiness before calling Jev.
