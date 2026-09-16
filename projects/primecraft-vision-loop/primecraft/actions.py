from __future__ import annotations

import time
import uuid
from typing import Any, Mapping

from .minecraft import Minecraft


class Actions:
    def __init__(self, minecraft: Minecraft, recorder):
        self.minecraft, self.recorder = minecraft, recorder

    def observe(self):
        return self.minecraft.observe()

    def run(self, action: Mapping[str, Any]) -> dict[str, Any]:
        self._validate(action)
        action_id = str(uuid.uuid4())
        started = time.time()
        self.recorder.write({"type": "action_requested", "action_id": action_id, "action": dict(action), "at": started})
        result = self.minecraft.action(action)
        status = result.get("status", "unknown")
        post = None
        if status in {"completed", "accepted", "done"}:
            post = self.minecraft.observe()
        self.recorder.write({"type": "action_result", "action_id": action_id, "status": status, "result": result, "post_observation": post, "at": time.time()})
        return {"action_id": action_id, "status": status, "result": result, "post_observation": post}

    def stop(self):
        return self.run({"kind": "stop"})

    @staticmethod
    def _validate(action: Mapping[str, Any]) -> None:
        kind = action.get("kind")
        if kind == "stop": return
        if kind == "look":
            if not (-360 <= float(action.get("yaw_deg", 0)) <= 360 and -90 <= float(action.get("pitch_deg", 0)) <= 90): raise ValueError("look_out_of_bounds")
            return
        if kind == "move_to":
            if not isinstance(action.get("x"), (int, float)) or not isinstance(action.get("y"), (int, float)) or not isinstance(action.get("z"), (int, float)): raise ValueError("move_target_required")
            if not 1 <= int(action.get("max_seconds", 30)) <= 120: raise ValueError("move_timeout_out_of_bounds")
            return
        if kind in {"mine", "place", "craft", "interact", "attack", "use"}:
            if not isinstance(action.get("target", action.get("item", "")), str): raise ValueError("action_target_required")
            return
        raise ValueError("unknown_action_kind")
