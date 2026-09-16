from __future__ import annotations
import argparse, json
from pathlib import Path
from .actions import Actions
from .actor import Actor, Recorder
from .minecraft import Minecraft, MinecraftError
from .models import OpenAICompatible

def main() -> int:
    parser=argparse.ArgumentParser(prog="primecraft"); parser.add_argument("command", choices=("doctor","observe","smoke","run","logs","remember","recall","propose-skill","run-skill","promote","rollback")); parser.add_argument("name", nargs="?"); parser.add_argument("--goal", default="Explore safely and report what you find"); parser.add_argument("--runs", default="runs"); parser.add_argument("--memory", default="runs/memory.jsonl"); parser.add_argument("--skills", default="skills"); parser.add_argument("--value", default=""); parser.add_argument("--steps", default="[]"); parser.add_argument("--evidence"); parser.add_argument("--version", type=int); parser.add_argument("--max-steps", type=int, default=8); args=parser.parse_args(); minecraft=Minecraft()
    try:
        from .memory import Memory
        from .skills import Skills
        if args.command == "remember": print(json.dumps(Memory(args.memory).remember(args.name or "note", args.value))); return 0
        if args.command == "recall": print(json.dumps(Memory(args.memory).recall(args.value))); return 0
        skills = Skills(args.skills)
        if args.command == "propose-skill": print(skills.propose(args.name or "candidate", json.loads(args.steps))); return 0
        if args.command == "promote": print(skills.promote_from_evidence(args.name or "candidate", args.evidence)); return 0
        if args.command == "rollback": print(skills.rollback(args.name or "candidate", args.version)); return 0
        if args.command == "doctor": print(json.dumps(minecraft.health(), indent=2)); return 0
        if args.command == "observe": print(json.dumps(minecraft.observe(), indent=2)); return 0
        if args.command == "smoke":
            health=minecraft.health(); observation=minecraft.observe()
            from .observations import Observation
            parsed=Observation.from_payload(observation)
            print(json.dumps({"health":health,"observation_id":parsed.id,"image_present":bool(parsed.image),"state_keys":sorted(parsed.state)}, indent=2)); return 0
        if args.command == "logs":
            for path in sorted(Path(args.runs).glob("**/*.jsonl")):
                for line in path.read_text(encoding="utf-8").splitlines(): print(line)
            return 0
        if args.command == "run-skill":
            recorder=Recorder(Path(args.runs)/"skill.jsonl"); actions=Actions(minecraft, recorder)
            def call(tool, payload):
                if tool == "observe": return actions.observe()
                if tool == "act": return actions.run(payload)
                if tool == "stop": return actions.stop()
                if tool == "remember": return Memory(args.memory).remember(payload.get("kind", "skill"), payload.get("value", payload))
                if tool == "recall": return Memory(args.memory).recall(payload.get("query", ""))
                raise ValueError("unsupported_skill_tool")
            print(json.dumps(skills.run(args.name or "candidate", call), default=str, indent=2)); return 0
        if not 1 <= args.max_steps <= 32: raise ValueError("max_steps_out_of_bounds")
        recorder=Recorder(Path(args.runs)/"current.jsonl"); print(json.dumps(Actor(Actions(minecraft, recorder), OpenAICompatible(), recorder).run(args.goal, args.max_steps), indent=2)); return 0
    except (MinecraftError, ValueError, OSError) as exc: print(json.dumps({"error":str(exc)})); return 2

if __name__ == "__main__": raise SystemExit(main())
