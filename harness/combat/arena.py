"""Isolated, bounded frozen-arena evaluation for combat candidates.

The arena owns every process and directory it creates.  It never attaches to an
existing Minecraft server: a supplied jar is copied into a fresh marked run
directory and all setup commands go to that child's stdin.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


MOBS = ("zombie", "skeleton")
JAVA_DEFAULT = r"C:\Users\hotdo\.lunarclient\jre\515e47c1d532181677af445d76add9cabc2317de\zulu25.30.17-ca-jre25.0.1-win_x64\bin\java.exe"


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_request(url: str, method: str = "GET", body: dict[str, Any] | None = None, timeout: float = 2.0) -> dict[str, Any]:
    payload = None if body is None else json.dumps(body).encode()
    request = Request(url, data=payload, method=method, headers={"content-type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read().decode())
        return value if isinstance(value, dict) else {}


def _spawned(status: dict[str, Any]) -> bool:
    """Require both the bridge's explicit connection event and a real pose."""
    connection = status.get("connection") or {}
    self_state = (status.get("observation") or {}).get("self") or {}
    position = self_state.get("position")
    return connection.get("status") == "spawned" and isinstance(position, dict) and all(isinstance(position.get(k), (int, float)) for k in ("x", "y", "z"))


def _wait_status(url: str, predicate, timeout_s: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            last = _json_request(url, timeout=1)
            if predicate(last):
                return last
        except (OSError, URLError, TimeoutError):
            pass
        time.sleep(.25)
    raise TimeoutError("timed out waiting for combat bridge state")


def _target_id(status: dict[str, Any]) -> Any:
    return ((status.get("observation") or {}).get("target") or {}).get("id")


def _invocation_result(status: dict[str, Any]) -> dict[str, Any]:
    invocation = status.get("invocation") or {}
    result = invocation.get("result") or status.get("result") or {}
    return result if isinstance(result, dict) else {}


def _succeeded_for_target(status: dict[str, Any], target_id: Any) -> bool:
    invocation = status.get("invocation") or {}
    result = _invocation_result(status)
    return (invocation.get("status") == "succeeded"
            and result.get("target_id") == target_id
            and result.get("terminal_event") == "target_death")


class ArenaServer:
    """Own one disposable Minecraft child and its console command channel."""

    def __init__(self, jar: Path, root: Path, java: str = "java", run_id: str | None = None, accept_eula: bool = False, seed: int = 37001):
        if not accept_eula:
            raise ValueError("Minecraft EULA must be explicitly accepted with accept_eula=True")
        jar = jar.resolve()
        if not jar.is_file():
            raise FileNotFoundError(jar)
        self.run_id = run_id or uuid.uuid4().hex
        self.root = root.resolve() / f"agent37-arena-{self.run_id}"
        self.root.mkdir(parents=True, exist_ok=False)
        (self.root / ".agent37-arena").write_text("owned disposable arena\n", encoding="utf-8")
        self.jar = self.root / jar.name
        shutil.copy2(jar, self.jar)
        self.port = _port()
        self.java = java
        self.seed = seed
        self.process: subprocess.Popen[str] | None = None
        self.log = self.root / "server.log"
        self._log_handle = None

    def _write_properties(self) -> None:
        values = {
            "server-port": self.port, "server-ip": "127.0.0.1", "online-mode": "false",
            "level-type": "minecraft:flat", "level-name": "agent37-test-world", "level-seed": self.seed,
            "difficulty": "normal", "spawn-monsters": "false", "spawn-npcs": "false",
            "enable-command-block": "true", "motd": "Agent-37 disposable combat arena",
            "white-list": "false", "allow-flight": "true", "sync-chunk-writes": "false",
        }
        (self.root / "server.properties").write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
        (self.root / "eula.txt").write_text("eula=true\n", encoding="utf-8")

    def start(self, timeout_s: float = 30) -> None:
        self._write_properties()
        self._log_handle = self.log.open("w", encoding="utf-8")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        self.process = subprocess.Popen([self.java, "-jar", self.jar.name, "--nogui"], cwd=self.root, stdin=subprocess.PIPE, stdout=self._log_handle, stderr=subprocess.STDOUT, text=True, creationflags=flags)
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"Minecraft server exited with {self.process.returncode}; see {self.log}")
            if self.log.exists() and "Done (" in self.log.read_text(encoding="utf-8", errors="replace"):
                return
            time.sleep(0.25)
        raise TimeoutError(f"Minecraft server did not start within {timeout_s}s")

    def command(self, command: str) -> None:
        if not self.process or self.process.poll() is not None or self.process.stdin is None:
            raise RuntimeError("arena server is not running")
        self.process.stdin.write(command.rstrip() + "\n")
        self.process.stdin.flush()

    def close(self) -> None:
        if self.process and self.process.poll() is None:
            try:
                self.command("stop")
                self.process.wait(timeout=10)
            except (OSError, TimeoutError, subprocess.TimeoutExpired):
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
        self.process = None
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None


