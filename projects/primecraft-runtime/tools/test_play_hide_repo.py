from __future__ import annotations

import inspect
import os
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path


PLAY = Path(r"D:\Codex\2026-08-26\prime-agent\play")
HIDDEN_IMPL = Path(
    r"D:\Codex\2026-08-26\plea\.prime\agent\skills\minecraft-control\src\minecraft_control\__init__.py"
)
os.environ.setdefault("PRIMEBOT_BRIDGE_PATH", str(HIDDEN_IMPL))
sys.path.insert(0, str(PLAY))

from play_hide_repo import RepoHiddenError, _orig_open, install, is_hidden, uninstall  # noqa: E402


class PlayHideRepoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        install()

    @classmethod
    def tearDownClass(cls) -> None:
        uninstall()

    def test_plea_source_is_hidden_play_skills_are_not(self) -> None:
        allowed = PLAY / "skills" / "primebot" / "SKILL.md"
        self.assertTrue(is_hidden(HIDDEN_IMPL))
        self.assertFalse(is_hidden(allowed))
        with self.assertRaises(RepoHiddenError):
            HIDDEN_IMPL.read_text(encoding="utf-8")
        self.assertIn("PrimeBot", allowed.read_text(encoding="utf-8"))

    def test_audit_hook_blocks_original_open(self) -> None:
        with self.assertRaises(RepoHiddenError):
            _orig_open(HIDDEN_IMPL, encoding="utf-8")

    def test_joystick_source_does_not_embed_repo_path(self) -> None:
        source = (PLAY / "minecraft_control.py").read_text(encoding="utf-8")
        self.assertNotIn("plea", source.lower())
        self.assertNotIn(r"D:\Codex\2026-08-26\plea", source)
        self.assertIn("PRIMEBOT_BRIDGE_PATH", source)

    def test_inspect_cannot_dump_joystick_implementation(self) -> None:
        import minecraft_control

        source = inspect.getsource(minecraft_control.health)
        self.assertNotIn("plea", source.lower())
        self.assertNotIn("urllib", source)
        self.assertLess(len(source.splitlines()), 20)

    def test_joystick_hides_adapter_and_checkpoint_apis(self) -> None:
        import minecraft_control

        names = {name for name in dir(minecraft_control) if not name.startswith("_")}
        self.assertIn("presence_action", names)
        self.assertNotIn("adapter_url", names)
        self.assertNotIn("start_chat_episode", names)
        self.assertNotIn("_validate_presence_action", names)

    def test_user_http_to_adapter_is_blocked(self) -> None:
        with self.assertRaises(RepoHiddenError):
            urllib.request.urlopen("http://127.0.0.1:18765/healthz", timeout=2)

    def test_play_temp_write_still_works(self) -> None:
        with tempfile.TemporaryDirectory(dir=PLAY) as temp:
            path = Path(temp) / "note.txt"
            path.write_text("ok\n", encoding="utf-8")
            self.assertEqual(path.read_text(encoding="utf-8"), "ok\n")


if __name__ == "__main__":
    unittest.main()
