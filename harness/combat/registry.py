"""Versioned combat skill registry with conservative promotion and rollback."""
from __future__ import annotations
import json, os, shutil, time, re
from pathlib import Path

class SkillRegistry:
    def __init__(self, root="skills_store"):
        self.root=Path(root); self.candidates=self.root/"candidates"; self.skills=self.root/"skills"; self.candidates.mkdir(parents=True,exist_ok=True); self.skills.mkdir(parents=True,exist_ok=True)
    def candidate(self, candidate_id):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", candidate_id): raise ValueError("invalid candidate id")
        p=self.candidates/candidate_id
        if not (p/"model.onnx").exists() or not (p/"metadata.json").exists(): raise FileNotFoundError(f"incomplete candidate: {candidate_id}")
        return p
    def evaluate_report(self,candidate_id):
        p=self.candidate(candidate_id)/("evaluation.json")
        if not p.exists(): raise ValueError("candidate has no frozen evaluation.json")
        return json.loads(p.read_text(encoding="utf-8"))
    def promote(self,candidate_id, skill="combat.engage"):
        src=self.candidate(candidate_id); meta=json.loads((src/"metadata.json").read_text(encoding="utf-8")); report=self.evaluate_report(candidate_id)
        if meta.get("synthetic") or not meta.get("promotion_eligible",False) or int(meta.get("encounter_count",0))<5: raise ValueError("candidate is synthetic, marked ineligible, or lacks five real encounters")
        if report.get("candidate_id") != candidate_id: raise ValueError("evaluation candidate mismatch")
        if report.get("model_sha256") != meta.get("model_sha256") or report.get("dataset_sha256") != meta.get("dataset_sha256"): raise ValueError("evaluation hashes do not match candidate metadata")
        if not report.get("completed") or report.get("model_sha256_after") != meta.get("model_sha256"): raise ValueError("promotion requires a completed immutable evaluation")
        if report.get("mode")!="frozen_arena" or report.get("teacher_intervention",True): raise ValueError("promotion requires frozen arena evaluation without teacher intervention")
        arena=report.get("arena",{}); environment=arena.get("qualified_environment")
        if environment != "open_surface": raise ValueError("initial promotion gate only qualifies open_surface")
        mobs=report.get("mobs",{}); required=("zombie","skeleton")
        for mob in required:
            m=mobs.get(mob,{})
            if int(m.get("trials",0))<5 or float(m.get("success_fraction",0))<.8 or int(m.get("safety_violations",1))>0 or int(m.get("deaths",1))>0: raise ValueError(f"promotion gate failed for {mob}")
        if int(report.get("safety_violations",1))>0: raise ValueError("promotion gate failed: safety violations")
        versions=sorted([p.name for p in (self.skills/skill).glob("v*")]) if (self.skills/skill).exists() else []
        version=f"v{len(versions)+1}"; dest=self.skills/skill/version; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copytree(src,dest)
        promoted_meta=json.loads((dest/"metadata.json").read_text(encoding="utf-8")); promoted_meta["qualified_environments"]=[environment]; (dest/"metadata.json").write_text(json.dumps(promoted_meta,indent=2),encoding="utf-8")
        (dest/"promotion.json").write_text(json.dumps({"skill":skill,"version":version,"candidate_id":candidate_id,"qualified_environments":[environment],"evaluation":report,"promoted_at":time.time()},indent=2),encoding="utf-8")
        pointer=self.skills/(skill+".active.json"); tmp=pointer.with_suffix(".tmp"); tmp.write_text(json.dumps({"skill":skill,"version":version,"path":str(dest.resolve())},indent=2),encoding="utf-8"); os.replace(tmp,pointer)
        return {"skill":skill,"version":version,"path":str(dest)}
    def active(self,skill="combat.engage"):
        p=self.skills/(skill+".active.json")
        if not p.exists(): return None
        data=json.loads(p.read_text(encoding="utf-8")); path=Path(data["path"])
        if not (path/"model.onnx").exists() or not (path/"metadata.json").exists(): raise ValueError("active skill artifact is missing")
        meta=json.loads((path/"metadata.json").read_text(encoding="utf-8"))
        from .dataset import sha256_file
        if meta.get("model_sha256") != sha256_file(path/"model.onnx"): raise ValueError("active skill model hash mismatch")
        return data
    def rollback(self,skill,version):
        target=self.skills/skill/version
        if not re.fullmatch(r"v[0-9]+", version) or not (target/"model.onnx").exists() or not (target/"promotion.json").exists(): raise ValueError(f"unknown promoted version: {version}")
        pointer=self.skills/(skill+".active.json"); tmp=pointer.with_suffix(".tmp"); tmp.write_text(json.dumps({"skill":skill,"version":version,"path":str(target.resolve()),"rolled_back_at":time.time()},indent=2),encoding="utf-8"); os.replace(tmp,pointer)
        return self.active(skill)
