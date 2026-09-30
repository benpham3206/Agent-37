# Agent-37 combat teacher

Record human-controlled Mineflayer combat, train a tactical policy, evaluate the frozen candidate in an isolated Minecraft arena, and promote it as `combat.engage`.

A behavior-cloning MLP chooses movement, attack permission, shield use, and disengagement at 10 Hz; a deterministic hitbox motor updates aim at 20 Hz. One safety arbiter handles every camera, movement, use, and attack request. A planner or language model only starts, monitors, or cancels encounters.

The scaffold runs, but bundles no demonstrations, trained weights, evaluation passes, or promoted skills. Combat competence requires real human data.

## Install

Python 3.10+ and Node.js are required. Training also needs PyTorch and ONNX.

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[train,dev]"
cd bridge
npm install
cd ..
```

## Teach

Start a separate `Agent37Teacher` bot on a Minecraft Java server:

```powershell
.venv\Scripts\agent37 combat teach `
  --server 127.0.0.1 `
  --port 25566 `
  --target zombie `
  --session zombie-surface-01 `
  --environment open_surface
```

The local control page uses first-person `prismarine-viewer` with pointer-lock mouse input, WASD, jump, sprint, sneak, attack, use/block, and hotbar selection. An overlay draws the selected entity AABB and aim point. Record encounters and label them `good`, `bad`, or `excluded`. Losing focus, pointer lock, or the WebSocket, or pressing Escape, releases all controls immediately.

Record whole zombie and skeleton encounters. Use a new session for each environment: `open_surface`, `underground`, `nether_open`, `fortress`, `end_island`, `bridge`, or `other`. Environment labels document coverage and are excluded from policy inputs. Relative target, equipment, dimension, support, drop, clearance, and hazard features across varied demonstrations support generalization.

Data is written under `data/combat/<session>/`: Python creates `session.json`, and the Node bridge writes versioned 20 Hz JSONL trajectories under `encounters/`. Requested teacher actions and arbiter-applied actions are stored separately. See [the data contract](docs/combat-contract.md) and [dataset notes](docs/dataset.md).

## Validate and train

```powershell
.venv\Scripts\agent37 combat dataset validate data/combat/zombie-surface-01

.venv\Scripts\agent37 combat train `
  data/combat/zombie-* data/combat/skeleton-* `
  --out skills_store/candidates/combat-001
```

Validation rejects missing fields, invalid clocks, synchronization gaps, and incomplete actions. Training uses only good, human-controlled rows; downsamples them to 10 Hz; builds four-frame histories without crossing encounter boundaries; and splits by whole encounter. The 64/64 ReLU MLP uses weighted binary cross entropy and exports `model.onnx` plus normalization, feature order, dataset/model hashes, split membership, coverage, and per-action/per-mob/per-environment metrics in `metadata.json`.

Synthetic data requires `--allow-synthetic` and is permanently marked ineligible for promotion.

## Evaluate, promote, and invoke

Evaluation always creates a new local server directory and never attaches operator commands to an existing survival world:

```powershell
.venv\Scripts\agent37 combat evaluate `
  --candidate skills_store/candidates/combat-001 `
  --server-jar C:\path\to\server.jar `
  --java C:\path\to\java.exe `
  --accept-eula

.venv\Scripts\agent37 combat promote --candidate combat-001
.venv\Scripts\agent37 combat rollback --skill combat.engage --version v1
```

The first promotion gate requires a completed, hash-stable frozen evaluation with at least five zombie and five skeleton trials, at least 80% success for each mob, no bot deaths, no teacher intervention, and zero safety violations. It qualifies only `open_surface`. Other environments must receive their own frozen suites before they can be advertised.

With a bridge running, the agent-facing interface stays coarse:

```powershell
.venv\Scripts\agent37 combat engage --target zombie --required-environment open_surface
.venv\Scripts\agent37 combat status
.venv\Scripts\agent37 combat cancel
```

Invocation loads the frozen ONNX artifact through a replaceable policy adapter; the active registry pointer changes atomically. A future VLA can use the same observation-to-tactical-action contract, preserving deterministic aim, arbitration, evaluation, registry, and planner tools.

## Layout

- `bridge/`: Mineflayer connection, observation and terrain features, teacher UI, recorder, ONNX inference, deterministic aim, and arbiter.
- `harness/combat/`: dataset validation, training, disposable arena, registry, CLI, and coarse tool.
- `contracts/policy.json`: shared ordered feature/output contract used by Python and Node.
- `docs/`: wire format and dataset/promotion rules.
- `tests/`: geometry, arbitration, projection, recording, dataset, ONNX export/runtime, registry, and arena invariants.

Run verification with:

```powershell
.venv\Scripts\python -m pytest -q
cd bridge
npm test
```

## Consolidated projects

`projects/` contains complete, separately labeled PrimeCraft, Mindcraft CE, and fast-brain snapshots with original layouts. Each `PROVENANCE.md` records source path, commit, dirty-state import, exclusions, and relationships. The combat teacher remains at the root.

| Project | Labels | Provenance |
| --- | --- | --- |
| `projects/primecraft-ce/` | `mindcraft-ce-base`, `primecraft-agent-contract` | [PROVENANCE](projects/primecraft-ce/PROVENANCE.md) |
| `projects/mindcraft-ce/` | `mindcraft-ce-base`, `primecraft-agent-contract`, `mindcraft-ce-runtime-upgrade` | [PROVENANCE](projects/mindcraft-ce/PROVENANCE.md) |
| `projects/primecraft-runtime/` | `primecraft-runtime` | [PROVENANCE](projects/primecraft-runtime/PROVENANCE.md) |
| `projects/primecraft-vision-loop/` | `primecraft-vision-loop` | [PROVENANCE](projects/primecraft-vision-loop/PROVENANCE.md) |
| `projects/primecraft-vision-draft/` | `primecraft-vision-draft` | [PROVENANCE](projects/primecraft-vision-draft/PROVENANCE.md) |
| `projects/fast-brain/` | `fast-brain-system1`, `fast-brain-system2`, `fast-brain-rocket2-optional` | [PROVENANCE](projects/fast-brain/PROVENANCE.md) |

`provenance/projects.json` and `provenance/sources.json` register the snapshots; `provenance/comparisons/` documents overlap between the two CE snapshots and the older CE copy. `python scripts/verify-provenance.py` checks labels, ownership, manifests, and forbidden runtime material. `bash scripts/project/check` also runs the offline per-project checks listed in `provenance/verification.md`.
