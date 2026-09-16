# Consolidation exclusions

Material deliberately not imported into this repository. Each entry names the
excluded class or file, the source it came from, and why.

## Excluded classes (all sources)

- Dependency trees: `node_modules/`, Python `.venv/`, `__pycache__/`, npm caches.
- Secrets and auth material: `keys.json`, `.env*`, tokens, Microsoft/Lunar auth
  caches, `PRIME_CE_BRIDGE_TOKEN` values, model credentials.
- Runtime state: Minecraft worlds, server jars, Java/adapter/bridge logs,
  evidence runs, generated screenshots/frames, trajectories, JSONL live streams.
- Model weights: `*.safetensors`, `*.onnx`, `*.pt` (Agent-37 `.gitignore`
  already excludes these).
- Generated worker material, snapshots, backups, nested `.git` metadata.

## Source-specific exclusions

- `D:/Codex/2026-08-26/plea` (primecraft-runtime): everything outside the
  documented allowlist (`AGENTS.md`, `CONTEXT.md`, `docs/`, selected
  `tools/*`, adapter source under `work/delegated/B-mineflayer-adapter`).
  Excluded: `outputs/`, `work/evidence`, `work/pads`, `.prime`, server/world
  directories, Node distributions, logs.
- QUIC `outputs/primecraft`: `runs/`, memory/skill stores, JSONL state.
- QUIC root `primecraft/`: imported whole as the historical draft (2 files).
- fast-brain: `__pycache__`, `logs/`, `work/`, `harness.jsonl`,
  `models/` (ROCKET-2 weights), `movement-viewer.html` review pending,
  `.venv`.
- fast-brain `vendor/`: ROCKET-2 upstream code; see
  `projects/fast-brain/PROVENANCE.md` and
  `provenance/manifests/fast-brain-vendor-excluded.sha256` for the license
  decision.
- Mindcraft CE checkouts: `__pycache__` untracked caches, auth caches.
- Agent-37 root: `data/`, `work/`, `bridge/work/`, `.venv/`, recordings,
  weights — local runtime evidence, kept private per existing `.gitignore`.
