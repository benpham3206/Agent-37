#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from play_harness import (
    format_play_launch_flags,
    parse_agent_list_payload,
    play_launch_flags,
    play_session_ids_to_stop,
    preferred_play_session_id,
    stop_play_sessions,
)


PLAY = r"D:\Codex\2026-08-26\prime-agent\play\sessions\a.jsonl"
OPT = r"D:\Codex\2026-08-26\prime-agent\optimize\sessions\b.jsonl"


class PlaySessionStopSelectionTests(unittest.TestCase):
    def test_stops_live_and_draft_play_not_optimize_or_stopped(self) -> None:
        payload = {
            "sessions": [
                {
                    "id": "opt-live",
                    "lifecycle": "live",
                    "sessionFile": OPT,
                    "modified": "2026-08-30T05:00:00.000Z",
                },
                {
                    "id": "play-old",
                    "lifecycle": "live",
                    "sessionFile": PLAY.replace("a.jsonl", "old.jsonl"),
                    "modified": "2026-08-30T04:00:00.000Z",
                },
                {
                    "id": "play-draft",
                    "lifecycle": "draft",
                    "sessionFile": PLAY.replace("a.jsonl", "draft.jsonl"),
                    "modified": "2026-08-30T04:50:00.000Z",
                },
                {
                    "id": "play-dead",
                    "lifecycle": "stopped",
                    "sessionFile": PLAY.replace("a.jsonl", "dead.jsonl"),
                    "modified": "2026-08-30T06:00:00.000Z",
                },
            ]
        }
        self.assertEqual(play_session_ids_to_stop(payload), ["play-draft", "play-old"])

    def test_prefers_live_play_for_chat_forward(self) -> None:
        payload = {
            "sessions": [
                {
                    "id": "play-draft",
                    "lifecycle": "draft",
                    "sessionFile": PLAY.replace("a.jsonl", "draft.jsonl"),
                    "modified": "2026-08-30T05:00:00.000Z",
                },
                {
                    "id": "play-live",
                    "lifecycle": "live",
                    "sessionFile": PLAY,
                    "modified": "2026-08-30T04:00:00.000Z",
                },
            ]
        }
        self.assertEqual(preferred_play_session_id(payload), "play-live")

    def test_empty_when_no_play(self) -> None:
        self.assertEqual(
            play_session_ids_to_stop({"sessions": [{"id": "x", "lifecycle": "live", "sessionFile": OPT}]}),
            [],
        )

    def test_parses_list_json_with_trailing_garbage(self) -> None:
        payload = parse_agent_list_payload(
            '{"sessions":[{"id":"play-1","lifecycle":"live","sessionFile":"D:/prime-agent/play/sessions/one.jsonl","modified":"1"}]}\nWARNING extra\n'
        )
        self.assertEqual(play_session_ids_to_stop(payload or {}), ["play-1"])

    def test_parses_concatenated_list_json(self) -> None:
        blob = (
            '{"sessions":[{"id":"play-1","lifecycle":"live","sessionFile":"D:/prime-agent/play/sessions/one.jsonl","modified":"1"}]}'
        )
        payload = parse_agent_list_payload(blob + "\n" + blob)
        self.assertEqual(play_session_ids_to_stop(payload or {}), ["play-1"])


