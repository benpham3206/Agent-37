#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from ensure_primebot_presence import parse_chat_command, parse_player_chat


class ChatCommandTests(unittest.TestCase):
    def test_join_and_leave(self) -> None:
        self.assertEqual(parse_chat_command("[21:00:00] [Server thread/INFO]: [Not Secure] <6ento> primebot join"), "join")
        self.assertEqual(parse_chat_command("<6ento> PrimeBot LEAVE"), "leave")
        self.assertEqual(parse_chat_command("<6ento> primebot leave please"), "leave")

    def test_ignores_noise_and_self(self) -> None:
        self.assertIsNone(parse_chat_command("<6ento> hello primebot"))
        self.assertIsNone(parse_chat_command("<PrimeBot> primebot leave"))
        self.assertIsNone(parse_chat_command("primebot join"))


class PlayerChatTests(unittest.TestCase):
    def test_player_goal_chat(self) -> None:
        self.assertEqual(
            parse_player_chat("[21:43:45] [Server thread/INFO]: [Not Secure] <6ento> craft a stone pickaxe"),
            ("6ento", "craft a stone pickaxe"),
        )

    def test_skips_commands_and_bot(self) -> None:
        self.assertIsNone(parse_player_chat("<6ento> primebot leave"))
        self.assertIsNone(parse_player_chat("<PrimeBot> hey 6ento, got your chat: craft a stone pickaxe"))


class PlayForwardPromptTests(unittest.TestCase):
    def test_forwarder_tells_play_not_to_edit_repo(self) -> None:
        source = Path(__file__).with_name("ensure_primebot_presence.py").read_text(encoding="utf-8")
        self.assertIn("PLAY ONLY", source)
        self.assertIn("Do not read, search, or edit project files", source)


if __name__ == "__main__":
    unittest.main()
