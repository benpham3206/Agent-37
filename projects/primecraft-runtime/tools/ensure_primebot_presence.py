#!/usr/bin/env python3
"""Keep PrimeBot joined on the local Survival server with no goal.

- Auto-joins when the Minecraft server is up (unless the last chat command was leave).
- In-game chat: `primebot join` / `primebot leave` (any player; read from server log).
- Other player chat is forwarded to the live PLAY Prime-Agent harness.
- Attaches without claiming the controller lease so PLAY can adopt via start_presence().
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from play_harness import parse_agent_list_payload, preferred_play_session_id

DEFAULT_ADAPTER_URL = "http://127.0.0.1:18765"
DEFAULT_MC_HOST = "127.0.0.1"
DEFAULT_MC_PORT = 25566
DEFAULT_VERSION = "26.1.2"
DEFAULT_USERNAME = "PrimeBot"
POLL_S = 1.0
CHAT_COMMAND = re.compile(
    r"<(?!PrimeBot\b)[^>]+>\s*primebot\s+(join|leave)\b",
    re.IGNORECASE,
)
PLAYER_CHAT = re.compile(
    r"<(?!PrimeBot\b)(?P<sender>[^>]+)>\s*(?P<message>.+)$",
)


def mc_listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def http_json(method: str, url: str, body: dict | None = None, timeout_s: float = 35.0) -> dict:
    encoded = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        error.close()
        raise RuntimeError(f"http_{error.code}:{detail}") from error
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"request_failed:{error}") from error


def write_status(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def parse_chat_command(line: str) -> str | None:
    match = CHAT_COMMAND.search(line)
    if match is None:
        return None
    return match.group(1).lower()


def parse_player_chat(line: str) -> tuple[str, str] | None:
    if parse_chat_command(line) is not None:
        return None
    match = PLAYER_CHAT.search(line)
    if match is None:
        return None
    sender = match.group("sender").strip()
    message = match.group("message").strip()
    if not sender or not message:
        return None
    return sender, message


def resolve_prime_agent_cmd(explicit: str | None = None) -> str | None:
    if explicit and Path(explicit).is_file():
        return explicit
    fallback = Path.home() / ".local" / "bin" / "prime-agent.cmd"
    if fallback.is_file():
        return str(fallback)
    return None


def find_play_session_id(prime_agent_cmd: str) -> str | None:
    try:
        completed = subprocess.run(
            [prime_agent_cmd, "list", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    return preferred_play_session_id(parse_agent_list_payload(completed.stdout) or {})


def forward_chat_to_play(prime_agent_cmd: str, sender: str, message: str) -> dict:
    session_id = find_play_session_id(prime_agent_cmd)
    if session_id is None:
        return {"ok": False, "error": "play_session_missing"}
    prompt = (
        f"IN-GAME CHAT from {sender}: {message}\n\n"
        "PLAY ONLY: this is a Minecraft play instruction for PrimeBot. "
        "Call start_presence() if needed (adopt if already joined; do not stop_presence). "
        "Carry it out with presence_action / send_presence_chat. "
        "Do not read, search, or edit project files. Do not run tests. "
        "Do not restart the adapter, server, or Prime windows."
    )
    try:
        # This prime-agent build accepts: send <agent> <message>
        # (--steer/--from are documented but rejected by the Windows cmd wrapper).
        completed = subprocess.run(
            [prime_agent_cmd, "send", session_id, prompt],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "error": f"send_failed:{error}", "session_id": session_id}
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "send_failed").strip()
        return {"ok": False, "error": detail[:300], "session_id": session_id}
    return {"ok": True, "session_id": session_id, "sender": sender, "message": message}


def attach_idle(adapter_url: str, host: str, port: int, version: str, username: str) -> dict:
    episode_id = f"prime-idle-{int(time.time() * 1000)}"
    body = {
        "episode_id": episode_id,
        "host": host,
        "port": port,
        "version": version,
        "auth": "offline",
        "username": username,
        "observe_only": False,
        "allow_actions": True,
        "action_enabled": True,
    }
    attached = http_json("POST", f"{adapter_url.rstrip('/')}/v1/attach", body, timeout_s=120.0)
    if attached.get("episode_id") in (None, ""):
        attached = dict(attached)
        attached["episode_id"] = episode_id
    return attached


def stop_episode(adapter_url: str, episode_id: str | None, reason: str) -> None:
    body = {
        "episode_id": episode_id or "prime-idle-clear",
        "reason": reason,
    }
    try:
        http_json("POST", f"{adapter_url.rstrip('/')}/v1/stop", body, timeout_s=15.0)
    except RuntimeError:
        return


class ServerLogTail:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._offset = 0
        self._inode: int | None = None
        if path.is_file():
            self._offset = path.stat().st_size
            self._inode = path.stat().st_ino

    def poll_events(self) -> list[dict]:
        if not self.path.is_file():
            return []
        stat = self.path.stat()
        if self._inode is not None and stat.st_ino != self._inode:
            self._offset = 0
            self._inode = stat.st_ino
        if stat.st_size < self._offset:
            self._offset = 0
        if stat.st_size == self._offset:
            return []
        with self.path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(self._offset)
            chunk = handle.read()
            self._offset = handle.tell()
        events: list[dict] = []
        for line in chunk.splitlines():
            command = parse_chat_command(line)
            if command is not None:
                events.append({"kind": "command", "command": command})
                continue
            chat = parse_player_chat(line)
            if chat is not None:
                events.append({"kind": "chat", "sender": chat[0], "message": chat[1]})
        return events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument("--mc-host", default=DEFAULT_MC_HOST)
    parser.add_argument("--mc-port", type=int, default=DEFAULT_MC_PORT)
    parser.add_argument("--mc-version", default=DEFAULT_VERSION)
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--status-file", type=Path, required=True)
    parser.add_argument("--server-log", type=Path, required=True)
    parser.add_argument("--poll-s", type=float, default=POLL_S)
    parser.add_argument(
        "--initial-desire",
        choices=("joined", "left"),
        default="joined",
        help="joined = auto-join when server is up; left = stay out until chat 'primebot join'",
    )
    parser.add_argument(
        "--prime-agent-cmd",
        default=os.environ.get("PRIME_AGENT_CMD"),
        help="Path to prime-agent.cmd for forwarding in-game chat to PLAY",
    )
    args = parser.parse_args()

    desire = args.initial_desire
    last_command: str | None = None
    last_forward: dict | None = None
    log_tail = ServerLogTail(args.server_log)
    prime_agent_cmd = resolve_prime_agent_cmd(args.prime_agent_cmd)

    write_status(
        args.status_file,
        {
            "schema": "primecraft/primebot-idle-join",
            "state": "starting",
            "desire": desire,
            "goal": None,
            "chat_commands": ["primebot join", "primebot leave"],
            "forwards_player_chat_to_play": True,
            "updated_at": now_iso(),
        },
    )

    while True:
        for event in log_tail.poll_events():
            if event.get("kind") == "command":
                command = str(event.get("command"))
                desire = "joined" if command == "join" else "left"
                last_command = command
                continue
            if event.get("kind") == "chat" and prime_agent_cmd:
                last_forward = forward_chat_to_play(
                    prime_agent_cmd,
                    str(event.get("sender")),
                    str(event.get("message")),
                )

        server_up = mc_listening(args.mc_host, args.mc_port)
        try:
            health = http_json("GET", f"{args.adapter_url.rstrip('/')}/healthz", timeout_s=3.0)
        except RuntimeError as error:
            write_status(
                args.status_file,
                {
                    "schema": "primecraft/primebot-idle-join",
                    "state": "adapter_down",
                    "desire": desire,
                    "goal": None,
                    "server_up": server_up,
                    "last_chat_command": last_command,
                    "error": str(error),
                    "updated_at": now_iso(),
                },
            )
            time.sleep(args.poll_s)
            continue

        adapter_state = health.get("state")
        episode_id = health.get("episode_id") if isinstance(health.get("episode_id"), str) else None

        if desire == "left":
            if adapter_state == "attached":
                stop_episode(args.adapter_url, episode_id, "primebot-chat-leave")
                write_status(
                    args.status_file,
                    {
                        "schema": "primecraft/primebot-idle-join",
                        "state": "left",
                        "desire": desire,
                        "goal": None,
                        "last_chat_command": last_command,
                        "updated_at": now_iso(),
                    },
                )
            else:
                write_status(
                    args.status_file,
                    {
                        "schema": "primecraft/primebot-idle-join",
                        "state": "left",
                        "desire": desire,
                        "goal": None,
                        "adapter_state": adapter_state,
                        "last_chat_command": last_command,
                        "updated_at": now_iso(),
                    },
                )
            time.sleep(args.poll_s)
            continue

        if not server_up:
            write_status(
                args.status_file,
                {
                    "schema": "primecraft/primebot-idle-join",
                    "state": "waiting_for_server",
                    "desire": desire,
                    "goal": None,
                    "adapter_state": adapter_state,
                    "episode_id": episode_id,
                    "last_chat_command": last_command,
                    "updated_at": now_iso(),
                },
            )
            time.sleep(args.poll_s)
            continue

        if adapter_state == "attached":
            write_status(
                args.status_file,
                {
                    "schema": "primecraft/primebot-idle-join",
                    "state": "joined_idle",
                    "desire": desire,
                    "goal": None,
                    "adapter_state": adapter_state,
                    "episode_id": episode_id,
                    "last_chat_command": last_command,
                    "last_forward_to_play": last_forward,
                    "updated_at": now_iso(),
                },
            )
            time.sleep(args.poll_s)
            continue

        if adapter_state in {"failed", "stopped"}:
            stop_episode(args.adapter_url, episode_id, "primebot-idle-reopen")
            time.sleep(0.5)
            try:
                health = http_json("GET", f"{args.adapter_url.rstrip('/')}/healthz", timeout_s=3.0)
            except RuntimeError:
                time.sleep(args.poll_s)
                continue
            adapter_state = health.get("state")

        if adapter_state == "ready" and health.get("allow_actions") is True:
            try:
                attached = attach_idle(
                    args.adapter_url,
                    args.mc_host,
                    args.mc_port,
                    args.mc_version,
                    args.username,
                )
                write_status(
                    args.status_file,
                    {
                        "schema": "primecraft/primebot-idle-join",
                        "state": "joined_idle",
                        "desire": desire,
                        "goal": None,
                        "adapter_state": "attached",
                        "episode_id": attached.get("episode_id"),
                        "last_chat_command": last_command,
                        "updated_at": now_iso(),
                    },
                )
            except RuntimeError as error:
                write_status(
                    args.status_file,
                    {
                        "schema": "primecraft/primebot-idle-join",
                        "state": "attach_failed",
                        "desire": desire,
                        "goal": None,
                        "last_chat_command": last_command,
                        "error": str(error),
                        "updated_at": now_iso(),
                    },
                )
            time.sleep(args.poll_s)
            continue

        write_status(
            args.status_file,
            {
                "schema": "primecraft/primebot-idle-join",
                "state": "waiting_adapter",
                "desire": desire,
                "goal": None,
                "adapter_state": adapter_state,
                "last_chat_command": last_command,
                "updated_at": now_iso(),
            },
        )
        time.sleep(args.poll_s)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