def _setup(server: ArenaServer, username: str) -> None:
    commands = [
        "gamerule doMobSpawning false", "gamerule doDaylightCycle false", "gamerule keepInventory true",
        "gamerule naturalRegeneration true", "time set night", "difficulty normal",
        f"tp {username} 0 64 0", "gamemode survival " + username,
        "fill -16 63 -16 16 63 16 minecraft:stone", "fill -16 64 -16 16 70 -16 minecraft:stone",
        "fill -16 64 16 16 70 16 minecraft:stone", "fill -16 64 -16 -16 70 16 minecraft:stone",
        "fill 16 64 -16 16 70 16 minecraft:stone", f"give {username} minecraft:iron_sword 1", f"give {username} minecraft:shield 1",
        f"item replace entity {username} weapon.mainhand with minecraft:iron_sword", f"item replace entity {username} weapon.offhand with minecraft:shield",
        f"item replace entity {username} armor.head with minecraft:iron_helmet",
        f"item replace entity {username} armor.chest with minecraft:iron_chestplate",
        f"item replace entity {username} armor.legs with minecraft:iron_leggings",
        f"item replace entity {username} armor.feet with minecraft:iron_boots",
        f"attribute {username} minecraft:generic.max_health base set 20", f"effect clear {username}",
        f"effect give {username} minecraft:instant_health 1 10 true",
    ]
    for command in commands:
        server.command(command)


def _spawn(server: ArenaServer, mob: str, x: int, z: int) -> None:
    server.command("kill @e[type=!player,tag=agent37_trial]")
    server.command(f'summon minecraft:{mob} {x} 64 {z} {{Tags:["agent37_trial"],PersistenceRequired:1b}}')


def _bridge_command(candidate_dir: Path, mob: str, port: int, web_port: int, session: str, data_dir: Path) -> list[str]:
    return ["node", "server.js", "--host", "127.0.0.1", "--port", str(port), "--target", mob,
            "--session", session, "--username", "Agent37Teacher", "--data-dir", str(data_dir), "--web-port", str(web_port),
            "--candidate-dir", str(candidate_dir)]


