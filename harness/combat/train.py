"""Small behavior-cloning learner; model artifacts are replaceable by a VLA later."""
from __future__ import annotations
import json, math, random, statistics, time
from pathlib import Path
from .dataset import DEFAULT_FEATURES, OUTPUTS, ENVIRONMENTS, feature_vector, action_vector, sha256_file, validate_session

def _rows(sessions):
    for root in sessions:
        root=Path(root)
        for f in sorted((root/"encounters").glob("*.jsonl")):
            rows=[]
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip(): rows.append(json.loads(line))
            if rows: yield root, rows

def build_examples(sessions, history=4, *, allow_synthetic=False):
    """Return examples and encounter-level split, never crossing encounter boundaries."""
    all_enc=[]; errors=[]; seen_ids=set(); synthetic=False
    for root, rows in _rows(sessions):
        val=validate_session(root)
        synthetic = synthetic or val.synthetic
        if synthetic and not allow_synthetic: errors.append(f"{root}: synthetic sessions require --allow-synthetic and are never promotable")
        if not val.valid: errors.extend([f"{root}: {e}" for e in val.errors] or [f"{root}: empty/invalid"])
        env=val.environment
        for eid in sorted({str(r.get("encounter_id")) for r in rows}):
            if eid in seen_ids: errors.append(f"duplicate encounter id across sessions: {eid}")
            seen_ids.add(eid)
            part=[r for r in rows if str(r.get("encounter_id"))==eid]
            # Keep only contiguous four-frame windows from good, teacher-controlled rows.
            if part and all(r.get("label")=="good" and r.get("arbiter",{}).get("source","teacher") in ("teacher","human","") for r in part): all_enc.append((str(root),eid,env,part[::2]))
    if errors: raise ValueError("invalid training data: " + "; ".join(errors[:8]))
    if len(all_enc)<3: raise ValueError("need at least three good encounters for train/validation/test split")
    rng=random.Random(37001); rng.shuffle(all_enc)
    n=len(all_enc); a=max(1,round(n*.7)); b=max(a+1,round(n*.85)); b=min(b,n-1); a=min(a,b-1)
    split={"train":all_enc[:a],"validation":all_enc[a:b],"test":all_enc[b:]}
    out={}
    for name, encs in split.items():
        xs=[]; ys=[]; envs=[]; mobs=[]
        for _,_,env,rows in encs:
            feats=[feature_vector(r) for r in rows]; acts=[action_vector(r) for r in rows]
            for i in range(history-1,len(rows)):
                xs.append([v for frame in feats[i-history+1:i+1] for v in frame]); ys.append(acts[i]); envs.append(env); mobs.append(str((rows[i].get("observation",{}).get("target") or {}).get("mob_type", "unknown")).lower())
        out[name]=(xs,ys,envs,mobs)
    memberships={k:[{"session":s,"encounter":e,"environment":env} for s,e,env,_ in v] for k,v in split.items()}
    return out, memberships

