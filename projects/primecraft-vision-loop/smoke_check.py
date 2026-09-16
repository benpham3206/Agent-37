"""Small offline boundary check; it does not claim Minecraft gameplay success."""

from pathlib import Path
from tempfile import TemporaryDirectory
from primecraft.memory import Memory
from primecraft.skills import Skills


def main() -> None:
    with TemporaryDirectory() as folder:
        memory = Memory(Path(folder) / "memory.jsonl")
        record = memory.remember("lesson", {"text": "reroute"})
        assert record["id"] and record["timestamp"] and memory.recall("reroute")
        skills = Skills(Path(folder) / "skills")
        for name in ("../escape", "bad/name"):
            try:
                skills.propose(name, [{"tool": "observe"}])
            except ValueError:
                pass
            else:
                raise AssertionError("unsafe skill name accepted")
        skills.propose("walk", [{"tool": "observe"}, {"tool": "move_to"}])
        try:
            skills.load("walk")
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("unapproved skill loaded")
        calls = []
        skills.approved.mkdir(parents=True)
        (skills.approved / "walk.json").write_text('{"name":"walk","version":1,"steps":[{"tool":"observe"},{"tool":"move_to"}]}')
        executed = skills.run("walk", lambda tool, args: calls.append(tool) or {"status": "failed"})
        assert executed and calls == ["observe"]
        evidence = Path(folder) / "evidence.json"
        evidence.write_text('{"candidate":"walk","environment":"minecraft","outcome":"pass","run_id":"r","reviewed":true,"reviewer":"human","candidate_sha256":"wrong"}')
        try:
            skills.promote_from_evidence("walk", evidence)
        except ValueError:
            pass
        else:
            raise AssertionError("unreviewed or mismatched evidence accepted")
    print("primecraft smoke boundaries ok (offline; no gameplay claim)")


if __name__ == "__main__":
    main()