def evaluate(candidate_dir: str | Path, *, server_jar: str | Path, java: str = "java", work_dir: str | Path = "data/arenas", trials_per_mob: int = 5, timeout_s: float = 45, seed: int = 37001, accept_eula: bool = False) -> dict[str, Any]:
    """Run frozen zombie/skeleton trials and save the result beside the candidate."""
    candidate = Path(candidate_dir).resolve()
    candidate.mkdir(parents=True, exist_ok=True)
    if trials_per_mob < 1:
        raise ValueError("trials_per_mob must be positive")
    model = candidate / "model.onnx"
    metadata = candidate / "metadata.json"
    if not model.is_file() or not metadata.is_file():
        raise FileNotFoundError("candidate must contain model.onnx and metadata.json")
    try:
        metadata_value = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("candidate metadata is invalid") from exc
    model_hash = _sha256(model)
    if metadata_value.get("model_sha256") != model_hash:
        raise ValueError("candidate metadata model_sha256 does not match model.onnx")
    candidate_id = candidate.name
    report: dict[str, Any] = {"schema_version": 1, "mode": "frozen_arena", "completed": False, "candidate_id": candidate_id,
        "model_sha256": model_hash, "dataset_sha256": metadata_value.get("dataset_sha256"),
        "teacher_intervention": False, "safety_violations": 0, "mobs": {}, "trials": [],
        "arena": {"path": None, "seed": seed, "server_jar_sha256": _sha256(Path(server_jar).resolve()), "environment_suite": "open_surface", "qualified_environment": "open_surface"}}
    arena = ArenaServer(Path(server_jar), Path(work_dir), java=java, accept_eula=accept_eula, seed=seed)
    report["arena"]["path"] = str(arena.root)
    bridge: subprocess.Popen[str] | None = None
    bridge_log = arena.root / "bridge.log"
    bridge_output = None
    try:
        arena.start(timeout_s=min(timeout_s, 60))
        web_port = _port(); data_dir = arena.root / "combat-data"; data_dir.mkdir()
        bridge_output = bridge_log.open("w", encoding="utf-8")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        bridge = subprocess.Popen(_bridge_command(candidate, MOBS[0], arena.port, web_port, arena.run_id, data_dir), cwd=Path(__file__).resolve().parents[2] / "bridge", stdout=bridge_output, stderr=subprocess.STDOUT, text=True, creationflags=flags)
        status_url = f"http://127.0.0.1:{web_port}/combat/status"
        _wait_status(status_url, _spawned, timeout_s)
        _setup(arena, "Agent37Teacher")
        _wait_status(status_url, _spawned, min(timeout_s, 15))
        import random
        rng = random.Random(seed)
        for mob in MOBS:
            if mob != MOBS[0]:
                if bridge and bridge.poll() is None:
                    bridge.terminate()
                    try: bridge.wait(timeout=5)
                    except subprocess.TimeoutExpired: bridge.kill()
                bridge = subprocess.Popen(_bridge_command(candidate, mob, arena.port, web_port, arena.run_id, data_dir), cwd=Path(__file__).resolve().parents[2] / "bridge", stdout=bridge_output, stderr=subprocess.STDOUT, text=True, creationflags=flags)
                _wait_status(status_url, _spawned, min(timeout_s, 30))
            rows = []
            for trial in range(trials_per_mob):
                offset = rng.choice(((3, 0), (-3, 0), (0, 3), (0, -3), (6, 2), (-6, -2), (2, 6), (-2, -6)))
                _json_request(f"http://127.0.0.1:{web_port}/combat/cancel", "POST", {})
                arena.command("kill @e[type=!player,tag=agent37_trial]")
                arena.command("tp Agent37Teacher 0 64 0")
                arena.command("data modify entity Agent37Teacher Health set value 20.0f")
                arena.command("data modify entity Agent37Teacher foodLevel set value 20")
                arena.command("effect clear Agent37Teacher")
                arena.command("item replace entity Agent37Teacher weapon.mainhand with minecraft:iron_sword")
                arena.command("item replace entity Agent37Teacher weapon.offhand with minecraft:shield")
                _wait_status(status_url, _spawned, min(timeout_s, 15))
                _spawn(arena, mob, *offset)
                bound = _wait_status(status_url, lambda s: _target_id(s) is not None, min(timeout_s, 15))
                bound_target_id = _target_id(bound)
                _json_request(f"http://127.0.0.1:{web_port}/combat/engage", "POST", {"target_type": mob, "candidate_dir": str(candidate), "max_duration_s": timeout_s})
                started = time.monotonic(); polls = []; success = False; bot_death = False; safety = 0; terminal = None
                while time.monotonic() - started < timeout_s:
                    try: status = _json_request(f"http://127.0.0.1:{web_port}/combat/status", timeout=2)
                    except (OSError, URLError): break
                    invocation = status.get("invocation") or {}; result = _invocation_result(status)
                    polls.append({"invocation": invocation, "target_id": _target_id(status), "self_health": ((status.get("observation") or {}).get("self") or {}).get("health")})
                    bot_death = bot_death or bool(result.get("bot_death") or result.get("self_death"))
                    safety = int(result.get("safety_violations", safety) or 0)
                    if invocation.get("status") in {"succeeded", "failed", "timeout", "inference_failed", "cancelled", "target_lost", "pursuit_limit", "candidate_load_failed"}:
                        terminal = invocation
                        success = _succeeded_for_target(status, bound_target_id)
                        break
                    time.sleep(.25)
                _json_request(f"http://127.0.0.1:{web_port}/combat/cancel", "POST", {})
                row = {"mob": mob, "trial": trial, "offset": {"x": offset[0], "z": offset[1]}, "target_id": bound_target_id, "success": success, "bot_death": bot_death, "safety_violations": safety, "terminal": terminal, "polls": polls}
                rows.append(row); report["trials"].append(row); report["safety_violations"] += safety
            report["mobs"][mob] = {"trials": len(rows), "success_fraction": sum(r["success"] for r in rows) / len(rows), "deaths": sum(r["bot_death"] for r in rows), "safety_violations": sum(r["safety_violations"] for r in rows)}
        report["completed"] = all(row.get("terminal") is not None for row in report["trials"])
        if not report["completed"]:
            report["error"] = "one or more arena trials ended without a terminal invocation result"
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        if bridge and bridge.poll() is None:
            bridge.terminate()
            try: bridge.wait(timeout=5)
            except subprocess.TimeoutExpired: bridge.kill()
        arena.close()
        if model.exists():
            report["model_sha256_after"] = _sha256(model)
            if report["model_sha256_after"] != model_hash:
                report["completed"] = False
                report["error"] = "candidate model changed during evaluation"
        if bridge_output:
            bridge_output.close()
        (candidate / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if report.get("error") == "candidate model changed during evaluation":
        raise RuntimeError(report["error"])
    return report
