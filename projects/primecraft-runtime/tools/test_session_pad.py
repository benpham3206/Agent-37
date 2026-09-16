import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("session_pad.py")


def run(root: Path, *args: str, input_text: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    command = [sys.executable, str(SCRIPT), *args, "--root", str(root)]
    return subprocess.run(command, input=input_text, text=True, capture_output=True, env=env)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        created = run(root, "new", "--actor", "prime", "--label", "test")
        assert created.returncode == 0, created.stderr
        metadata = json.loads(created.stdout)
        pad = Path(metadata["pad_path"])
        assert pad.is_file()
        assert "- **Must not break:**" in pad.read_text()

        play_created = run(root, "new", "--actor", "prime", "--label", "new-play-session", "--profile", "play")
        assert play_created.returncode == 0, play_created.stderr
        play_pad = Path(json.loads(play_created.stdout)["pad_path"])
        play_text = play_pad.read_text(encoding="utf-8")
        assert "inspect the shared catalog" not in play_text
        assert "start_presence" in play_text
        assert "does not own project code" in play_text
        assert "play/skills" not in play_text
        assert "how-to" not in play_text.lower()

        validated = run(root, "validate", "--path", str(pad))
        assert validated.returncode == 0, validated.stderr

        listed = run(root, "list", "--actor", "prime", "--json")
        assert listed.returncode == 0, listed.stderr
        listed_ids = {item["session_id"] for item in json.loads(listed.stdout)}
        assert metadata["session_id"] in listed_ids

        refused = run(root, "write", "--path", str(pad), "--reason", "checkpoint", input_text=pad.read_text())
        assert refused.returncode != 0
        assert "owner is required" in refused.stderr

        wrong_env = dict(os.environ)
        wrong_env["PRIME_PROJECT_PAD_OWNER"] = "other-session"
        refused = run(root, "write", "--path", str(pad), "--reason", "checkpoint", input_text=pad.read_text(), env=wrong_env)
        assert refused.returncode != 0
        assert "owner mismatch" in refused.stderr

        good_env = dict(os.environ)
        good_env["PRIME_PROJECT_PAD_OWNER"] = metadata["owner"]
        content = pad.read_text() + "\nA verified test result was recorded.\n"
        written = run(root, "write", "--path", str(pad), "--reason", "verified-result", input_text=content, env=good_env)
        assert written.returncode == 0, written.stderr
        assert "A verified test result" in pad.read_text()

        checkpoint_removed = content.replace(
            "- " + metadata["created_at"] + ": expected: session pad exists and is readable; actual: initialized.\n",
            "",
        )
        refused = run(root, "write", "--path", str(pad), "--reason", "checkpoint", input_text=checkpoint_removed, env=good_env)
        assert refused.returncode != 0
        assert "checkpoint history is append-only" in refused.stderr

        read_back = run(root, "read", "--session-id", metadata["session_id"])
        assert read_back.returncode == 0, read_back.stderr
        assert "A verified test result" in read_back.stdout

    print("session_pad tests: 9/9 passed")


if __name__ == "__main__":
    main()
