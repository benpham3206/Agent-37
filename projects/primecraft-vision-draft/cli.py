from __future__ import annotations

import argparse
import json
from pathlib import Path

from .actions import Actions
from .actor import Actor, Recorder
from .minecraft import Minecraft, MinecraftError
from .models import OpenAICompatible


def main() -> int:
    parser = argparse.ArgumentParser(prog="primecraft")
    parser.add_argument("command", choices=("doctor", "observe", "run", "logs"))
    parser.add_argument("--goal", default="Explore safely and report what you find")
    parser.add_argument("--runs", default="runs")
    args = parser.parse_args()
    minecraft = Minecraft()
    try:
        if args.command == "doctor":
            print(json.dumps(minecraft.health(), indent=2)); return 0
        if args.command == "observe":
            print(json.dumps(minecraft.observe(), indent=2)); return 0
        if args.command == "logs":
            for path in sorted(Path(args.runs).glob("**/*.jsonl")):
                for line in path.read_text(encoding="utf-8").splitlines():
                    value = json.loads(line)
                    if value.get("type") in {"movement", "observation", "action_result"}:
                        print(json.dumps(value, default=str))
            return 0
        run = Path(args.runs) / "current.jsonl"
        recorder = Recorder(run)
        result = Actor(Actions(minecraft, recorder), OpenAICompatible(), recorder).step(args.goal)
        print(json.dumps(result, indent=2)); return 0
    except (MinecraftError, ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)})); return 2