class StopPlaySessionsTests(unittest.TestCase):
    def test_issues_stop_for_each_play_id(self) -> None:
        calls: list[list[str]] = []

        def runner(argv, **_kwargs):
            calls.append(list(argv))

            class Result:
                returncode = 0
                stdout = '{"sessions":[]}' if argv[1] == "list" else ""
                stderr = ""

            if argv[1] == "list":
                Result.stdout = (
                    '{"sessions":['
                    '{"id":"play-1","lifecycle":"live",'
                    '"sessionFile":"D:/prime-agent/play/sessions/one.jsonl","modified":"2"},'
                    '{"id":"play-2","lifecycle":"draft",'
                    '"sessionFile":"D:/prime-agent/play/sessions/two.jsonl","modified":"1"}'
                    "]}"
                )
            return Result()

        receipt = stop_play_sessions("prime-agent.cmd", runner=runner)
        self.assertEqual(receipt["stopped"], ["play-1", "play-2"])
        self.assertEqual(
            [call[1:] for call in calls if call[1] == "stop"],
            [["stop", "play-1"], ["stop", "play-2"]],
        )

    def test_already_gone_session_counts_as_stopped(self) -> None:
        def runner(argv, **_kwargs):
            class Result:
                returncode = 1 if argv[1] == "stop" else 0
                stdout = ""
                stderr = "Error: Unknown active session: play-1" if argv[1] == "stop" else ""

            if argv[1] == "list":
                Result.returncode = 0
                Result.stdout = (
                    '{"sessions":[{"id":"play-1","lifecycle":"live",'
                    '"sessionFile":"D:/prime-agent/play/sessions/one.jsonl","modified":"1"}]}'
                )
                Result.stderr = ""
            return Result()

        receipt = stop_play_sessions("prime-agent.cmd", runner=runner)
        self.assertEqual(receipt["stopped"], ["play-1"])
        self.assertEqual(receipt["errors"], [])


class PlaySkillIsolationTests(unittest.TestCase):
    def test_launch_flags_disable_project_skill_discovery(self) -> None:
        root = Path(r"D:\Codex\2026-08-26\prime-agent\play")
        flags = play_launch_flags(root)
        self.assertEqual(flags[0], "--no-skills")
        self.assertIn("--no-context-files", flags)
        rendered = format_play_launch_flags(root)
        self.assertNotIn("minecraft-control", rendered)
        self.assertNotIn("plea-optimize", rendered)
        self.assertIn("primebot", rendered)
        self.assertNotIn("write-minecraft-skill", rendered)

    def test_play_skills_are_minecraft_how_tos_outside_the_repo_skill_tree(self) -> None:
        skills = Path(r"D:\Codex\2026-08-26\prime-agent\play\skills")
        primebot = (skills / "primebot" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("start_presence", primebot)
        self.assertIn("presence_action", primebot)
        self.assertNotIn("inspect.getsource", primebot)
        self.assertNotIn("primecraft.ps1", primebot)
        self.assertNotIn("plea", primebot.lower())
        self.assertFalse((skills / "write-minecraft-skill" / "SKILL.md").is_file())
        writer = Path(r"D:\Codex\2026-08-26\prime-agent\play\optional-skills\write-minecraft-skill\SKILL.md")
        self.assertTrue(writer.is_file())
        self.assertNotIn(".prime/agent/skills", writer.read_text(encoding="utf-8"))


class CommandSurfaceTests(unittest.TestCase):
    def test_primecraft_exposes_play_restart(self) -> None:
        source = Path(__file__).with_name("primecraft.ps1").read_text(encoding="utf-8")
        self.assertIn("'play-restart'", source)
        self.assertIn("Restart-PlayHarness", source)
        self.assertIn("--launch-flags", source)

    def test_play_skill_forbids_repo_work(self) -> None:
        skill = Path(r"D:\Codex\2026-08-26\prime-agent\play\skills\primebot\SKILL.md")
        source = skill.read_text(encoding="utf-8")
        self.assertIn("You only play Minecraft", source)
        self.assertIn("Forbidden", source)
        self.assertNotIn("editing project files", source)
        self.assertNotIn("primecraft.ps1", source)
        self.assertNotIn("plea", source.lower())

    def test_play_wrapper_hides_repo_cwd(self) -> None:
        source = Path(__file__).with_name("prime-agent-on-d.ps1").read_text(encoding="utf-8")
        self.assertIn("IPYTHONDIR", source)
        self.assertIn("$agentCwd = $profileRoot", source)
        self.assertIn("PRIMEBOT_BRIDGE_PATH", source)
        self.assertNotIn("PYTHONPATH", source)

    def test_prime_agent_cmd_routes_play_restart(self) -> None:
        cmd = Path.home() / ".local" / "bin" / "prime-agent.cmd"
        source = cmd.read_text(encoding="utf-8")
        self.assertIn("play", source.lower())
        self.assertIn("restart", source.lower())
        self.assertIn("play-restart", source)


if __name__ == "__main__":
    unittest.main()
