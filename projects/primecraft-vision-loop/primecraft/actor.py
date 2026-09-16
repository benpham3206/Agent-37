from __future__ import annotations
import json, time
from pathlib import Path
from .actions import Actions
from .models import OpenAICompatible
from .observations import Observation

class Recorder:
    def __init__(self, path: Path):
        self.path = path; self.path.parent.mkdir(parents=True, exist_ok=True)
    def write(self, value):
        with self.path.open("a", encoding="utf-8") as handle: handle.write(json.dumps(value, default=str) + "\n")

class Actor:
    def __init__(self, actions: Actions, model: OpenAICompatible, recorder: Recorder): self.actions, self.model, self.recorder = actions, model, recorder
    def run(self, goal: str, max_steps: int = 8):
        results = []
        for _ in range(max_steps): results.append(self.step(goal))
        return results

    def step(self, goal: str):
        payload = self.actions.observe(); observation = Observation.from_payload(payload)
        self.recorder.write({"type":"observation","id":observation.id,"payload":payload,"at":time.time()})
        action = self.model.decide("Goal: " + goal + ". Choose a bounded action and verify its effect.", observation.image, observation.state)
        if not isinstance(action, dict) or not isinstance(action.get("kind"), str): raise ValueError("invalid_model_action")
        return self.actions.run(action)
