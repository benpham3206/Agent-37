# Combat dataset and learner

Each teaching session is a directory containing `session.json` and `encounters/<encounter-id>.jsonl`. `session.json` requires an `environment` tag: `open_surface`, `underground`, `nether_open`, `fortress`, `end_island`, `bridge`, or `other`; free-form `notes` are allowed. The wire format is defined in `docs/combat-contract.md`; rows are synchronized at roughly 20 Hz and labels belong to an encounter. A training example is a four-frame history at 10 Hz, built only from `good` teacher-controlled rows within one encounter. This keeps adjacent frames from leaking across train, validation, and test.

Validate before training:

```bash
agent37 combat dataset validate data/combat/zombie-basics-01
```

Training uses a compact 64/64 ReLU MLP and weighted binary cross entropy for sparse action outputs. In addition to relative combat state, the policy observes the bridge's numeric dimension one-hot and terrain summary (`support_grid`, drop depth, clearance, and nearby hazards). It never reads the session environment label. Normalization is computed from training windows only and is saved in `metadata.json` beside the ONNX model. Metadata stores split membership as `{session, encounter, environment}` pairs, data coverage and absent environments, and per-output/per-environment validation metrics. Dataset directories marked `synthetic: true` are useful for unit tests but are ineligible for promotion.

The arena writes `evaluation.json` in the candidate directory. Promotion requires matching candidate model and dataset hashes, a `mode` of `frozen_arena`, no teacher intervention, at least five trials each for zombie and skeleton, at least 0.80 success fraction, zero deaths, and zero safety violations. A suitable report has this shape:

```json
{
  "candidate_id": "candidate-id",
  "mode": "frozen_arena",
  "model_sha256": "...",
  "dataset_sha256": "...",
  "teacher_intervention": false,
  "safety_violations": 0,
  "mobs": {
    "zombie": {"trials": 5, "success_fraction": 0.8, "deaths": 0, "safety_violations": 0},
    "skeleton": {"trials": 5, "success_fraction": 0.8, "deaths": 0, "safety_violations": 0}
  }
}
```

The initial arena promotion qualifies only `open_surface`, and the active artifact advertises that in `qualified_environments`. The coarse tool accepts `--required-environment` and refuses an unqualified request. Promoted versions are copied under `skills_store/skills/combat.engage/vN`; `combat.engage.active.json` is replaced atomically. Rollback points the same active pointer to an existing promoted version.
