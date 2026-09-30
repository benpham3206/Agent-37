# Combat dataset and learner

Each teaching session contains `session.json` and `encounters/<encounter-id>.jsonl`. `session.json` requires an `environment` tag: `open_surface`, `underground`, `nether_open`, `fortress`, `end_island`, `bridge`, or `other`; free-form `notes` are allowed. See `docs/combat-contract.md` for the wire format. Rows synchronize at roughly 20 Hz; labels apply to encounters. Four-frame histories at 10 Hz use only `good` teacher-controlled rows within one encounter, preventing adjacent-frame leakage across train, validation, and test.

Validate before training:

```bash
agent37 combat dataset validate data/combat/zombie-basics-01
```

Training uses a 64/64 ReLU MLP and weighted binary cross entropy for sparse action outputs. Alongside relative combat state, the policy observes numeric dimension one-hot and bridge terrain summary (`support_grid`, drop depth, clearance, and nearby hazards). It never reads the session environment label. Compute normalization from training windows only; save it in `metadata.json` beside the ONNX model. Metadata stores split membership as `{session, encounter, environment}` pairs, data coverage and absent environments, and per-output/per-environment validation metrics. Dataset directories marked `synthetic: true` are useful for unit tests but are ineligible for promotion.

The arena writes `evaluation.json` in the candidate directory. Promotion requires matching candidate model and dataset hashes, a `mode` of `frozen_arena`, no teacher intervention, at least five trials each for zombie and skeleton, at least 0.80 success fraction, zero deaths, and zero safety violations. Report shape:

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

Initial promotion qualifies only `open_surface`, advertised in `qualified_environments`. The coarse tool accepts `--required-environment` and refuses an unqualified request. Promoted versions are copied under `skills_store/skills/combat.engage/vN`; `combat.engage.active.json` is replaced atomically. Rollback activates an existing promoted version.