def train(sessions, out_dir, *, seed=37001, epochs=30, allow_synthetic=False):
    try:
        import torch
        from torch import nn
    except ImportError as e: raise RuntimeError("training requires torch; install the optional train dependencies") from e
    policy=json.loads((Path(__file__).parents[2]/"contracts/policy.json").read_text(encoding="utf-8"))
    history=policy["history"]; features=policy["features"]; outputs=policy["outputs"]
    if features != DEFAULT_FEATURES or outputs != OUTPUTS: raise ValueError("contracts/policy.json does not match Python feature/output definitions")
    examples,splits=build_examples(sessions,history,allow_synthetic=allow_synthetic)
    torch.manual_seed(seed)
    X=torch.tensor(examples["train"][0],dtype=torch.float32); Y=torch.tensor(examples["train"][1],dtype=torch.float32)
    if len(X)==0: raise ValueError("no usable good teacher rows")
    mean=X.mean(0); std=X.std(0); std[std<1e-6]=1
    class Policy(nn.Module):
        def __init__(self):
            super().__init__(); self.net=nn.Sequential(nn.Linear(X.shape[1],64),nn.ReLU(),nn.Linear(64,64),nn.ReLU(),nn.Linear(64,len(outputs)))
        def forward(self,x): return self.net(x)
    model=Policy(); pos=Y.sum(0); neg=len(Y)-pos; weights=(neg+1)/(pos+1)
    loss_fn=nn.BCEWithLogitsLoss(pos_weight=weights)
    opt=torch.optim.Adam(model.parameters(),lr=.001)
    for _ in range(epochs):
        opt.zero_grad(); loss=loss_fn(model((X-mean)/std),Y); loss.backward(); opt.step()
    metrics={}
    with torch.no_grad():
        for split,(xs,ys,envs,mobs) in examples.items():
            if not xs: continue
            pred=(torch.sigmoid(model((torch.tensor(xs)-mean)/std))>=.5).int(); truth=torch.tensor(ys).int()
            metrics[split]={}
            for j,name in enumerate(outputs):
                tp=((pred[:,j]==1)&(truth[:,j]==1)).sum().item(); fp=((pred[:,j]==1)&(truth[:,j]==0)).sum().item(); fn=((pred[:,j]==0)&(truth[:,j]==1)).sum().item()
                precision=tp/(tp+fp) if tp+fp else 0.; recall=tp/(tp+fn) if tp+fn else 0.; f1=2*precision*recall/(precision+recall) if precision+recall else 0.
                metrics[split][name]={"accuracy":float((pred[:,j]==truth[:,j]).float().mean()),"precision":precision,"recall":recall,"f1":f1}
            metrics[split]["overall"]=float((pred==truth).float().mean())
            metrics[split]["by_environment"]={}
            for env in sorted(set(envs)):
                indexes=[i for i,e in enumerate(envs) if e==env]
                if indexes: metrics[split]["by_environment"][env]={"rows":len(indexes),"overall":float((pred[indexes]==truth[indexes]).float().mean())}
            metrics[split]["by_mob"]={}
            for mob in sorted(set(mobs)):
                indexes=[i for i,m in enumerate(mobs) if m==mob]
                if indexes: metrics[split]["by_mob"][mob]={"rows":len(indexes),"overall":float((pred[indexes]==truth[indexes]).float().mean())}
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True); tmp=out/"model.onnx.tmp"
    dummy=torch.zeros((1,X.shape[1]))
    try: torch.onnx.export(model,(dummy,),str(tmp),input_names=["observations"],output_names=["logits"],opset_version=17,dynamo=False)
    except Exception as e: raise RuntimeError(f"ONNX export failed: {e}")
    tmp.replace(out/"model.onnx")
    ds_hash=_hash_sessions(sessions)
    covered=sorted({m["environment"] for v in splits.values() for m in v}); synthetic=any(validate_session(s).synthetic for s in sessions); meta={"schema_version":1,"artifact_type":"combat.tactical_policy","history":history,"rate_hz":policy["rate_hz"],"features":features,"outputs":outputs,"normalization":{"mean":mean.tolist(),"std":std.tolist()},"splits":splits,"encounter_count":sum(len(v) for v in splits.values()),"data_coverage":{"environments":covered,"absent_environments":[e for e in ENVIRONMENTS if e not in covered]},"qualified_environments":[],"metrics":metrics,"dataset_sha256":ds_hash,"model_sha256":sha256_file(out/"model.onnx"),"created_at":time.time(),"synthetic":synthetic,"promotion_eligible":not synthetic}
    (out/"metadata.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    return meta

def _hash_sessions(paths):
    import hashlib
    h=hashlib.sha256()
    for p in sorted(map(str,paths)):
        root=Path(p)
        for f in sorted(root.rglob("*.jsonl")):
            h.update(f.relative_to(root).as_posix().encode()); h.update(f.read_bytes())
    return h.hexdigest()
