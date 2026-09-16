"""Reviewed Mineflayer adapter with a safe observe-only default.

The service owns a small HTTP control plane and delegates the game-facing
surface to an injected session.  The shipped Node session exposes attach,
observe, and stop by default.  An explicit action-enabled configuration adds
only bounded movement, chat, and stop-motion.  Tests use
FakeMineflayerFactory and never open an external socket.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol, runtime_checkable


_BRIDGE_DIR = Path(__file__).resolve().parents[1] / "B-bridge"
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))

from bridge import (  # noqa: E402
    Bridge,
    BridgeRejected,
    ChatAction,
    CraftAction,
    DigAction,
    ExecutionOutcome,
    GotoAction,
    LookAction,
    NavigateAction,
    MoveAction,
    Observation,
    PlaceAction,
    StopAction,
    WoodToTableAction,
)


class AdapterRejected(Exception):
    """A request or configuration was rejected at an adapter boundary."""

    __slots__ = ("code",)

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class AdapterFailure(Exception):
    """A bounded client operation failed or timed out."""

    __slots__ = ("code",)

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_USERNAME = re.compile(r"[A-Za-z0-9_]{3,16}\Z")
_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){1,2}\Z")
_HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}\Z")
_LOOPBACK = {"127.0.0.1", "::1"}
_AUTH_MODES = {"offline", "microsoft"}
_WOOD_TARGETS = {
    "minecraft:oak_log",
    "minecraft:spruce_log",
    "minecraft:birch_log",
    "minecraft:jungle_log",
    "minecraft:acacia_log",
    "minecraft:dark_oak_log",
    "minecraft:mangrove_log",
    "minecraft:cherry_log",
}
_BLOCK_ID = re.compile(r"minecraft:[a-z0-9_]{1,64}\Z")


def _require_exact_keys(raw: Mapping[object, object], required: set[str], code: str) -> None:
    keys = set(raw.keys())
    if any(not isinstance(key, str) for key in keys):
        raise AdapterRejected(code)
    if keys != required:
        raise AdapterRejected(code)


def _safe_identifier(value: object, code: str = "invalid_value") -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise AdapterRejected(code)
    return value


def _host(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or not _HOST.fullmatch(value):
        raise AdapterRejected("invalid_target")
    return value.lower()


def _port(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise AdapterRejected("invalid_target")
    return value


def _strict_bool(value: object, expected: bool, code: str) -> bool:
    if not isinstance(value, bool) or value is not expected:
        raise AdapterRejected(code)
    return value


@dataclass(frozen=True, slots=True)
class Target:
    host: str
    port: int

    @classmethod
    def from_mapping(cls, raw: object) -> Target:
        if not isinstance(raw, Mapping):
            raise AdapterRejected("invalid_allowlist")
        _require_exact_keys(raw, {"host", "port"}, "invalid_allowlist")
        return cls(host=_host(raw["host"]), port=_port(raw["port"]))


def parse_target_text(value: str) -> Target:
    if not isinstance(value, str) or value.count(":") != 1:
        raise AdapterRejected("invalid_allowlist")
    host, port_text = value.rsplit(":", 1)
    if not port_text.isdecimal():
        raise AdapterRejected("invalid_allowlist")
    return Target(host=_host(host), port=_port(int(port_text)))


def _bounded_timeout(value: object, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AdapterRejected("invalid_timeout")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise AdapterRejected("invalid_timeout")
    return result


@dataclass(frozen=True, slots=True)
class AdapterConfig:
    bind_host: str
    control_port: int
    target: Target
    allowed_targets: tuple[Target, ...]
    version: str
    auth: str
    username: str
    observe_only: bool
    allow_actions: bool
    action_enabled: bool
    evidence_dir: Path
    attach_timeout_s: float = 30.0
    request_timeout_s: float = 5.0
    observation_ttl_s: float = 5.0
    action_timeout_s: float = 5.0
    lease_ttl_s: float = 5.0
    node_exe: str = "node"
    client_script: Path | None = None
    node_modules_dir: Path | None = None
    auth_cache_dir: Path | None = None

    @classmethod
    def from_mapping(cls, raw: object) -> AdapterConfig:
        if not isinstance(raw, Mapping):
            raise AdapterRejected("invalid_config")
        required = {
            "bind_host",
            "control_port",
            "target_host",
            "target_port",
            "version",
            "auth",
            "username",
            "observe_only",
            "allow_actions",
            "allowed_targets",
            "evidence_dir",
        }
        optional = {
            "action_enabled",
            "attach_timeout_s",
            "request_timeout_s",
            "observation_ttl_s",
            "action_timeout_s",
            "lease_ttl_s",
            "node_exe",
            "client_script",
            "node_modules_dir",
            "auth_cache_dir",
        }
        keys = set(raw.keys())
        if any(not isinstance(key, str) for key in keys) or not required <= keys or keys - required - optional:
            raise AdapterRejected("invalid_config")

        bind_host = raw["bind_host"]
        if not isinstance(bind_host, str) or bind_host not in _LOOPBACK:
            raise AdapterRejected("loopback_required")
        control_port = _port(raw["control_port"])
        target = Target(host=_host(raw["target_host"]), port=_port(raw["target_port"]))

        version = raw["version"]
        if not isinstance(version, str) or not _VERSION.fullmatch(version) or version.lower() in {"auto", "latest"}:
            raise AdapterRejected("explicit_version_required")
        auth = raw["auth"]
        if not isinstance(auth, str) or auth not in _AUTH_MODES:
            raise AdapterRejected("explicit_auth_required")
        username = raw["username"]
        if not isinstance(username, str) or not _USERNAME.fullmatch(username):
            raise AdapterRejected("invalid_username")
        action_enabled = raw.get("action_enabled", False)
        if not isinstance(action_enabled, bool):
            raise AdapterRejected("invalid_action_mode")
        if action_enabled:
            _strict_bool(raw["observe_only"], False, "observe_only_required")
            _strict_bool(raw["allow_actions"], True, "actions_not_enabled")
        else:
            _strict_bool(raw["observe_only"], True, "observe_only_required")
            _strict_bool(raw["allow_actions"], False, "actions_forbidden")

        allowed_raw = raw["allowed_targets"]
        if not isinstance(allowed_raw, (list, tuple)) or not allowed_raw:
            raise AdapterRejected("invalid_allowlist")
        allowed = tuple(Target.from_mapping(item) for item in allowed_raw)
        if len(set(allowed)) != len(allowed):
            raise AdapterRejected("invalid_allowlist")
        if target not in allowed:
            raise AdapterRejected("target_not_allowlisted")

        evidence_raw = raw["evidence_dir"]
        if not isinstance(evidence_raw, str) or not os.path.isabs(evidence_raw):
            raise AdapterRejected("invalid_evidence_dir")
        evidence_dir = Path(evidence_raw)
        if not evidence_dir.exists() or not evidence_dir.is_dir() or evidence_dir.is_symlink():
            raise AdapterRejected("invalid_evidence_dir")

        node_exe = raw.get("node_exe", "node")
        if not isinstance(node_exe, str) or not node_exe.strip() or "\x00" in node_exe:
            raise AdapterRejected("invalid_runtime")
        script_raw = raw.get("client_script")
        client_script = None
        if script_raw is not None:
            if not isinstance(script_raw, str) or not os.path.isabs(script_raw):
                raise AdapterRejected("invalid_runtime")
            client_script = Path(script_raw)
            if not client_script.is_file() or client_script.is_symlink():
                raise AdapterRejected("invalid_runtime")
        node_modules_raw = raw.get("node_modules_dir")
        node_modules_dir = None
        if node_modules_raw is not None:
            if not isinstance(node_modules_raw, str) or not os.path.isabs(node_modules_raw):
                raise AdapterRejected("invalid_runtime")
            node_modules_dir = Path(node_modules_raw)
            if not node_modules_dir.is_dir() or node_modules_dir.is_symlink():
                raise AdapterRejected("invalid_runtime")

        auth_cache_raw = raw.get("auth_cache_dir")
        auth_cache_dir = None
        if auth_cache_raw is not None:
            if not isinstance(auth_cache_raw, str) or not os.path.isabs(auth_cache_raw):
                raise AdapterRejected("invalid_auth_cache_dir")
            auth_cache_dir = Path(auth_cache_raw)
            if not auth_cache_dir.is_dir() or auth_cache_dir.is_symlink():
                raise AdapterRejected("invalid_auth_cache_dir")

        return cls(
            bind_host=bind_host,
            control_port=control_port,
            target=target,
            allowed_targets=allowed,
            version=version,
            auth=auth,
            username=username,
            observe_only=not action_enabled,
            allow_actions=action_enabled,
            action_enabled=action_enabled,
            evidence_dir=evidence_dir,
            attach_timeout_s=_bounded_timeout(raw.get("attach_timeout_s", 30.0), 0.1, 120.0),
            request_timeout_s=_bounded_timeout(raw.get("request_timeout_s", 5.0), 0.1, 30.0),
            observation_ttl_s=_bounded_timeout(raw.get("observation_ttl_s", 5.0), 0.1, 60.0),
            action_timeout_s=_bounded_timeout(raw.get("action_timeout_s", 5.0), 0.1, 30.0),
            lease_ttl_s=_bounded_timeout(raw.get("lease_ttl_s", 5.0), 0.1, 60.0),
            node_exe=node_exe,
            client_script=client_script,
            node_modules_dir=node_modules_dir,
            auth_cache_dir=auth_cache_dir,
        )


class EvidenceLog:
    """Append-only, allowlisted, non-secret adapter evidence."""

    _FIELDS = {
        "episode_id",
        "target_host",
        "target_port",
        "version",
        "auth",
        "username",
        "state",
        "error_code",
        "reason",
        "observation_id",
        "observed_at_ms",
        "client_kind",
        "controller_id",
        "epoch",
        "request_seq",
        "receipt_id",
        "action_kind",
        "instruction_id",
        "text_length",
        "message_id",
        "received_at_ms",
        "sender",
        "result",
        "digest",
    }

    def __init__(self, directory: Path):
        self._path = directory / "adapter-events.jsonl"
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def append(self, event_type: str, **fields: object) -> None:
        if not _IDENTIFIER.fullmatch(event_type) or set(fields) - self._FIELDS:
            raise AdapterRejected("invalid_evidence")
        safe: dict[str, object] = {"schema": "minecraft-ce/adapter-event", "schema_version": 1}
        safe["event_id"] = f"evt-{time.time_ns()}"
        safe["emitted_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        safe["event_type"] = event_type
        for key, value in fields.items():
            if isinstance(value, bool) or value is None:
                raise AdapterRejected("invalid_evidence")
            if isinstance(value, int):
                if value < 0:
                    raise AdapterRejected("invalid_evidence")
            elif isinstance(value, str):
                if not value or len(value) > 256 or any(ord(char) < 0x20 for char in value):
                    raise AdapterRejected("invalid_evidence")
            else:
                raise AdapterRejected("invalid_evidence")
            safe[key] = value
        line = json.dumps(safe, separators=(",", ":"), sort_keys=True) + "\n"
        with self._lock, self._path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())


@runtime_checkable
class MineflayerSession(Protocol):
    def attach(self, timeout_s: float) -> None:
        ...

    def observation(self, timeout_s: float) -> Mapping[str, object]:
        ...

    def chat_inbox(self, timeout_s: float) -> Sequence[Mapping[str, object]]:
        ...

    def walk(self, direction: str, duration_ms: int, timeout_s: float) -> None:
        ...

    def look(self, yaw_deg: float, pitch_deg: float, timeout_s: float) -> None:
        ...

    def navigate(self, block: str, max_distance: int, timeout_s: float) -> Mapping[str, object]:
        ...

    def goto(self, x: int, y: int, z: int, timeout_s: float) -> Mapping[str, object]:
        ...

    def wood_to_table(self, max_distance: int, timeout_s: float) -> Mapping[str, object]:
        ...

    def dig(self, block: str, max_distance: int, timeout_s: float) -> Mapping[str, object]:
        ...

    def craft(self, item: str, count: int, timeout_s: float) -> Mapping[str, object]:
        ...

    def place(self, item: str, timeout_s: float) -> Mapping[str, object]:
        ...

    def chat(self, message: str, timeout_s: float) -> None:
        ...

    def stop_motion(self, timeout_s: float) -> None:
        ...

    def close(self, timeout_s: float) -> None:
        ...

    def abort(self) -> None:
        ...


class MineflayerFactory(Protocol):
    def create(self, config: AdapterConfig) -> MineflayerSession:
        ...


class _SessionActionExecutor:
    """The only action dispatch surface exposed to the Bridge."""

    def __init__(self, timeout_s: float):
        self._timeout_s = timeout_s
        self._session: MineflayerSession | None = None

    def set_session(self, session: MineflayerSession | None) -> None:
        self._session = session

    def execute(self, action: object) -> ExecutionOutcome:
        session = self._session
        if session is None:
            return ExecutionOutcome(False, "missing_client")
        try:
            if isinstance(action, MoveAction):
                _bounded_call(
                    session.walk,
                    action.direction,
                    action.duration_ms,
                    self._timeout_s,
                    timeout_s=self._timeout_s,
                )
            elif isinstance(action, LookAction):
                _bounded_call(
                    session.look,
                    action.yaw_deg,
                    action.pitch_deg,
                    self._timeout_s,
                    timeout_s=self._timeout_s,
                )
            elif isinstance(action, NavigateAction):
                result = _bounded_call(
                    session.navigate,
                    action.block,
                    action.max_distance,
                    self._timeout_s,
                    timeout_s=self._timeout_s,
                )
                if isinstance(result, Mapping) and isinstance(result.get("event"), str):
                    return ExecutionOutcome(True, result["event"])
            elif isinstance(action, GotoAction):
                result = _bounded_call(
                    session.goto,
                    action.x,
                    action.y,
                    action.z,
                    self._timeout_s,
                    timeout_s=self._timeout_s,
                )
                if isinstance(result, Mapping) and isinstance(result.get("event"), str):
                    return ExecutionOutcome(True, result["event"])
            elif isinstance(action, WoodToTableAction):
                result = _bounded_call(
                    session.wood_to_table,
                    action.max_distance,
                    self._timeout_s,
                    timeout_s=self._timeout_s,
                )
                if isinstance(result, Mapping) and isinstance(result.get("event"), str):
                    return ExecutionOutcome(True, result["event"], result)
            elif isinstance(action, DigAction):
                result = _bounded_call(
                    session.dig,
                    action.block,
                    action.max_distance,
                    self._timeout_s,
                    timeout_s=self._timeout_s,
                )
                if isinstance(result, Mapping) and isinstance(result.get("event"), str):
                    return ExecutionOutcome(True, result["event"], result)
            elif isinstance(action, CraftAction):
                result = _bounded_call(
                    session.craft,
                    action.item,
                    action.count,
                    self._timeout_s,
                    timeout_s=self._timeout_s,
                )
                if isinstance(result, Mapping) and isinstance(result.get("event"), str):
                    return ExecutionOutcome(True, result["event"], result)
            elif isinstance(action, PlaceAction):
                result = _bounded_call(
                    session.place,
                    action.item,
                    self._timeout_s,
                    timeout_s=self._timeout_s,
                )
                if isinstance(result, Mapping) and isinstance(result.get("event"), str):
                    return ExecutionOutcome(True, result["event"], result)
            elif isinstance(action, ChatAction):
                _bounded_call(session.chat, action.message, self._timeout_s, timeout_s=self._timeout_s)
            elif isinstance(action, StopAction):
                _bounded_call(session.stop_motion, self._timeout_s, timeout_s=self._timeout_s)
            else:
                return ExecutionOutcome(False, "unsupported_action")
        except AdapterFailure as error:
            return ExecutionOutcome(False, "action_timeout" if error.code == "operation_timeout" else error.code)
        except Exception:
            return ExecutionOutcome(False, "client_failure")
        return ExecutionOutcome(True, "accepted")

    def stop(self) -> None:
        session = self._session
        if session is not None:
            try:
                _bounded_call(session.stop_motion, self._timeout_s, timeout_s=self._timeout_s)
            except Exception:
                pass


def _bounded_call(function: Callable[..., Any], *args: object, timeout_s: float) -> Any:
    result: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)

    def run() -> None:
        try:
            result.put(("ok", function(*args)))
        except Exception as error:  # boundary converts all client failures to safe codes
            result.put(("error", error))

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout_s)
    if worker.is_alive():
        raise AdapterFailure("operation_timeout")
    kind, value = result.get_nowait()
    if kind == "error":
        if isinstance(value, AdapterFailure):
            raise value
        raise AdapterFailure("client_failure")
    return value


def _observation_dict(observation: Observation) -> dict[str, object]:
    result: dict[str, object] = {
        "schema_version": observation.schema_version,
        "observation_id": observation.observation_id,
        "observed_at_ms": observation.observed_at_ms,
        "dimension": observation.dimension,
        "position": {"x": observation.position.x, "y": observation.position.y, "z": observation.position.z},
        "velocity": {"x": observation.velocity.x, "y": observation.velocity.y, "z": observation.velocity.z},
        "health": observation.health,
        "food": observation.food,
        "air": observation.air,
        "fire_ticks": observation.fire_ticks,
        "is_alive": observation.is_alive,
        "selected_slot": observation.selected_slot,
        "inventory": [
            {"slot": item.slot, "item": item.item, "count": item.count}
            for item in observation.inventory
        ],
        "nearby_entities": [
            {"entity_id": entity.entity_id, "kind": entity.kind, "distance": entity.distance}
            for entity in observation.nearby_entities
        ],
    }
    if observation.schema_version in {"observation.v2", "observation.v3"} and observation.world is not None:
        result["recent_chat"] = [
            {
                "sender": message.sender,
                "message": message.message,
                "received_at_ms": message.received_at_ms,
            }
            for message in observation.recent_chat
        ]
        result["world"] = {
            "below": observation.world.below,
            "feet": observation.world.feet,
            "head": observation.world.head,
            "nearby_blocks": [
                {
                    "block": block.block,
                    "distance": block.distance,
                    **(
                        {"position": {"x": block.position.x, "y": block.position.y, "z": block.position.z}}
                        if block.position is not None
                        else {}
                    ),
                }
                for block in observation.world.nearby_blocks
            ],
        }
    if observation.schema_version == "observation.v3" and observation.advancements is not None:
        result["advancements"] = {
            "known": observation.advancements.known,
            "entries": {
                advancement_id: {
                    "requirements": [list(group) for group in entry.requirements],
                    "criteria": {criterion: timestamp for criterion, timestamp in entry.criteria},
                }
                for advancement_id, entry in observation.advancements.entries
            },
        }
    return result


def _chat_message_dict(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        raise AdapterFailure("invalid_chat_message")
    _require_exact_keys(raw, {"message_id", "received_at_ms", "username", "message"}, "invalid_chat_message")
    message_id = _safe_identifier(raw["message_id"], "invalid_chat_message")
    received_at_ms = raw["received_at_ms"]
    if isinstance(received_at_ms, bool) or not isinstance(received_at_ms, int) or received_at_ms < 0:
        raise AdapterFailure("invalid_chat_message")
    username = raw["username"]
    if not isinstance(username, str) or not _USERNAME.fullmatch(username):
        raise AdapterFailure("invalid_chat_message")
    message = raw["message"]
    if not isinstance(message, str) or not message or len(message) > 200 or any(ord(char) < 0x20 for char in message):
        raise AdapterFailure("invalid_chat_message")
    return {
        "message_id": message_id,
        "received_at_ms": received_at_ms,
        "username": username,
        "message": message,
    }


def _inventory_counts(raw: object, label: str) -> dict[str, int]:
    if not isinstance(raw, Mapping):
        raise AdapterFailure("invalid_operation_result")
    _require_exact_keys(raw, {"logs", "planks", "crafting_tables"}, "invalid_operation_result")
    result: dict[str, int] = {}
    for key in ("logs", "planks", "crafting_tables"):
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 8_192:
            raise AdapterFailure("invalid_operation_result")
        result[key] = value
    return result


def _operation_target(raw: object) -> dict[str, object] | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise AdapterFailure("invalid_operation_result")
    _require_exact_keys(raw, {"block", "x", "y", "z"}, "invalid_operation_result")
    block = raw["block"]
    if not isinstance(block, str) or block not in _WOOD_TARGETS:
        raise AdapterFailure("invalid_operation_result")
    coordinates: dict[str, int] = {}
    for key, minimum, maximum in (
        ("x", -30_000_000, 30_000_000),
        ("y", -4_096, 4_096),
        ("z", -30_000_000, 30_000_000),
    ):
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise AdapterFailure("invalid_operation_result")
        coordinates[key] = value
    return {"block": block, **coordinates}


def _wood_to_table_result(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        raise AdapterFailure("invalid_operation_result")
    required = {
        "ok",
        "event",
        "reason",
        "max_distance",
        "target",
        "target_after",
        "before",
        "after_harvest",
        "after_planks",
        "after",
    }
    _require_exact_keys(raw, required, "invalid_operation_result")
    if raw["ok"] is not True:
        raise AdapterFailure("invalid_operation_result")
    event = raw["event"]
    reason = raw["reason"]
    max_distance = raw["max_distance"]
    if event not in {"wood_to_table_complete", "target_unavailable", "unsafe"}:
        raise AdapterFailure("invalid_operation_result")
    if reason not in {"completed", "no_log_in_range", "no_safe_reachable_log", "initial_state_unsafe", "reached_state_unsafe"}:
        raise AdapterFailure("invalid_operation_result")
    if isinstance(max_distance, bool) or not isinstance(max_distance, int) or not 1 <= max_distance <= 64:
        raise AdapterFailure("invalid_operation_result")
    target = _operation_target(raw["target"])
    before = _inventory_counts(raw["before"], "before")
    after = _inventory_counts(raw["after"], "after")
    target_after = raw["target_after"]
    if target_after is not None and (not isinstance(target_after, str) or not _BLOCK_ID.fullmatch(target_after)):
        raise AdapterFailure("invalid_operation_result")

    after_harvest_raw = raw["after_harvest"]
    after_planks_raw = raw["after_planks"]
    if event == "wood_to_table_complete":
        if reason != "completed" or target is None or target_after is None or target_after == target["block"]:
            raise AdapterFailure("invalid_operation_result")
        after_harvest = _inventory_counts(after_harvest_raw, "after_harvest")
        after_planks = _inventory_counts(after_planks_raw, "after_planks")
        if (
            after_harvest["logs"] < before["logs"] + 1
            or after_planks["planks"] < before["planks"] + 4
            or after_planks["logs"] > after_harvest["logs"] - 1
            or after["planks"] > after_planks["planks"] - 4
            or after["crafting_tables"] < before["crafting_tables"] + 1
        ):
            raise AdapterFailure("operation_postcondition_failed")
    else:
        if event == "target_unavailable" and reason not in {"no_log_in_range", "no_safe_reachable_log"}:
            raise AdapterFailure("invalid_operation_result")
        if event == "unsafe" and reason not in {"initial_state_unsafe", "reached_state_unsafe"}:
            raise AdapterFailure("invalid_operation_result")
        if after_harvest_raw is not None or after_planks_raw is not None or before != after:
            raise AdapterFailure("operation_postcondition_failed")
        after_harvest = None
        after_planks = None

    return {
        "event": event,
        "reason": reason,
        "max_distance": max_distance,
        "target": target,
        "target_after": target_after,
        "before": before,
        "after_harvest": after_harvest,
        "after_planks": after_planks,
        "after": after,
    }


def _parse_attach_request(raw: object, config: AdapterConfig) -> str:
    if not isinstance(raw, Mapping):
        raise AdapterRejected("invalid_attach")
    _require_exact_keys(
        raw,
        {
            "episode_id",
            "host",
            "port",
            "version",
            "auth",
            "username",
            "observe_only",
            "allow_actions",
            "action_enabled",
        },
        "invalid_attach",
    )
    episode_id = _safe_identifier(raw["episode_id"], "invalid_episode")
    target = Target(host=_host(raw["host"]), port=_port(raw["port"]))
    if target != config.target or target not in config.allowed_targets:
        raise AdapterRejected("target_not_allowlisted")
    if raw["version"] != config.version:
        raise AdapterRejected("version_mismatch")
    if raw["auth"] != config.auth:
        raise AdapterRejected("auth_mismatch")
    if raw["username"] != config.username:
        raise AdapterRejected("username_mismatch")
    _strict_bool(raw["observe_only"], config.observe_only, "observe_only_required")
    _strict_bool(raw["allow_actions"], config.allow_actions, "actions_forbidden")
    _strict_bool(raw["action_enabled"], config.action_enabled, "action_mode_mismatch")
    return episode_id


def _parse_session_metadata(raw: object, config: AdapterConfig, required: set[str]) -> tuple[str, str | None, int | None]:
    if not isinstance(raw, Mapping):
        raise AdapterRejected("invalid_request")
    _require_exact_keys(raw, required, "invalid_request")
    episode_id = _safe_identifier(raw["episode_id"], "invalid_episode")
    target = Target(host=_host(raw["host"]), port=_port(raw["port"]))
    if target != config.target or target not in config.allowed_targets:
        raise AdapterRejected("target_not_allowlisted")
    if raw["version"] != config.version:
        raise AdapterRejected("version_mismatch")
    if raw["auth"] != config.auth:
        raise AdapterRejected("auth_mismatch")
    if raw["username"] != config.username:
        raise AdapterRejected("username_mismatch")
    controller_id = None
    epoch = None
    if "controller_id" in required:
        controller_id = _safe_identifier(raw["controller_id"], "invalid_controller")
    if "epoch" in required:
        epoch = _bounded_positive_int(raw["epoch"], "invalid_epoch")
    return episode_id, controller_id, epoch


def _bounded_positive_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise AdapterRejected(code)
    return value


def _action_kind(raw: object) -> str:
    if not isinstance(raw, Mapping) or not isinstance(raw.get("kind"), str):
        raise AdapterRejected("invalid_action")
    kind = raw["kind"]
    if kind not in {"move", "look", "navigate", "goto", "wood_to_table", "dig", "craft", "place", "chat", "stop"}:
        raise AdapterRejected("unsafe_action")
    return kind


# These outcomes describe an attempted action that did not change the world.
# They remain observable and retryable without disconnecting the episode.
_RECOVERABLE_ACTION_FAILURES = {
    "path_not_found",
    "path_incomplete",
    "target_not_found",
    "target_unavailable",
    "no_safe_reachable_log",
    "harvest_precondition_failed",
    "harvest_timeout",
    "harvest_not_collected",
    "recipe_data_unavailable",
    "plank_recipe_unavailable",
    "plank_craft_timeout",
    "plank_postcondition_failed",
    "table_recipe_unavailable",
    "table_craft_timeout",
    "table_postcondition_failed",
    "target_postcondition_failed",
    "dig_failed",
    "recipe_unavailable",
    "craft_timeout",
    "craft_failed",
    "item_unavailable",
    "place_target_unavailable",
    "place_timeout",
    "place_failed",
}


def _parse_stop_request(raw: object, episode_id: str | None) -> tuple[str, str]:
    if not isinstance(raw, Mapping):
        raise AdapterRejected("invalid_stop")
    _require_exact_keys(raw, {"episode_id", "reason"}, "invalid_stop")
    requested_episode = _safe_identifier(raw["episode_id"], "invalid_episode")
    reason = _safe_identifier(raw["reason"], "invalid_stop")
    if episode_id is not None and requested_episode != episode_id:
        raise AdapterRejected("episode_mismatch")
    return requested_episode, reason


class AdapterService:
    """Fail-closed lifecycle core behind the HTTP shell."""

    def __init__(
        self,
        config: AdapterConfig,
        factory: MineflayerFactory,
        *,
        clock_ms: Callable[[], int] | None = None,
    ):
        self.config = config
        self.factory = factory
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self._evidence = EvidenceLog(config.evidence_dir)
        self._action_executor = _SessionActionExecutor(config.action_timeout_s)
        self._bridge = Bridge(
            clock=self._clock_ms,
            executor=self._action_executor,
            lease_ttl_ms=int(config.lease_ttl_s * 1000),
        )
        self._state = "ready"
        self._episode_id: str | None = None
        self._client: MineflayerSession | None = None
        self._last_observation: Observation | None = None
        self._instructions: dict[str, str] = {}
        self._lock = threading.RLock()
        self._watched_lease_epoch: int | None = None
        self._watchdog_stop = threading.Event()
        self._watchdog_thread = threading.Thread(
            target=self._lease_watchdog_loop,
            name="minecraft-adapter-lease-watchdog",
            daemon=True,
        )
        self._evidence.append(
            "service_started",
            target_host=config.target.host,
            target_port=config.target.port,
            version=config.version,
            auth=config.auth,
            username=config.username,
            state=self._state,
            client_kind=type(factory).__name__,
        )
        self._watchdog_thread.start()

    @property
    def evidence_path(self) -> Path:
        return self._evidence.path

    def health(self) -> dict[str, object]:
        # Do not wait on the action lock. A long dig/craft holds it for seconds
        # and used to make healthz time out, which then disconnected the bot.
        return {
            "service": "minecraft-ce-adapter",
            "state": self._state,
            "bind_host": self.config.bind_host,
            "control_port": self.config.control_port,
            "target": {"host": self.config.target.host, "port": self.config.target.port},
            "version": self.config.version,
            "auth": self.config.auth,
            "username": self.config.username,
            "observe_only": self.config.observe_only,
            "allow_actions": self.config.allow_actions,
            "action_enabled": self.config.action_enabled,
            "client_attached": self._client is not None,
            "episode_id": self._episode_id,
            "last_observation_at_ms": self._last_observation.observed_at_ms if self._last_observation else None,
            "capabilities": {
                "observation": True,
                "actions": self.config.action_enabled,
                "movement": self.config.action_enabled,
                "pathfinder": self.config.action_enabled,
                "wood_to_table": self.config.action_enabled,
                "dig": self.config.action_enabled,
                "craft": self.config.action_enabled,
                "place": self.config.action_enabled,
                "chat": self.config.action_enabled,
                "stop": True,
            },
        }

    def attach(self, raw: object) -> dict[str, object]:
        with self._lock:
            if self._state != "ready":
                raise AdapterRejected("invalid_state")
            episode_id = _parse_attach_request(raw, self.config)
            self._episode_id = episode_id
            self._state = "attaching"
            self._evidence.append(
                "attach_requested",
                episode_id=episode_id,
                target_host=self.config.target.host,
                target_port=self.config.target.port,
                version=self.config.version,
                auth=self.config.auth,
                username=self.config.username,
                state=self._state,
            )
            session: MineflayerSession | None = None
            try:
                session = _bounded_call(self.factory.create, self.config, timeout_s=self.config.request_timeout_s)
                if not isinstance(session, MineflayerSession):
                    raise AdapterFailure("invalid_client")
                _bounded_call(session.attach, self.config.attach_timeout_s, timeout_s=self.config.attach_timeout_s)
            except Exception as error:
                if session is not None:
                    try:
                        self._close_session(session)
                    except AdapterFailure:
                        pass
                self._action_executor.set_session(None)
                self._client = None
                self._state = "failed"
                self._evidence.append(
                    "attach_failed",
                    episode_id=episode_id,
                    target_host=self.config.target.host,
                    target_port=self.config.target.port,
                    version=self.config.version,
                    auth=self.config.auth,
                    username=self.config.username,
                    state=self._state,
                    error_code=self._safe_error_code(error),
                )
                if isinstance(error, AdapterFailure):
                    raise error
                raise AdapterFailure(self._safe_error_code(error))
            self._client = session
            self._action_executor.set_session(session)
            self._state = "attached"
            self._evidence.append(
                "attached",
                episode_id=episode_id,
                target_host=self.config.target.host,
                target_port=self.config.target.port,
                version=self.config.version,
                auth=self.config.auth,
                username=self.config.username,
                state=self._state,
            )
            return {
                "status": "attached",
                "episode_id": episode_id,
                "target": {"host": self.config.target.host, "port": self.config.target.port},
                "version": self.config.version,
                "auth": self.config.auth,
                "username": self.config.username,
                "logged_in": True,
                "spawned": True,
                "observe_only": self.config.observe_only,
                "allow_actions": self.config.allow_actions,
                "action_enabled": self.config.action_enabled,
            }

    def observation(self) -> dict[str, object]:
        with self._lock:
            if self._state != "attached" or self._client is None or self._episode_id is None:
                raise AdapterRejected("not_attached")
            try:
                raw = _bounded_call(self._client.observation, self.config.request_timeout_s, timeout_s=self.config.request_timeout_s)
                observation = self._bridge.ingest_observation(raw)
                now = self._clock_ms()
                if observation.observed_at_ms > now + 5_000:
                    raise AdapterFailure("future_observation")
                if observation.observed_at_ms < now - int(self.config.observation_ttl_s * 1000):
                    raise AdapterFailure("stale_observation")
            except BridgeRejected:
                self._fail_attached("invalid_observation")
                raise AdapterFailure("invalid_observation")
            except Exception as error:
                code = error.code if isinstance(error, AdapterFailure) else self._safe_error_code(error)
                self._fail_attached(code)
                raise AdapterFailure(code)
            self._last_observation = observation
            self._evidence.append(
                "observation",
                episode_id=self._episode_id,
                target_host=self.config.target.host,
                target_port=self.config.target.port,
                version=self.config.version,
                auth=self.config.auth,
                username=self.config.username,
                state=self._state,
                observation_id=observation.observation_id,
                observed_at_ms=observation.observed_at_ms,
            )
            return {
                "episode_id": self._episode_id,
                "observe_only": self.config.observe_only,
                "allow_actions": self.config.allow_actions,
                "action_enabled": self.config.action_enabled,
                "observation": _observation_dict(observation),
            }

    def chat_inbox(self) -> dict[str, object]:
        with self._lock:
            self._require_attached()
            try:
                raw_messages = _bounded_call(
                    self._client.chat_inbox,
                    self.config.request_timeout_s,
                    timeout_s=self.config.request_timeout_s,
                )
                if not isinstance(raw_messages, Sequence) or isinstance(raw_messages, (str, bytes)) or len(raw_messages) > 64:
                    raise AdapterFailure("invalid_chat_response")
                messages = [_chat_message_dict(item) for item in raw_messages]
            except AdapterFailure:
                raise
            except Exception as error:
                raise AdapterFailure("invalid_chat_response") from error
            for message in messages:
                self._evidence.append(
                    "chat_received",
                    episode_id=self._episode_id,
                    message_id=message["message_id"],
                    received_at_ms=message["received_at_ms"],
                    sender=message["username"],
                    text_length=len(message["message"]),
                    state=self._state,
                )
            return {
                "episode_id": self._episode_id,
                "messages": messages,
            }

    def claim_controller(self, raw: object) -> dict[str, object]:
        with self._lock:
            self._require_action_mode()
            self._require_attached()
            episode_id, controller_id, _ = _parse_session_metadata(
                raw,
                self.config,
                {"episode_id", "host", "port", "version", "auth", "username", "controller_id"},
            )
            self._require_episode(episode_id)
            assert controller_id is not None
            try:
                lease = self._bridge.claim_controller(controller_id)
            except BridgeRejected as error:
                raise AdapterRejected(error.code) from error
            self._watched_lease_epoch = lease.epoch
            self._evidence.append(
                "controller_claimed",
                episode_id=episode_id,
                controller_id=lease.controller_id,
                epoch=lease.epoch,
                state=self._state,
            )
            return {
                "status": "claimed",
                "episode_id": episode_id,
                "controller_id": lease.controller_id,
                "epoch": lease.epoch,
                "expires_at_ms": lease.expires_at_ms,
            }

    def heartbeat(self, raw: object) -> dict[str, object]:
        with self._lock:
            self._require_action_mode()
            self._require_attached()
            episode_id, controller_id, epoch = _parse_session_metadata(
                raw,
                self.config,
                {"episode_id", "host", "port", "version", "auth", "username", "controller_id", "epoch"},
            )
            self._require_episode(episode_id)
            assert controller_id is not None and epoch is not None
            try:
                lease = self._bridge.heartbeat(controller_id, epoch)
            except BridgeRejected as error:
                if error.code == "expired_lease":
                    self._watched_lease_epoch = None
                    self._fail_attached("lease_expired")
                raise AdapterRejected(error.code) from error
            return {
                "status": "alive",
                "episode_id": episode_id,
                "controller_id": lease.controller_id,
                "epoch": lease.epoch,
                "expires_at_ms": lease.expires_at_ms,
            }

    def release_controller(self, raw: object) -> dict[str, object]:
        with self._lock:
            self._require_action_mode()
            self._require_attached()
            episode_id, controller_id, epoch = _parse_session_metadata(
                raw,
                self.config,
                {"episode_id", "host", "port", "version", "auth", "username", "controller_id", "epoch"},
            )
            self._require_episode(episode_id)
            assert controller_id is not None and epoch is not None
            try:
                self._bridge.release_controller(controller_id, epoch)
            except BridgeRejected as error:
                raise AdapterRejected(error.code) from error
            self._watched_lease_epoch = None
            self._evidence.append(
                "controller_released",
                episode_id=episode_id,
                controller_id=controller_id,
                epoch=epoch,
                state=self._state,
            )
            return {"status": "released", "episode_id": episode_id, "controller_id": controller_id, "epoch": epoch}

    def instruction(self, raw: object) -> dict[str, object]:
        with self._lock:
            self._require_action_mode()
            self._require_attached()
            required = {
                "episode_id",
                "host",
                "port",
                "version",
                "auth",
                "username",
                "controller_id",
                "epoch",
                "instruction_id",
                "text",
            }
            episode_id, controller_id, epoch = _parse_session_metadata(raw, self.config, required)
            self._require_episode(episode_id)
            assert controller_id is not None and epoch is not None and isinstance(raw, Mapping)
            text = raw["text"]
            if not isinstance(text, str) or not text or len(text) > 512 or any(ord(char) < 0x20 for char in text):
                raise AdapterRejected("invalid_instruction")
            instruction_id = _safe_identifier(raw["instruction_id"], "invalid_instruction")
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
            try:
                self._bridge.require_controller(controller_id, epoch)
            except BridgeRejected as error:
                raise AdapterRejected(error.code) from error
            previous = self._instructions.get(instruction_id)
            if previous is not None:
                if previous != digest:
                    raise AdapterRejected("instruction_conflict")
                return {"status": "replayed", "episode_id": episode_id, "instruction_id": instruction_id}
            if len(self._instructions) >= 256:
                self._instructions.pop(next(iter(self._instructions)))
            self._instructions[instruction_id] = digest
            self._evidence.append(
                "instruction_received",
                episode_id=episode_id,
                controller_id=controller_id,
                epoch=epoch,
                instruction_id=instruction_id,
                text_length=len(text),
                digest=digest,
                state=self._state,
            )
            return {"status": "accepted", "episode_id": episode_id, "instruction_id": instruction_id}

    def action(self, raw: object) -> dict[str, object]:
        with self._lock:
            self._require_action_mode()
            self._require_attached()
            required = {
                "episode_id",
                "host",
                "port",
                "version",
                "auth",
                "username",
                "controller_id",
                "epoch",
                "request_seq",
                "idempotency_key",
                "action",
            }
            episode_id, controller_id, epoch = _parse_session_metadata(raw, self.config, required)
            self._require_episode(episode_id)
            assert controller_id is not None and epoch is not None and isinstance(raw, Mapping)
            kind = _action_kind(raw["action"])
            if kind != "stop":
                self._require_fresh_observation()
            request_seq = _bounded_positive_int(raw["request_seq"], "invalid_request")
            idempotency_key = raw["idempotency_key"]
            if not isinstance(idempotency_key, str):
                raise AdapterRejected("invalid_request")
            self._evidence.append(
                "action_attempted",
                episode_id=episode_id,
                controller_id=controller_id,
                epoch=epoch,
                request_seq=request_seq,
                action_kind=kind,
                state=self._state,
            )
            try:
                receipt = self._bridge.submit_action(
                    controller_id=controller_id,
                    epoch=epoch,
                    request_seq=request_seq,
                    idempotency_key=idempotency_key,
                    raw_action=raw["action"],
                )
            except BridgeRejected as error:
                raise AdapterRejected(error.code) from error
            self._evidence.append(
                "action_completed",
                episode_id=episode_id,
                controller_id=controller_id,
                epoch=receipt.epoch,
                request_seq=receipt.request_seq,
                receipt_id=receipt.receipt_id,
                action_kind=receipt.action_kind,
                result=receipt.detail,
                state=self._state,
            )
            if not receipt.accepted and receipt.detail not in _RECOVERABLE_ACTION_FAILURES:
                self._fail_attached(receipt.detail)
                raise AdapterFailure(receipt.detail)
            response: dict[str, object] = {
                "status": "accepted",
                "episode_id": episode_id,
                "controller_id": controller_id,
                "epoch": receipt.epoch,
                "request_seq": receipt.request_seq,
                "receipt_id": receipt.receipt_id,
                "action_kind": receipt.action_kind,
                "accepted": receipt.accepted,
                "detail": receipt.detail,
                "replayed": receipt.replayed,
            }
            if receipt.result is not None:
                response["result"] = dict(receipt.result)
            return response

    def _require_action_mode(self) -> None:
        if not self.config.action_enabled:
            raise AdapterRejected("actions_forbidden")

    def _require_attached(self) -> None:
        if self._state != "attached" or self._client is None or self._episode_id is None:
            raise AdapterRejected("not_attached")

    def _require_episode(self, episode_id: str) -> None:
        if self._episode_id != episode_id:
            raise AdapterRejected("episode_mismatch")

    def _require_fresh_observation(self) -> None:
        observation = self._last_observation
        if observation is None or observation.observed_at_ms < self._clock_ms() - int(self.config.observation_ttl_s * 1000):
            self._fail_attached("stale_state")
            raise AdapterFailure("stale_state")

    def stop(self, raw: object) -> dict[str, object]:
        with self._lock:
            episode_id, reason = _parse_stop_request(raw, self._episode_id)
            if self._client is None:
                # Idle, failed-closed, or sticky-stop: reopen so the next attach can run.
                self._episode_id = None
                self._state = "ready"
                self._evidence.append("stopped", episode_id=episode_id, reason=reason, state=self._state)
                return {"status": "stopped", "episode_id": episode_id, "state": self._state}
            try:
                self._watched_lease_epoch = None
                self._bridge.fail_closed()
                self._close_session(self._client)
            except AdapterFailure as error:
                self._state = "failed"
                self._action_executor.set_session(None)
                self._evidence.append(
                    "stop_failed",
                    episode_id=episode_id,
                    reason=reason,
                    state=self._state,
                    error_code=error.code,
                )
                raise
            self._client = None
            self._action_executor.set_session(None)
            self._episode_id = None
            self._state = "ready"
            self._evidence.append("stopped", episode_id=episode_id, reason=reason, state=self._state)
            return {"status": "stopped", "episode_id": episode_id, "state": self._state}

    def shutdown(self) -> None:
        self._watchdog_stop.set()
        with self._lock:
            self._watched_lease_epoch = None
            self._bridge.fail_closed()
            if self._client is not None:
                try:
                    self._close_session(self._client)
                except AdapterFailure:
                    pass
                self._client = None
                self._action_executor.set_session(None)
            if self._state not in {"stopped", "failed"}:
                self._state = "stopped"
        if self._watchdog_thread is not threading.current_thread():
            self._watchdog_thread.join(timeout=min(1.0, self.config.request_timeout_s))

    def _lease_watchdog_loop(self) -> None:
        interval_s = min(1.0, max(0.025, self.config.lease_ttl_s / 4.0))
        while not self._watchdog_stop.wait(interval_s):
            self._lease_watchdog_once()

    def _lease_watchdog_once(self) -> None:
        with self._lock:
            if self._state != "attached" or self._watched_lease_epoch is None:
                return
            lease = self._bridge.current_lease
            if lease is not None:
                return
            self._watched_lease_epoch = None
            self._fail_attached("lease_expired")

    def _close_session(self, session: MineflayerSession) -> None:
        try:
            _bounded_call(session.close, self.config.request_timeout_s, timeout_s=self.config.request_timeout_s)
        except Exception as error:
            try:
                session.abort()
            except Exception:
                pass
            raise AdapterFailure(error.code if isinstance(error, AdapterFailure) else "stop_failure")

    def _fail_attached(self, error_code: str) -> None:
        self._watched_lease_epoch = None
        self._bridge.fail_closed()
        if self._client is not None:
            try:
                self._close_session(self._client)
            except AdapterFailure:
                pass
        self._client = None
        self._action_executor.set_session(None)
        self._state = "failed"
        if self._episode_id is not None:
            self._evidence.append(
                "session_failed",
                episode_id=self._episode_id,
                target_host=self.config.target.host,
                target_port=self.config.target.port,
                version=self.config.version,
                auth=self.config.auth,
                username=self.config.username,
                state=self._state,
                error_code=error_code,
            )

    @staticmethod
    def _safe_error_code(error: Exception) -> str:
        if isinstance(error, (AdapterFailure, AdapterRejected)):
            return error.code
        return "client_failure"


class FakeMineflayerSession:
    """Offline test/session double. It never opens a network socket."""

    def __init__(
        self,
        observation: Mapping[str, object],
        *,
        attach_error: str | None = None,
        walk_error: str | None = None,
        navigate_error: str | None = None,
        goto_error: str | None = None,
        chat_error: str | None = None,
        stop_motion_error: str | None = None,
        walk_delay_s: float = 0.0,
    ):
        self._observation = dict(observation)
        self._attach_error = attach_error
        self._walk_error = walk_error
        self._navigate_error = navigate_error
        self._goto_error = goto_error
        self._chat_error = chat_error
        self._stop_motion_error = stop_motion_error
        self._walk_delay_s = walk_delay_s
        self.attach_calls = 0
        self.observe_calls = 0
        self.close_calls = 0
        self.abort_calls = 0
        self.walk_calls: list[tuple[str, int]] = []
        self.look_calls: list[tuple[float, float]] = []
        self.navigate_calls: list[tuple[str, int]] = []
        self.goto_calls: list[tuple[int, int, int]] = []
        self.wood_to_table_calls: list[int] = []
        self.dig_calls: list[tuple[str, int]] = []
        self.craft_calls: list[tuple[str, int]] = []
        self.place_calls: list[str] = []
        self.chat_calls: list[str] = []
        self.stop_motion_calls = 0

    def attach(self, timeout_s: float) -> None:
        self.attach_calls += 1
        if self._attach_error:
            raise AdapterFailure(self._attach_error)

    def observation(self, timeout_s: float) -> Mapping[str, object]:
        self.observe_calls += 1
        return dict(self._observation)

    def chat_inbox(self, timeout_s: float) -> Sequence[Mapping[str, object]]:
        return []

    def walk(self, direction: str, duration_ms: int, timeout_s: float) -> None:
        if self._walk_delay_s:
            time.sleep(self._walk_delay_s)
        if self._walk_error:
            raise AdapterFailure(self._walk_error)
        self.walk_calls.append((direction, duration_ms))

    def look(self, yaw_deg: float, pitch_deg: float, timeout_s: float) -> None:
        self.look_calls.append((yaw_deg, pitch_deg))

    def navigate(self, block: str, max_distance: int, timeout_s: float) -> Mapping[str, object]:
        self.navigate_calls.append((block, max_distance))
        if self._navigate_error:
            raise AdapterFailure(self._navigate_error)
        return {"event": "pathfound", "block": block, "max_distance": max_distance}

    def goto(self, x: int, y: int, z: int, timeout_s: float) -> Mapping[str, object]:
        self.goto_calls.append((x, y, z))
        if self._goto_error:
            raise AdapterFailure(self._goto_error)
        return {"event": "pathfound", "x": x, "y": y, "z": z}

    def wood_to_table(self, max_distance: int, timeout_s: float) -> Mapping[str, object]:
        self.wood_to_table_calls.append(max_distance)
        return {
            "event": "wood_to_table_complete",
            "reason": "completed",
            "max_distance": max_distance,
            "target": {"block": "minecraft:oak_log", "x": 1, "y": 64, "z": -2},
            "target_after": "minecraft:air",
            "before": {"logs": 4, "planks": 0, "crafting_tables": 0},
            "after_harvest": {"logs": 5, "planks": 0, "crafting_tables": 0},
            "after_planks": {"logs": 4, "planks": 4, "crafting_tables": 0},
            "after": {"logs": 4, "planks": 0, "crafting_tables": 1},
        }

    def dig(self, block: str, max_distance: int, timeout_s: float) -> Mapping[str, object]:
        self.dig_calls.append((block, max_distance))
        return {"ok": True, "event": "dug", "block": block, "collected": True}

    def craft(self, item: str, count: int, timeout_s: float) -> Mapping[str, object]:
        self.craft_calls.append((item, count))
        return {"ok": True, "event": "crafted", "item": item, "count": count}

    def place(self, item: str, timeout_s: float) -> Mapping[str, object]:
        self.place_calls.append(item)
        return {"ok": True, "event": "placed", "item": item}

    def chat(self, message: str, timeout_s: float) -> None:
        if self._chat_error:
            raise AdapterFailure(self._chat_error)
        self.chat_calls.append(message)

    def stop_motion(self, timeout_s: float) -> None:
        self.stop_motion_calls += 1
        if self._stop_motion_error:
            raise AdapterFailure(self._stop_motion_error)

    def close(self, timeout_s: float) -> None:
        self.close_calls += 1

    def abort(self) -> None:
        self.abort_calls += 1


class FakeMineflayerFactory:
    def __init__(
        self,
        observation: Mapping[str, object],
        *,
        attach_error: str | None = None,
        walk_error: str | None = None,
        navigate_error: str | None = None,
        goto_error: str | None = None,
        chat_error: str | None = None,
        stop_motion_error: str | None = None,
        walk_delay_s: float = 0.0,
    ):
        self.observation_value = dict(observation)
        self.attach_error = attach_error
        self.walk_error = walk_error
        self.navigate_error = navigate_error
        self.goto_error = goto_error
        self.chat_error = chat_error
        self.stop_motion_error = stop_motion_error
        self.walk_delay_s = walk_delay_s
        self.sessions: list[FakeMineflayerSession] = []

    def create(self, config: AdapterConfig) -> MineflayerSession:
        session = FakeMineflayerSession(
            self.observation_value,
            attach_error=self.attach_error,
            walk_error=self.walk_error,
            navigate_error=self.navigate_error,
            goto_error=self.goto_error,
            chat_error=self.chat_error,
            stop_motion_error=self.stop_motion_error,
            walk_delay_s=self.walk_delay_s,
        )
        self.sessions.append(session)
        return session


class NodeMineflayerSession:
    """Restricted JSON-line client for the shipped Node worker."""

    def __init__(self, config: AdapterConfig):
        script = config.client_script or Path(__file__).with_name("mineflayer_client.cjs")
        if not script.is_file() or script.is_symlink():
            raise AdapterFailure("client_script_missing")
        try:
            environment = None
            if config.node_modules_dir is not None:
                environment = os.environ.copy()
                environment["NODE_PATH"] = str(config.node_modules_dir)
            self._process = subprocess.Popen(
                [config.node_exe, str(script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=environment,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as error:
            raise AdapterFailure("node_runtime_unavailable") from error
        self._config = config
        self._lock = threading.Lock()

    def _request(self, payload: Mapping[str, object], timeout_s: float) -> Mapping[str, object]:
        with self._lock:
            if self._process.poll() is not None or self._process.stdin is None or self._process.stdout is None:
                raise AdapterFailure("client_exited")
            try:
                self._process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
                self._process.stdin.flush()
            except OSError as error:
                raise AdapterFailure("client_write_failure") from error
            response: queue.Queue[object] = queue.Queue(maxsize=1)

            def read_line() -> None:
                try:
                    response.put(self._process.stdout.readline())
                except Exception:
                    response.put(None)

            reader = threading.Thread(target=read_line, daemon=True)
            reader.start()
            reader.join(timeout_s)
            if reader.is_alive():
                raise AdapterFailure("operation_timeout")
            line = response.get_nowait()
            if not isinstance(line, str) or not line:
                raise AdapterFailure("client_exited")
            try:
                decoded = json.loads(line)
            except json.JSONDecodeError as error:
                raise AdapterFailure("invalid_client_response") from error
            if not isinstance(decoded, Mapping):
                raise AdapterFailure("invalid_client_response")
            if decoded.get("ok") is not True:
                raise AdapterFailure(str(decoded.get("error_code", "client_failure")))
            return decoded

    def attach(self, timeout_s: float) -> None:
        self._request(
            {
                "op": "attach",
                "host": self._config.target.host,
                "port": self._config.target.port,
                "version": self._config.version,
                "auth": self._config.auth,
                "username": self._config.username,
                "auth_cache_dir": str(self._config.auth_cache_dir) if self._config.auth_cache_dir is not None else None,
                "action_enabled": self._config.action_enabled,
                "movement_log_path": str(self._config.evidence_dir / "movement.jsonl"),
            },
            timeout_s,
        )

    def observation(self, timeout_s: float) -> Mapping[str, object]:
        response = self._request({"op": "observe"}, timeout_s)
        observation = response.get("observation")
        if not isinstance(observation, Mapping):
            raise AdapterFailure("invalid_client_response")
        return observation

    def chat_inbox(self, timeout_s: float) -> Sequence[Mapping[str, object]]:
        response = self._request({"op": "read_chat"}, timeout_s)
        messages = response.get("messages")
        if not isinstance(messages, list):
            raise AdapterFailure("invalid_client_response")
        return messages

    def walk(self, direction: str, duration_ms: int, timeout_s: float) -> None:
        self._request({"op": "move", "direction": direction, "duration_ms": duration_ms}, timeout_s)

    def look(self, yaw_deg: float, pitch_deg: float, timeout_s: float) -> None:
        self._request({"op": "look", "yaw_deg": yaw_deg, "pitch_deg": pitch_deg}, timeout_s)

    def navigate(self, block: str, max_distance: int, timeout_s: float) -> Mapping[str, object]:
        return self._request({"op": "navigate", "block": block, "max_distance": max_distance}, timeout_s)

    def goto(self, x: int, y: int, z: int, timeout_s: float) -> Mapping[str, object]:
        return self._request({"op": "goto", "x": x, "y": y, "z": z}, timeout_s)

    def wood_to_table(self, max_distance: int, timeout_s: float) -> Mapping[str, object]:
        try:
            return _wood_to_table_result(
                self._request({"op": "wood_to_table", "max_distance": max_distance}, timeout_s)
            )
        except AdapterRejected as error:
            raise AdapterFailure("invalid_operation_result") from error

    def dig(self, block: str, max_distance: int, timeout_s: float) -> Mapping[str, object]:
        return self._request({"op": "dig", "block": block, "max_distance": max_distance}, timeout_s)

    def craft(self, item: str, count: int, timeout_s: float) -> Mapping[str, object]:
        return self._request({"op": "craft", "item": item, "count": count}, timeout_s)

    def place(self, item: str, timeout_s: float) -> Mapping[str, object]:
        return self._request({"op": "place", "item": item}, timeout_s)

    def chat(self, message: str, timeout_s: float) -> None:
        self._request({"op": "chat", "message": message}, timeout_s)

    def stop_motion(self, timeout_s: float) -> None:
        self._request({"op": "stop_motion"}, timeout_s)

    def close(self, timeout_s: float) -> None:
        self._request({"op": "stop"}, timeout_s)
        self._process.wait(timeout=timeout_s)

    def abort(self) -> None:
        if self._process.poll() is None:
            self._process.kill()


class NodeMineflayerFactory:
    def create(self, config: AdapterConfig) -> MineflayerSession:
        return NodeMineflayerSession(config)


class AdapterHTTPHandler(BaseHTTPRequestHandler):
    service: AdapterService

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, status: HTTPStatus, payload: Mapping[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> object:
        length_text = self.headers.get("Content-Length")
        if length_text is None or not length_text.isdecimal() or int(length_text) > 64 * 1024:
            raise AdapterRejected("invalid_request")
        try:
            body = self.rfile.read(int(length_text))
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AdapterRejected("invalid_request")

    def _handle(self, function: Callable[..., Mapping[str, object]], *args: object) -> None:
        try:
            self._send_json(HTTPStatus.OK, function(*args))
        except AdapterRejected as error:
            status = HTTPStatus.CONFLICT if error.code in {"invalid_state", "not_attached"} else HTTPStatus.BAD_REQUEST
            self._send_json(status, {"error_code": error.code})
        except AdapterFailure as error:
            status = HTTPStatus.GATEWAY_TIMEOUT if error.code in {"operation_timeout", "action_timeout"} else HTTPStatus.BAD_GATEWAY
            self._send_json(status, {"error_code": error.code})

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._handle(self.service.health)
        elif self.path == "/v1/observation":
            self._handle(self.service.observation)
        elif self.path == "/v1/chat/inbox":
            self._handle(self.service.chat_inbox)
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error_code": "not_found"})

    def do_POST(self) -> None:
        if self.path not in {
            "/v1/attach",
            "/v1/controller/claim",
            "/v1/controller/heartbeat",
            "/v1/controller/release",
            "/v1/instruction",
            "/v1/action",
            "/v1/stop",
        }:
            self._send_json(HTTPStatus.NOT_FOUND, {"error_code": "not_found"})
            return
        try:
            body = self._read_json()
        except AdapterRejected as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error_code": error.code})
            return
        if self.path == "/v1/attach":
            self._handle(self.service.attach, body)
        elif self.path == "/v1/controller/claim":
            self._handle(self.service.claim_controller, body)
        elif self.path == "/v1/controller/heartbeat":
            self._handle(self.service.heartbeat, body)
        elif self.path == "/v1/controller/release":
            self._handle(self.service.release_controller, body)
        elif self.path == "/v1/instruction":
            self._handle(self.service.instruction, body)
        elif self.path == "/v1/action":
            self._handle(self.service.action, body)
        else:
            self._handle(self.service.stop, body)


class AdapterHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def build_server(service: AdapterService, *, port: int | None = None) -> AdapterHTTPServer:
    bind_port = service.config.control_port if port is None else port
    server = AdapterHTTPServer((service.config.bind_host, bind_port), AdapterHTTPHandler)
    server.RequestHandlerClass.service = service
    return server


def _cli_config(arguments: argparse.Namespace) -> AdapterConfig:
    allowed = [parse_target_text(value) for value in arguments.allowed_target]
    if arguments.enable_actions and (arguments.observe_only or arguments.no_actions):
        raise AdapterRejected("conflicting_action_flags")
    return AdapterConfig.from_mapping(
        {
            "bind_host": arguments.bind,
            "control_port": arguments.control_port,
            "target_host": arguments.mc_host,
            "target_port": arguments.mc_port,
            "version": arguments.mc_version,
            "auth": arguments.auth,
            "username": arguments.username,
            "observe_only": not arguments.enable_actions,
            "allow_actions": arguments.enable_actions,
            "action_enabled": arguments.enable_actions,
            "allowed_targets": [{"host": target.host, "port": target.port} for target in allowed],
            "evidence_dir": arguments.evidence_dir,
            "node_exe": arguments.node_exe,
            "client_script": arguments.client_script,
            "node_modules_dir": arguments.node_modules_dir,
            "auth_cache_dir": arguments.auth_cache_dir,
            "action_timeout_s": arguments.action_timeout_s,
            "lease_ttl_s": arguments.lease_ttl_s,
        }
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="loopback-only Mineflayer adapter; actions require explicit opt-in")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--control-port", type=int, required=True)
    parser.add_argument("--mc-host", required=True)
    parser.add_argument("--mc-port", type=int, required=True)
    parser.add_argument("--mc-version", required=True)
    parser.add_argument("--auth", required=True, choices=sorted(_AUTH_MODES))
    parser.add_argument("--username", required=True)
    parser.add_argument("--allowed-target", action="append", required=True, metavar="HOST:PORT")
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--node-exe", default="node")
    parser.add_argument("--client-script")
    parser.add_argument("--node-modules-dir")
    parser.add_argument("--auth-cache-dir")
    parser.add_argument("--action-timeout-s", type=float, default=5.0)
    parser.add_argument("--lease-ttl-s", type=float, default=60.0)
    parser.add_argument("--factory", choices=("node", "fake"), default="node")
    parser.add_argument("--observe-only", action="store_true")
    parser.add_argument("--no-actions", action="store_true")
    parser.add_argument("--enable-actions", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        config = _cli_config(arguments)
    except AdapterRejected as error:
        print(json.dumps({"error_code": error.code}, separators=(",", ":")), file=sys.stderr)
        return 2
    factory: MineflayerFactory = FakeMineflayerFactory(_default_fake_observation()) if arguments.factory == "fake" else NodeMineflayerFactory()
    service = AdapterService(config, factory)
    server = build_server(service)
    print(json.dumps({"status": "ready", **service.health()}, separators=(",", ":")), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        service.shutdown()
        server.server_close()
    return 0


def _default_fake_observation() -> dict[str, object]:
    now = int(time.time() * 1000)
    return {
        "schema_version": "observation.v1",
        "observation_id": "fake-observation",
        "observed_at_ms": now,
        "dimension": "overworld",
        "position": {"x": 0.0, "y": 64.0, "z": 0.0},
        "velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
        "health": 20.0,
        "food": 20,
        "air": 300,
        "fire_ticks": 0,
        "is_alive": True,
        "selected_slot": 0,
        "inventory": [],
        "nearby_entities": [],
    }


if __name__ == "__main__":
    raise SystemExit(main())
