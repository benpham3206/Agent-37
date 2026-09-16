"""Coarse agent-facing combat tool. It never exposes tick-level controls."""
from __future__ import annotations
import json, urllib.request
from pathlib import Path
from .registry import SkillRegistry

class CombatTool:
    def __init__(self, registry="skills_store", bridge="http://127.0.0.1:8765"):
        self.registry=SkillRegistry(registry); self.bridge=bridge.rstrip("/")
    def engage(self,target_type,required_environment=None,**limits):
        active=self.registry.active()
        if not active: raise RuntimeError("no active combat skill")
        if required_environment and required_environment not in json.loads((Path(active["path"])/"metadata.json").read_text(encoding="utf-8")).get("qualified_environments",[]): raise RuntimeError(f"active combat skill is not qualified for {required_environment}")
        body={"target_type":target_type,"candidate_dir":active["path"],**limits}
        req=urllib.request.Request(self.bridge+"/combat/engage",json.dumps(body).encode(),{"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(req,timeout=5) as r: return json.load(r)
    def status(self):
        with urllib.request.urlopen(self.bridge+"/combat/status",timeout=5) as r: return json.load(r)
    def cancel(self):
        req=urllib.request.Request(self.bridge+"/combat/cancel",b"{}",{"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(req,timeout=5) as r: return json.load(r)
