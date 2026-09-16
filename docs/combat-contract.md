# Combat prototype implementation contract

This slice follows the existing plans' Python outer learner, Node Mineflayer adapter, 20 Hz event sensor, coarse tool interface, frozen evaluation and versioned artifacts. The current combat request supersedes the old Session 1 scope and speedrun extension. No planner provider, progression scripts or runtime code generation are added.

## Wire and storage v1

JSON objects use snake_case. Positions are `{x,y,z}`, angles radians, distance blocks, velocity blocks/tick. Node uses monotonic milliseconds and a local physics tick counter; `server_tick` is null unless actually available. Do not call client ticks server ticks. Unavailable observations are null, never guessed health or aggro. Hitboxes are client entity geometry, labelled `privileged_hitbox`; vanilla clients do not expose authoritative server AABBs or all mob health.

Each session has `session.json` and `encounters/<id>.jsonl`. Every JSONL row:

```
{schema_version:1, session_id, encounter_id, tick, timestamp_ms,
 server_tick:null, source:"privileged_hitbox", recording_state:"recording",
 label:"good"|"bad"|"excluded"|"unlabelled",
 observation:{self:{position,velocity,yaw,pitch,on_ground,health,hunger,armor,effects,
 held_item,hotbar_slot,cooldown,sprinting,sneaking,using_item,recent_events},
 target:null|{id,mob_type,position,velocity,width,height,aabb:{min,max},
 relative_position,distance,bearing,elevation,angular_error,line_of_sight,in_reach,
 aim_point,health,events},hostiles:[],projectiles:[],collision:{},selector:{}},
 teacher_action:{forward,back,left,right,jump,sprint,sneak,attack,use,hotbar,
 mouse_dx,mouse_dy,yaw_delta,pitch_delta,emergency_stop,manual_abort},
 applied_action:{...},arbiter:{source,reason}}
```

Actions are complete booleans, hotbar integer 0..8, finite camera deltas. Record requested and applied actions separately. Labels apply to encounters; segment boundaries create a new encounter file, including pause/resume boundaries. Training uses only good teacher-controlled rows and never crosses encounters in history windows. Human data only; synthetic verification fixtures must be declared and ineligible for promotion.

## Tactical features and model

Shared `contracts/policy.json` lists ordered relative numeric features and ordered boolean output keys. History length 4 at 10 Hz. Python builds features from observation using precisely the same definitions as Node. Model input `observations` float32 shape [batch, history*feature_count], normalization saved in metadata and applied outside ONNX. Output `logits` [batch, action_count]; sigmoid threshold .5. MLP 64/64 ReLU with weighted BCE. No learned camera. Output controls forward/back/left/right/jump/sprint/sneak/attack/use/disengage. Target type one-hot and held sword/axe/shield capabilities condition policy. Hold is all movement false. Metadata includes feature order, history, mean/std, model/dataset SHA256, splits and per-output/per-mob metrics.

Candidates live in `skills_store/candidates/<id>/{model.onnx,metadata.json}`. Registry activation is a Python-owned pointer. Only actual frozen arena evaluation can qualify promotion. Require multiple trials for zombie and skeleton, no teacher intervention, minimum success fraction and no safety violations; offline metrics alone never promote.

## Node bridge

`node bridge/server.js --host localhost --port 25565 --target zombie --session NAME --data-dir PATH --web-port 8765` starts teacher page. Python CLI launches it and owns session metadata. Viewer uses prismarine-viewer first-person, same local page has control UI. Bind localhost. Browser WS `/control`: `{type:"control",action:{...}}`, `{type:"release"}`, `{type:"emergency_stop"}`, `{type:"record",command:"start"|"pause"|"resume"|"stop"}`, `{type:"label",label:"good"|"bad"|"excluded"}`, `{type:"target",mob_type}`. Server state `{type:"state",observation,recording_state,session_id,encounter_id,arbiter,viewer_port}`. Use exclusive teacher ownership, heartbeat every 100ms, release on blur, pointer-unlock, disconnect, emergency and stale input.

HTTP coarse tools: POST `/combat/engage` with `{target_type,candidate_dir,max_duration_s,max_pursuit_distance,retreat_health}` starts one bounded invocation, returns `{invocation_id}`. GET `/combat/status` returns current/completed structured result. POST `/combat/cancel` releases controls. Candidate path is supplied by local Python registry or evaluator, never browser controls. Bot lifecycle and inference failures stop all controls. Candidate eval and active registry invocation use the same motor.

Aim and arbiter at 20 Hz, inference at 10 Hz, max one outstanding inference with timeout. Arbiter priority emergency > survival retreat > human > skill > navigation > idle. All Mineflayer control/attack/look/use writes owned by arbiter. No navigation movement plugin may bypass it; pathfinding is an adapter boundary for future integration, no navigation required for this slice.

## Arena ownership

Root agent owns `harness/combat/arena.py` and arena scripts. It launches a dedicated local Java server in a newly created marked directory with an isolated port and console, no arbitrary external-world commands. Setup commands are only sent to this child server's stdin. Human teaching does not require operator commands. No real human demonstrations are bundled or invented. Runtime smoke evidence cannot claim learned competence.
