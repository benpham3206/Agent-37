# Provenance: fast-brain

- Source path: `C:/Users/hotdo/Documents/Codex/2026-09-11/crea/outputs/fast-brain`
- Remote: none (non-Git event-first project)
- Branch / commit: n/a
- Shallow: n/a
- Dirty: n/a
- captured_at: 2026-09-15T19:09:49-07:00
- Import mode: allowlisted working-tree snapshot, original layout kept
- Diff labels: `fast-brain-system1`, `fast-brain-system2`,
  `fast-brain-rocket2-optional`
- Imported: `bridge.mjs`, `public/`, `harness/`, `tests/`, `runner.py`,
  `start-bridge.ps1`, `start-server.ps1`, `PAD.md`
- Exclusions applied: `__pycache__/`, `.venv/`, `logs/`, `work/`,
  `harness.jsonl` (live trajectory), `models/` (ROCKET-2 weights),
  `vendor/` (see below)
- Manifest: `provenance/manifests/fast-brain-dest.sha256`
- Source manifest: `provenance/manifests/fast-brain-src.sha256`
- Relationships: bridge uses Mineflayer and reuses CE `node_modules` via
  `FAST_BRAIN_NODE_MODULES`; harness calls the bridge HTTP/SSE/WS
  boundary

## Subsystems

- `system1` (`fast-brain-system1`): `bridge.mjs`, `public/` — event
  sensor, 20 ms fail-closed motor loop, cockpit/viewer.
- `system2` (`fast-brain-system2`): `harness/`, `tests/` — event-stream
  state reconstruction, situation detectors, bounded tools, actor loop,
  skill mining, scoreboard.
- `rocket2-optional` (`fast-brain-rocket2-optional`): `runner.py` plus the
  excluded `vendor/` and `models/` material.

## vendor/ license decision

`vendor/` is ROCKET-2 upstream code (`rocket_model.py` references
`/ROCKET2-OSS/model.py`). License scan of all vendor `*.py` files found an
Apache-2.0 header only in `tree_util.py` (Google LLC); the ROCKET-2 files
carry no license statement. Per the consolidation policy, vendor bytes are
EXCLUDED pending license review. Their SHA-256s are recorded in
`provenance/manifests/fast-brain-vendor-excluded.sha256` (35 files
including `__pycache__` entries from the source tree). Re-import requires
a license determination.

## Changes after import

- `fast-brain-jev-tactical` — added the Jev (TypeSafe System One)
  tactical fast brain: `harness/jev.py` (state encoding, question fan-out,
  decision reduction, JevActor loop), the `tactical` reflex skill and
  `/v1/tactic` routes in `bridge.mjs` (fail-closed TTL tactics),
  `tests/test_jev.py`, `docs/jev-tactical.md`, and the `jev` subcommand in
  `harness/__main__.py`. Commit subject:
  `fast-brain: add Jev tactical fast brain (System One) over the reflex
  motor loop`. The pre-change source snapshot is recoverable from Git
  history (import commit `f7879f9`).
