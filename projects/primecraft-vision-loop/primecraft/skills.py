"""Declarative, bounded skills with candidate staging and evidence promotion."""

from __future__ import annotations

import json
import hashlib
import re
import shutil
from pathlib import Path
from typing import Any, Callable


class Skills:
    TOOLS = frozenset({"observe", "look", "move_to", "act", "stop", "remember", "recall"})
    MAX_STEPS = 16

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.candidates = self.root / "candidates"
        self.approved = self.root / "approved"
        self.archive = self.root / "archive"

    @staticmethod
    def _safe_name(name: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
            raise ValueError("skill name must be a simple filename")
        return name

    @classmethod
    def _check_steps(cls, steps: list[dict[str, Any]]) -> None:
        if not steps or len(steps) > cls.MAX_STEPS:
            raise ValueError(f"skill must contain 1-{cls.MAX_STEPS} steps")
        if any(step.get("tool") not in cls.TOOLS or "skill" in step for step in steps):
            raise ValueError("skill contains an unsupported or nested tool")

    def propose(self, name: str, steps: list[dict[str, Any]], *, reason: str = "") -> Path:
        """Write a candidate document; steps are tool names plus JSON arguments."""
        name = self._safe_name(name)
        self._check_steps(steps)
        document = {"name": name, "version": 1, "reason": reason, "steps": steps}
        target = self.candidates / f"{name}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        return target

    def promote_from_evidence(self, name: str, evidence_path: str | Path) -> Path:
        """Operator action: promote only a recorder-signed, matching run record."""
        name = self._safe_name(name)
        source = self.candidates / f"{name}.json"
        if not source.exists():
            raise FileNotFoundError(source)
        evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if (evidence.get("candidate") != name or evidence.get("candidate_sha256") != digest
                or evidence.get("environment") != "minecraft"
                or evidence.get("outcome") != "pass" or not evidence.get("run_id")
                or evidence.get("reviewed") is not True or not evidence.get("reviewer")):
            raise ValueError("promotion requires matching recorder evidence and explicit operator review")
        document = json.loads(source.read_text(encoding="utf-8"))
        versions = [int(path.stem.rsplit(".v", 1)[1]) for path in self.approved.glob(f"{name}.v*.json")]
        document["version"] = max(versions, default=0) + 1
        target = self.approved / f"{name}.v{document['version']}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        document["evidence"] = evidence
        target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        active = self.approved / f"{name}.json"
        if active.exists():
            self.archive.mkdir(parents=True, exist_ok=True)
            old = json.loads(active.read_text(encoding="utf-8"))
            shutil.copyfile(active, self.archive / f"{name}.v{old['version']}.json")
        shutil.copyfile(target, active)
        return target

    def rollback(self, name: str, version: int) -> Path:
        """Restore an archived approved version by copying it into the active slot."""
        name = self._safe_name(name)
        source = self.archive / f"{name}.v{version}.json"
        if not source.exists():
            raise FileNotFoundError(source)
        target = self.approved / f"{name}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return target

    def load(self, name: str) -> dict[str, Any]:
        name = self._safe_name(name)
        target = self.approved / f"{name}.json"
        if not target.exists():
            versions = sorted(self.approved.glob(f"{name}.v*.json"))
            if not versions:
                raise FileNotFoundError(target)
            target = versions[-1]
        return json.loads(target.read_text(encoding="utf-8"))

    def run(self, name: str, call: Callable[[str, dict[str, Any]], Any], *, max_steps: int = 16) -> list[Any]:
        """Execute only listed tools, with a hard step bound and no code loading."""
        steps = self.load(name)["steps"]
        if len(steps) > min(max_steps, self.MAX_STEPS):
            raise ValueError("skill exceeds step bound")
        results = []
        for step in steps:
            result = call(step["tool"], step.get("args", {}))
            results.append(result)
            if isinstance(result, dict) and (result.get("terminal") is False or result.get("status") in {"accepted", "running", "pending", "failed", "error"}):
                break
        return results
