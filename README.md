# Agent-37 combat teacher

This prototype implements one complete boundary: a human controls a Mineflayer bot, records synchronized combat demonstrations, trains a small tactical policy, evaluates the frozen candidate in an isolated Minecraft arena, and promotes it as the coarse `combat.engage` skill.

It uses the hybrid controller described in the project plans. A behavior-cloning MLP chooses movement, attack permission, shield use, and disengagement at 10 Hz. A deterministic hitbox motor updates aim at 20 Hz. Every camera, movement, use, and attack request passes through one safety arbiter. A planner or language model only starts, monitors, or cancels an encounter.

No demonstrations, trained weights, evaluation passes, or promoted skills are bundled. The scaffold is runnable; combat competence begins after real human data is recorded.

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

The command opens the local control page. Its first-person `prismarine-viewer` view supports pointer-lock mouse input, WASD, jump, sprint, sneak, attack, use/block, and hotbar selection. The overlay draws the selected entity AABB and aim point. Recording controls create encounter files and label an entire encounter `good`, `bad`, or `excluded`. Losing focus, pointer lock, the WebSocket, or pressing Escape releases all controls immediately.

Record several whole encounters for both zombies and skeletons. Use a new session for each environment: `open_surface`, `underground`, `nether_open`, `fortress`, `end_island`, `bridge`, or `other`. The environment label documents coverage; it is deliberately excluded from policy inputs. Generalization comes from relative target, equipment, dimension, support, drop, clearance, and hazard features recorded across varied demonstrations.

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

The active registry pointer is replaced atomically. Invocation loads the frozen ONNX artifact through a replaceable policy adapter. A future VLA can implement the same observation-to-tactical-action boundary without changing deterministic aim, arbitration, evaluation, registry, or the planner-facing tool.

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

Related PrimeCraft, Mindcraft CE, and fast-brain work is imported under
`projects/` as complete, separately labeled snapshots. Each directory keeps its
original layout and carries a `PROVENANCE.md` stating its source path, commit,
dirty-state import, exclusions, and relationships. The Agent-37 combat teacher
stays at the repository root.

| Project | Labels | Provenance |
| --- | --- | --- |
| `projects/primecraft-ce/` | `mindcraft-ce-base`, `primecraft-agent-contract` | [PROVENANCE](projects/primecraft-ce/PROVENANCE.md) |
| `projects/mindcraft-ce/` | `mindcraft-ce-base`, `primecraft-agent-contract`, `mindcraft-ce-runtime-upgrade` | [PROVENANCE](projects/mindcraft-ce/PROVENANCE.md) |
| `projects/primecraft-runtime/` | `primecraft-runtime` | [PROVENANCE](projects/primecraft-runtime/PROVENANCE.md) |
| `projects/primecraft-vision-loop/` | `primecraft-vision-loop` | [PROVENANCE](projects/primecraft-vision-loop/PROVENANCE.md) |
| `projects/primecraft-vision-draft/` | `primecraft-vision-draft` | [PROVENANCE](projects/primecraft-vision-draft/PROVENANCE.md) |
| `projects/fast-brain/` | `fast-brain-system1`, `fast-brain-system2`, `fast-brain-rocket2-optional` | [PROVENANCE](projects/fast-brain/PROVENANCE.md) |

The registry is `provenance/projects.json` and `provenance/sources.json`.
Overlap between the two CE snapshots and the older CE copy is documented in
`provenance/comparisons/`. `python scripts/verify-provenance.py` checks labels,
ownership, manifests, and forbidden runtime material; `bash scripts/project/check`
runs it together with the offline per-project checks listed in
`provenance/verification.md`.
