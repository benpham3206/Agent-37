import json
from harness.combat.dataset import validate_session, DEFAULT_FEATURES, feature_vector
from harness.combat.registry import SkillRegistry

def _row(eid="e1", tick=0):
    action={k:False for k in ["forward","back","left","right","jump","sprint","sneak","attack","use","disengage","emergency_stop","manual_abort"]}; action.update({"mouse_dx":0.,"mouse_dy":0.,"yaw_delta":0.,"pitch_delta":0.})
    return {"schema_version":1,"session_id":"s","encounter_id":eid,"tick":tick,"timestamp_ms":tick*50,"server_tick":None,"source":"privileged_hitbox","recording_state":"recording","label":"good","observation":{"self":{"position":{"x":0,"y":0,"z":0},"velocity":{"x":0,"y":0,"z":0},"yaw":0,"pitch":0,"on_ground":True},"target":None,"hostiles":[],"projectiles":[],"collision":{},"selector":{}},"teacher_action":action,"applied_action":action.copy(),"arbiter":{"source":"teacher","reason":""}}

def test_invalid_clock_rejected(tmp_path):
    (tmp_path/"encounters").mkdir(); (tmp_path/"session.json").write_text(json.dumps({"schema_version":1}))
    row=_row(); row["tick"]="0"; (tmp_path/"encounters/e.jsonl").write_text(json.dumps(row)+"\n")
    assert not validate_session(tmp_path).valid

def test_offline_evaluation_cannot_promote(tmp_path):
    c=tmp_path/"candidates/c"; c.mkdir(parents=True); (c/"model.onnx").write_bytes(b"x"); (c/"metadata.json").write_text(json.dumps({"promotion_eligible":True,"encounter_count":5,"model_sha256":"x","dataset_sha256":"d"}))
    (c/"evaluation.json").write_text(json.dumps({"candidate_id":"c","mode":"offline","teacher_intervention":False}))
    try: SkillRegistry(tmp_path).promote("c")
    except ValueError as e: assert "frozen" in str(e) or "hash" in str(e)
    else: assert False, "offline evaluation was promoted"

def test_contract_feature_order_and_terrain_observation():
    row={"observation":{"dimension":"overworld","self":{"health":20,"on_ground":True},"target":None,"terrain":{"support_grid":{"center":1,"forward":.5,"back":1,"left":1,"right":0},"drop_depth":{"forward":0,"back":2,"left":0,"right":4},"clearance":{"forward":3,"back":2,"left":1,"right":0},"hazards":True}}}
    values=feature_vector(row)
    assert len(values)==len(DEFAULT_FEATURES)==46
    assert values[DEFAULT_FEATURES.index("support_forward")] == .5
    assert values[DEFAULT_FEATURES.index("drop_right")] == 4
    assert values[DEFAULT_FEATURES.index("hazard_near")] == 1

def test_train_exports_checked_onnx_without_crossing_encounters(tmp_path):
    import pytest
    torch=pytest.importorskip("torch"); onnx=pytest.importorskip("onnx"); ort=pytest.importorskip("onnxruntime")
    from harness.combat.train import build_examples, train
    root=tmp_path/"session"; (root/"encounters").mkdir(parents=True); (root/"session.json").write_text(json.dumps({"schema_version":1,"session_id":"s","environment":"open_surface"}))
    for i in range(6):
        mob="zombie" if i%2==0 else "skeleton"; rows=[]
        for tick in range(8):
            row=_row(f"e{i}",tick); row["observation"]["target"]={"id":i,"mob_type":mob,"position":{"x":1,"y":0,"z":1},"velocity":{"x":0,"y":0,"z":0},"width":.6,"height":1.8,"aabb":{"min":{"x":.7,"y":0,"z":.7},"max":{"x":1.3,"y":1.8,"z":1.3}},"distance":1.4,"relative_position":{"x":1,"y":0,"z":1},"bearing":0,"elevation":0,"angular_error":{"yaw":0,"pitch":0},"line_of_sight":True,"in_reach":True}
            rows.append(row)
        (root/"encounters"/f"e{i}.jsonl").write_text("\n".join(json.dumps(r) for r in rows)+"\n")
    examples,splits=build_examples([root]); assert all(len(set((x["session"],x["encounter"]) for x in v))==len(v) for v in splits.values())
    meta=train([root],tmp_path/"candidate",epochs=1)
    onnx.checker.check_model(onnx.load(str(tmp_path/"candidate"/"model.onnx")))
    session=ort.InferenceSession(str(tmp_path/"candidate"/"model.onnx"),providers=["CPUExecutionProvider"])
    shape=meta["history"]*len(meta["features"]); output=session.run(None,{"observations":__import__("numpy").zeros((1,shape),dtype="float32")})[0]
    assert output.shape==(1,len(meta["outputs"]))
