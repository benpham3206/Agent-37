#!/usr/bin/env python3
"""Stop live/draft PLAY Prime-Agent sessions without touching OPTIMIZE or Minecraft."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

Runner = Callable[..., Any]


def parse_agent_list_payload(stdout: str) -> dict[str, Any] | None:
    text = stdout or ""
    start = text.find("{")
    if start < 0:
        return None
    try:
        payload, _end = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _session_file(session: Mapping[str, Any]) -> str:
    return str(session.get("sessionFile") or "").replace("\\", "/").lower()


def open_play_sessions(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    sessions = payload.get("sessions")
    if not isinstance(sessions, list):
        return []
    play: list[dict[str, Any]] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        if "/play/" not in _session_file(session):
            continue
        if str(session.get("lifecycle") or "") not in {"live", "draft"}:
            continue
        play.append(session)
    play.sort(key=lambda item: str(item.get("modified") or item.get("created") or ""), reverse=True)
    return play


def play_session_ids_to_stop(payload: Mapping[str, Any]) -> list[str]:
    ids: list[str] = []
    for session in open_play_sessions(payload):
        session_id = session.get("id")
        if isinstance(session_id, str) and session_id:
            ids.append(session_id)
    return ids


def preferred_play_session_id(payload: Mapping[str, Any]) -> str | None:
    sessions = open_play_sessions(payload)
    live = [session for session in sessions if str(session.get("lifecycle") or "") == "live"]
    pool = live or sessions
    if not pool:
        return None
    session_id = pool[0].get("id")
    return session_id if isinstance(session_id, str) and session_id else None


def play_skill_dirs(play_root: Path) -> list[Path]:
    skills_root = Path(play_root) / "skills"
    if not skills_root.is_dir():
        return []
    found: list[Path] = []
    for child in sorted(skills_root.iterdir()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            found.append(child)
    return found


def play_launch_flags(play_root: Path) -> list[str]:
    flags = ["--no-skills", "--no-context-files"]
    for skill_dir in play_skill_dirs(play_root):
        flags.extend(["--skill", str(skill_dir)])
    return flags


def format_play_launch_flags(play_root: Path) -> str:
    parts: list[str] = []
    for item in play_launch_flags(play_root):
        if any(ch in item for ch in " '\""):
            parts.append("'" + item.replace("'", "''") + "'")
        else:
            parts.append(item)
    return " ".join(parts)


def stop_play_sessions(prime_agent_cmd: str, *, runner: Runner = subprocess.run) -> dict[str, Any]:
    listed = runner(
        [prime_agent_cmd, "list", "--json"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if listed.returncode != 0:
        return {"stopped": [], "errors": ["list_failed"]}
    payload = parse_agent_list_payload(listed.stdout or "")
    if payload is None:
        return {"stopped": [], "errors": ["list_invalid"]}
    stopped: list[str] = []
    errors: list[str] = []
    for session_id in play_session_ids_to_stop(payload):
        result = runner(
            [prime_agent_cmd, "stop", session_id],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        detail = (result.stderr or result.stdout or "stop_failed").strip()
        if result.returncode == 0 or "unknown active session" in detail.lower():
            stopped.append(session_id)
        else:
            errors.append(f"{session_id}:{detail[:200]}")
    return {"stopped": stopped, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stop PLAY Prime-Agent sessions.")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--launch-flags", action="store_true")
    parser.add_argument("--play-root", default="")
    parser.add_argument("--prime-agent-cmd", default="")
    args = parser.parse_args(argv)
    if args.launch_flags:
        play_root = Path(args.play_root.strip() or r"D:\Codex\2026-08-26\prime-agent\play")
        sys.stdout.write(format_play_launch_flags(play_root) + "\n")
        return 0
    if not args.stop:
        parser.print_help()
        return 2
    cmd = args.prime_agent_cmd.strip() or str(Path.home() / ".local" / "bin" / "prime-agent.cmd")
    receipt = stop_play_sessions(cmd)
    json.dump(receipt, sys.stdout)
    sys.stdout.write("\n")
    return 0 if not receipt["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
