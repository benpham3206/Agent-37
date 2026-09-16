from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from mineflayer_adapter import (  # noqa: E402
    AdapterConfig,
    AdapterFailure,
    AdapterHTTPServer,
    AdapterRejected,
    AdapterService,
    EvidenceLog,
    FakeMineflayerFactory,
    NodeMineflayerSession,
    build_server,
)


HOST = "6ento.lunarclient.world"
PORT = 64680
NODE = Path(r"D:\Codex\2026-08-26\plea\work\node-v22.23.2-win-x64\node.exe")
WORKER = HERE / "mineflayer_client.cjs"


def valid_observation(*, observed_at_ms: int | None = None) -> dict[str, object]:
    return {
        "schema_version": "observation.v1",
        "observation_id": "obs-1",
        "observed_at_ms": int(time.time() * 1000) if observed_at_ms is None else observed_at_ms,
        "dimension": "overworld",
        "position": {"x": 1.0, "y": 64.0, "z": -2.0},
        "velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
        "health": 20.0,
        "food": 20,
        "air": 300,
        "fire_ticks": 0,
        "is_alive": True,
        "selected_slot": 0,
        "inventory": [{"slot": 0, "item": "minecraft:oak_log", "count": 4}],
        "nearby_entities": [],
    }


def valid_perception_observation(*, observed_at_ms: int | None = None) -> dict[str, object]:
    observation = valid_observation(observed_at_ms=observed_at_ms)
    observation.update(
        {
            "schema_version": "observation.v2",
            "recent_chat": [
                {"sender": "PlayerOne", "message": "hello PrimeBot", "received_at_ms": observation["observed_at_ms"]}
            ],
            "world": {
                "below": "minecraft:grass_block",
                "feet": "minecraft:air",
                "head": "minecraft:air",
                "nearby_blocks": [{"block": "minecraft:oak_log", "distance": 3.0}],
            },
        }
    )
    return observation


def valid_advancement_observation(*, observed_at_ms: int | None = None) -> dict[str, object]:
    observation = valid_perception_observation(observed_at_ms=observed_at_ms)
    observation.update(
        {
            "schema_version": "observation.v3",
            "advancements": {
                "known": True,
                "entries": {
                    "minecraft:story/root": {
                        "requirements": [["crafting_table"]],
                        "criteria": {"crafting_table": None},
                    }
                },
            },
        }
    )
    return observation


def config_mapping(directory: str, **overrides: object) -> dict[str, object]:
    mapping: dict[str, object] = {
        "bind_host": "127.0.0.1",
        "control_port": 8765,
        "target_host": HOST,
        "target_port": PORT,
        "version": "26.1.2",
        "auth": "offline",
        "username": "DObserver",
        "observe_only": True,
        "allow_actions": False,
        "action_enabled": False,
        "allowed_targets": [{"host": HOST, "port": PORT}],
        "evidence_dir": directory,
        "attach_timeout_s": 1.0,
        "request_timeout_s": 0.5,
        "observation_ttl_s": 1.0,
    }
    mapping.update(overrides)
    return mapping


def attach_request(*, episode_id: str = "episode-1", **overrides: object) -> dict[str, object]:
    request: dict[str, object] = {
        "episode_id": episode_id,
        "host": HOST,
        "port": PORT,
        "version": "26.1.2",
        "auth": "offline",
        "username": "DObserver",
        "observe_only": True,
        "allow_actions": False,
        "action_enabled": False,
    }
    request.update(overrides)
    return request


def action_config_overrides() -> dict[str, object]:
    return {"observe_only": False, "allow_actions": True, "action_enabled": True}


def action_attach_request(*, episode_id: str = "episode-1") -> dict[str, object]:
    request = attach_request(episode_id=episode_id)
    request.update({"observe_only": False, "allow_actions": True, "action_enabled": True})
    return request


def controller_request(*, controller_id: str = "prime-actor", episode_id: str = "episode-1") -> dict[str, object]:
    return {
        "episode_id": episode_id,
        "host": HOST,
        "port": PORT,
        "version": "26.1.2",
        "auth": "offline",
        "username": "DObserver",
        "controller_id": controller_id,
    }


def lease_request(*, controller_id: str = "prime-actor", epoch: int = 1, episode_id: str = "episode-1") -> dict[str, object]:
    request = controller_request(controller_id=controller_id, episode_id=episode_id)
    request["epoch"] = epoch
    return request


def instruction_request(*, controller_id: str = "prime-actor", epoch: int = 1, text: str = "walk forward") -> dict[str, object]:
    request = lease_request(controller_id=controller_id, epoch=epoch)
    request.update({"instruction_id": "instruction-1", "text": text})
    return request


def action_request(
    action: dict[str, object],
    *,
    controller_id: str = "prime-actor",
    epoch: int = 1,
    request_seq: int = 1,
    idempotency_key: str = "action-1",
) -> dict[str, object]:
    request = lease_request(controller_id=controller_id, epoch=epoch)
    request.update({"request_seq": request_seq, "idempotency_key": idempotency_key, "action": action})
    return request


class AdapterConfigBoundaryTests(unittest.TestCase):
    def test_requires_loopback_control_plane(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AdapterRejected, "loopback_required"):
                AdapterConfig.from_mapping(config_mapping(directory, bind_host="0.0.0.0"))

    def test_requires_exact_allowlisted_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AdapterRejected, "target_not_allowlisted"):
                AdapterConfig.from_mapping(
                    config_mapping(directory, target_host="other.example", allowed_targets=[{"host": HOST, "port": PORT}])
                )
            with self.assertRaisesRegex(AdapterRejected, "invalid_allowlist"):
                AdapterConfig.from_mapping(
                    config_mapping(directory, allowed_targets=[{"host": HOST, "port": PORT}, {"host": HOST, "port": PORT}])
                )

    def test_rejects_ambiguous_version_and_auth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for key, value, code in (
                ("version", "auto", "explicit_version_required"),
                ("version", "latest", "explicit_version_required"),
                ("auth", "", "explicit_auth_required"),
                ("auth", "unknown", "explicit_auth_required"),
            ):
                with self.subTest(key=key, value=value):
                    with self.assertRaisesRegex(AdapterRejected, code):
                        AdapterConfig.from_mapping(config_mapping(directory, **{key: value}))

    def test_requires_observe_only_and_no_actions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AdapterRejected, "observe_only_required"):
                AdapterConfig.from_mapping(config_mapping(directory, observe_only=False))
            with self.assertRaisesRegex(AdapterRejected, "actions_forbidden"):
                AdapterConfig.from_mapping(config_mapping(directory, allow_actions=True))

    def test_requires_explicit_fields_and_real_evidence_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = config_mapping(directory)
            del missing["username"]
            with self.assertRaisesRegex(AdapterRejected, "invalid_config"):
                AdapterConfig.from_mapping(missing)
            with self.assertRaisesRegex(AdapterRejected, "invalid_evidence_dir"):
                AdapterConfig.from_mapping(config_mapping(str(Path(directory) / "missing")))


class AdapterServiceTests(unittest.TestCase):
    @contextmanager
    def service(
        self,
        *,
        observation: dict[str, object] | None = None,
        factory_options: dict[str, object] | None = None,
        **config_overrides: object,
    ):
        with tempfile.TemporaryDirectory() as directory:
            config = AdapterConfig.from_mapping(config_mapping(directory, **config_overrides))
            factory = FakeMineflayerFactory(observation or valid_observation(), **(factory_options or {}))
            service = AdapterService(config, factory)
            try:
                yield service, factory, config
            finally:
                service.shutdown()

    def test_health_attach_observe_stop_lifecycle_is_clean(self) -> None:
        with self.service() as (service, factory, config):
            health = service.health()
            self.assertEqual(health["state"], "ready")
            self.assertFalse(health["allow_actions"])
            self.assertEqual(service.attach(attach_request()), {**{
                "status": "attached",
                "episode_id": "episode-1",
                "target": {"host": HOST, "port": PORT},
                "version": "26.1.2",
                "auth": "offline",
                "username": "DObserver",
                "logged_in": True,
                "spawned": True,
                "observe_only": True,
                "allow_actions": False,
                "action_enabled": False,
            }})
            response = service.observation()
            self.assertEqual(response["episode_id"], "episode-1")
            self.assertTrue(response["observe_only"])
            self.assertFalse(response["allow_actions"])
            self.assertEqual(response["observation"]["observation_id"], "obs-1")
            stopped = service.stop({"episode_id": "episode-1", "reason": "test-stop"})
            self.assertEqual(stopped["state"], "ready")
            self.assertEqual(factory.sessions[0].close_calls, 1)
            self.assertFalse(service.health()["client_attached"])
            self.assertEqual(service.stop({"episode_id": "episode-1", "reason": "test-stop-again"})["state"], "ready")
            self.assertEqual(factory.sessions[0].close_calls, 1)

    def test_health_returns_while_action_lock_is_held(self) -> None:
        with self.service() as (service, _factory, _config):
            service._lock.acquire()
            try:
                health = service.health()
            finally:
                service._lock.release()
            self.assertEqual(health["state"], "ready")
            self.assertFalse(health["client_attached"])

    def test_rejects_malformed_attach_before_factory(self) -> None:
        with self.service() as (service, factory, _):
            bad = attach_request(port=25565)
            with self.assertRaisesRegex(AdapterRejected, "target_not_allowlisted"):
                service.attach(bad)
            self.assertEqual(factory.sessions, [])
            bad = attach_request(extra="unsupported")
            with self.assertRaisesRegex(AdapterRejected, "invalid_attach"):
                service.attach(bad)
            self.assertEqual(factory.sessions, [])

    def test_stale_observation_fails_closed_and_detaches(self) -> None:
        stale = valid_observation(observed_at_ms=int(time.time() * 1000) - 10_000)
        with self.service(observation=stale, observation_ttl_s=0.1) as (service, factory, _):
            service.attach(attach_request())
            with self.assertRaisesRegex(AdapterFailure, "stale_observation"):
                service.observation()
            self.assertEqual(service.health()["state"], "failed")
            self.assertFalse(service.health()["client_attached"])
            self.assertEqual(factory.sessions[0].close_calls, 1)

    def test_invalid_observation_fails_closed(self) -> None:
        malformed = valid_observation()
        del malformed["health"]
        with self.service(observation=malformed) as (service, factory, _):
            service.attach(attach_request())
            with self.assertRaisesRegex(AdapterFailure, "invalid_observation"):
                service.observation()
            self.assertEqual(service.health()["state"], "failed")
            self.assertEqual(factory.sessions[0].close_calls, 1)

    def test_perception_v3_returns_advancements_but_not_adapter_evidence(self) -> None:
        with self.service(observation=valid_advancement_observation()) as (service, _, _):
            service.attach(attach_request())
            observed = service.observation()
            self.assertEqual(observed["observation"]["schema_version"], "observation.v3")
            self.assertTrue(observed["observation"]["advancements"]["known"])
            self.assertIn("minecraft:story/root", observed["observation"]["advancements"]["entries"])
            evidence = service.evidence_path.read_text(encoding="utf-8")
            self.assertNotIn("minecraft:story/root", evidence)
        with self.service(observation=valid_perception_observation()) as (service, _, _):
            service.attach(attach_request())
            observed = service.observation()
            self.assertEqual(observed["observation"]["schema_version"], "observation.v2")
            self.assertEqual(observed["observation"]["recent_chat"][0]["message"], "hello PrimeBot")
            self.assertEqual(observed["observation"]["world"]["nearby_blocks"][0]["block"], "minecraft:oak_log")
            evidence = service.evidence_path.read_text(encoding="utf-8")
            self.assertNotIn("hello PrimeBot", evidence)
            self.assertNotIn("minecraft:oak_log", evidence)

    def test_client_attach_failure_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = AdapterConfig.from_mapping(config_mapping(directory))
            factory = FakeMineflayerFactory(valid_observation(), attach_error="client_attach_failure")
            service = AdapterService(config, factory)
            with self.assertRaisesRegex(AdapterFailure, "client_attach_failure"):
                service.attach(attach_request())
            self.assertEqual(service.health()["state"], "failed")
            self.assertEqual(factory.sessions[0].close_calls, 1)

    def test_evidence_is_append_only_and_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adapter-events.jsonl"
            path.write_text("sentinel\n", encoding="utf-8")
            log = EvidenceLog(Path(directory))
            with self.assertRaisesRegex(AdapterRejected, "invalid_evidence"):
                log.append("bad", secret="must-not-be-accepted")
            log.append("safe", episode_id="episode-1", state="ready")
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("sentinel\n"))
            self.assertEqual(json.loads(text.splitlines()[1])["event_type"], "safe")
            self.assertNotIn("secret", text)

    def test_action_mode_is_explicit_and_supports_instruction_move_chat_and_stop(self) -> None:
        with self.service(**action_config_overrides()) as (service, factory, _):
            attached = service.attach(action_attach_request())
            self.assertFalse(attached["observe_only"])
            self.assertTrue(attached["allow_actions"])
            self.assertTrue(attached["action_enabled"])
            service.observation()
            lease = service.claim_controller(controller_request())
            self.assertEqual(lease["controller_id"], "prime-actor")
            instruction = service.instruction(instruction_request())
            self.assertEqual(instruction["status"], "accepted")
            moved = service.action(action_request({"kind": "move", "direction": "forward", "duration_ms": 250}))
            self.assertEqual(moved["action_kind"], "move")
            self.assertEqual(factory.sessions[0].walk_calls, [("forward", 250)])
            chatted = service.action(
                action_request(
                    {"kind": "chat", "message": "Prime checkpoint ready"},
                    request_seq=2,
                    idempotency_key="action-2",
                )
            )
            self.assertEqual(chatted["action_kind"], "chat")
            self.assertEqual(factory.sessions[0].chat_calls, ["Prime checkpoint ready"])
            looked = service.action(
                action_request(
                    {"kind": "look", "yaw_deg": 0, "pitch_deg": 0},
                    request_seq=3,
                    idempotency_key="action-look",
                )
            )
            self.assertEqual(looked["action_kind"], "look")
            self.assertEqual(factory.sessions[0].look_calls, [(0, 0)])
            navigated = service.action(
                action_request(
                    {"kind": "navigate", "block": "wood", "max_distance": 64},
                    request_seq=4,
                    idempotency_key="action-navigate",
                )
            )
            self.assertEqual(navigated["action_kind"], "navigate")
            self.assertEqual(navigated["detail"], "pathfound")
            self.assertEqual(factory.sessions[0].navigate_calls, [("wood", 64)])
            went = service.action(
                action_request(
                    {"kind": "goto", "x": 4, "y": 64, "z": -2},
                    request_seq=5,
                    idempotency_key="action-goto",
                )
            )
            self.assertEqual(went["action_kind"], "goto")
            self.assertEqual(went["detail"], "pathfound")
            self.assertEqual(factory.sessions[0].goto_calls, [(4, 64, -2)])
            wood_to_table = service.action(
                action_request(
                    {"kind": "wood_to_table", "max_distance": 64},
                    request_seq=6,
                    idempotency_key="action-wood-to-table",
                )
            )
            self.assertEqual(wood_to_table["action_kind"], "wood_to_table")
            self.assertEqual(wood_to_table["detail"], "wood_to_table_complete")
            self.assertEqual(wood_to_table["result"]["after"]["crafting_tables"], 1)
            self.assertEqual(factory.sessions[0].wood_to_table_calls, [64])
            action_stop = service.action(
                action_request(
                    {"kind": "stop"},
                    request_seq=7,
                    idempotency_key="action-stop",
                )
            )
            self.assertEqual(action_stop["action_kind"], "stop")
            stopped = service.stop({"episode_id": "episode-1", "reason": "checkpoint-stop"})
            self.assertEqual(stopped["state"], "ready")
            self.assertEqual(factory.sessions[0].close_calls, 1)
            self.assertGreaterEqual(factory.sessions[0].stop_motion_calls, 1)
            evidence = service.evidence_path.read_text(encoding="utf-8")
            self.assertIn("instruction_received", evidence)
            self.assertIn("action_completed", evidence)
            self.assertNotIn("Prime checkpoint ready", evidence)

    def test_target_unavailable_is_recoverable_and_can_stop_cleanly(self) -> None:
        with self.service(**action_config_overrides()) as (service, factory, _):
            service.attach(action_attach_request())
            service.observation()
            service.claim_controller(controller_request())
            before = {"logs": 0, "planks": 0, "crafting_tables": 0}
            factory.sessions[0].wood_to_table = lambda max_distance, timeout_s: {
                "event": "target_unavailable",
                "reason": "no_log_in_range",
                "max_distance": max_distance,
                "target": None,
                "target_after": None,
                "before": before,
                "after_harvest": None,
                "after_planks": None,
                "after": before,
            }

            receipt = service.action(
                action_request({"kind": "wood_to_table", "max_distance": 64})
            )

            self.assertTrue(receipt["accepted"])
            self.assertEqual(receipt["detail"], "target_unavailable")
            self.assertEqual(service.health()["state"], "attached")
            stopped = service.stop({"episode_id": "episode-1", "reason": "target-unavailable"})
            self.assertEqual(stopped["state"], "ready")
            evidence = service.evidence_path.read_text(encoding="utf-8")
            self.assertIn('"result":"target_unavailable"', evidence)
            self.assertNotIn('"event_type":"session_failed"', evidence)

    def test_single_controller_lease_rejects_other_owner(self) -> None:
        with self.service(**action_config_overrides()) as (service, _, _):
            service.attach(action_attach_request())
            service.observation()
            service.claim_controller(controller_request(controller_id="controller-a"))
            with self.assertRaisesRegex(AdapterRejected, "controller_mismatch"):
                service.action(action_request({"kind": "move", "direction": "forward", "duration_ms": 10}, controller_id="controller-b"))

    def test_idle_lease_expiry_watchdog_closes_the_session(self) -> None:
        with self.service(lease_ttl_s=0.1, **action_config_overrides()) as (service, factory, _):
            service.attach(action_attach_request())
            service.observation()
            service.claim_controller(controller_request())

            deadline = time.monotonic() + 1.0
            while service.health()["state"] == "attached" and time.monotonic() < deadline:
                time.sleep(0.01)

            self.assertEqual(service.health()["state"], "failed")
            self.assertEqual(factory.sessions[0].close_calls, 1)
            self.assertGreaterEqual(factory.sessions[0].stop_motion_calls, 1)
            evidence = service.evidence_path.read_text(encoding="utf-8")
            self.assertIn('"event_type":"session_failed"', evidence)
            self.assertIn('"error_code":"lease_expired"', evidence)
            stopped = service.stop({"episode_id": "episode-1", "reason": "reopen-after-fail"})
            self.assertEqual(stopped["state"], "ready")
            self.assertEqual(service.health()["state"], "ready")
            self.assertEqual(service.attach(action_attach_request())["status"], "attached")

    def test_action_requires_fresh_state_and_stops_on_stale_state(self) -> None:
        with self.service(observation_ttl_s=0.1, **action_config_overrides()) as (service, factory, _):
            service.attach(action_attach_request())
            service.claim_controller(controller_request())
            with self.assertRaisesRegex(AdapterFailure, "stale_state"):
                service.action(action_request({"kind": "move", "direction": "forward", "duration_ms": 10}))
            self.assertEqual(service.health()["state"], "failed")
            self.assertEqual(factory.sessions[0].close_calls, 1)
            self.assertIn("stale_state", service.evidence_path.read_text(encoding="utf-8"))

    def test_recoverable_navigation_failure_keeps_episode_attached(self) -> None:
        with self.service(factory_options={"navigate_error": "path_not_found"}, **action_config_overrides()) as (service, factory, _):
            service.attach(action_attach_request())
            service.observation()
            service.claim_controller(controller_request())
            receipt = service.action(action_request({"kind": "navigate", "block": "oak_log", "max_distance": 64}))
            self.assertFalse(receipt["accepted"])
            self.assertEqual(receipt["detail"], "path_not_found")
            self.assertEqual(service.health()["state"], "attached")
            self.assertEqual(factory.sessions[0].close_calls, 0)
            service.stop({"episode_id": "episode-1", "reason": "test-stop"})

    def test_goto_rejects_non_integer_coordinates(self) -> None:
        with self.service(**action_config_overrides()) as (service, factory, _):
            service.attach(action_attach_request())
            service.observation()
            service.claim_controller(controller_request())
            with self.assertRaisesRegex(AdapterRejected, "invalid_value"):
                service.action(action_request({"kind": "goto", "x": 1.5, "y": 64, "z": 0}))
            self.assertEqual(factory.sessions[0].goto_calls, [])

    def test_action_timeout_fails_closed(self) -> None:
        with self.service(
            factory_options={"walk_delay_s": 0.5},
            action_timeout_s=0.1,
            **action_config_overrides(),
        ) as (service, factory, _):
            service.attach(action_attach_request())
            service.observation()
            service.claim_controller(controller_request())
            with self.assertRaisesRegex(AdapterFailure, "action_timeout"):
                service.action(action_request({"kind": "move", "direction": "forward", "duration_ms": 500}))
            self.assertEqual(service.health()["state"], "failed")
            self.assertEqual(factory.sessions[0].close_calls, 1)

    def test_chat_length_and_redaction_boundaries(self) -> None:
        with self.service(**action_config_overrides()) as (service, _, _):
            service.attach(action_attach_request())
            service.observation()
            service.claim_controller(controller_request())
            with self.assertRaisesRegex(AdapterRejected, "invalid_value"):
                service.action(action_request({"kind": "chat", "message": "x" * 201}))
            with self.assertRaisesRegex(AdapterRejected, "unsafe_chat"):
                service.action(
                    action_request(
                        {"kind": "chat", "message": "password=do-not-send"},
                        idempotency_key="secret-chat",
                    )
                )
            evidence = service.evidence_path.read_text(encoding="utf-8")
            self.assertNotIn("do-not-send", evidence)

    def test_explicit_action_mode_rejects_ambiguous_flags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AdapterRejected, "observe_only_required"):
                AdapterConfig.from_mapping(
                    config_mapping(
                        directory,
                        action_enabled=True,
                        observe_only=True,
                        allow_actions=True,
                    )
                )


class AdapterHTTPTests(unittest.TestCase):
    @contextmanager
    def http_service(self):
        with tempfile.TemporaryDirectory() as directory:
            config = AdapterConfig.from_mapping(config_mapping(directory))
            factory = FakeMineflayerFactory(valid_observation())
            service = AdapterService(config, factory)
            server: AdapterHTTPServer = build_server(service, port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield service, factory, f"http://127.0.0.1:{server.server_address[1]}"
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()
                service.shutdown()

    @staticmethod
    def request(base: str, method: str, path: str, body: object | None = None) -> tuple[int, dict[str, object]]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(f"{base}{path}", data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=2) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def test_http_health_attach_observe_stop_and_no_action_route(self) -> None:
        with self.http_service() as (_, factory, base):
            status, health = self.request(base, "GET", "/healthz")
            self.assertEqual(status, 200)
            self.assertFalse(health["capabilities"]["actions"])
            status, attached = self.request(base, "POST", "/v1/attach", attach_request())
            self.assertEqual(status, 200)
            self.assertTrue(attached["observe_only"])
            status, observed = self.request(base, "GET", "/v1/observation")
            self.assertEqual(status, 200)
            self.assertEqual(observed["observation"]["observation_id"], "obs-1")
            status, body = self.request(base, "POST", "/v1/action", {"kind": "move"})
            self.assertEqual(status, 400)
            self.assertEqual(body["error_code"], "actions_forbidden")
            status, stopped = self.request(base, "POST", "/v1/stop", {"episode_id": "episode-1", "reason": "http-stop"})
            self.assertEqual(status, 200)
            self.assertEqual(stopped["state"], "ready")
            self.assertEqual(factory.sessions[0].close_calls, 1)


class NodeWorkerTests(unittest.TestCase):
    def test_explicit_dependency_root_is_passed_to_node_worker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dependency_root = Path(directory) / "node_modules"
            dependency_root.mkdir()
            config = AdapterConfig.from_mapping(
                config_mapping(directory, node_modules_dir=str(dependency_root))
            )
            with patch("mineflayer_adapter.subprocess.Popen") as popen:
                NodeMineflayerSession(config)
            self.assertEqual(
                popen.call_args.kwargs["env"]["NODE_PATH"],
                str(dependency_root),
            )

    def test_restricted_worker_exists_and_has_valid_syntax(self) -> None:
        self.assertTrue(WORKER.is_file())
        self.assertTrue(NODE.is_file())
        result = subprocess.run([str(NODE), "--check", str(WORKER)], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        los = subprocess.run([str(NODE), str(WORKER.with_name("test_dig_los.cjs"))], capture_output=True, text=True, timeout=5, cwd=str(WORKER.parent))
        self.assertEqual(los.returncode, 0, los.stderr + los.stdout)
        self.assertIn("ok", los.stdout)
        ash_path = subprocess.run([str(NODE), str(WORKER.with_name("test_ash_path.cjs"))], capture_output=True, text=True, timeout=5, cwd=str(WORKER.parent))
        self.assertEqual(ash_path.returncode, 0, ash_path.stderr + ash_path.stdout)
        self.assertIn("ok", ash_path.stdout)
        overlay = subprocess.run([str(NODE), str(WORKER.with_name("test_baritone_path_overlay.cjs"))], capture_output=True, text=True, timeout=5, cwd=str(WORKER.parent))
        self.assertEqual(overlay.returncode, 0, overlay.stderr + overlay.stdout)
        self.assertIn("ok", overlay.stdout)
        source = WORKER.read_text(encoding="utf-8")
        for operation in ('"attach"', '"observe"', '"move"', '"goto"', '"wood_to_table"', '"dig"', '"craft"', '"place"', '"chat"', '"stop_motion"', '"stop"'):
            self.assertIn(operation, source)
        for required_perception_surface in ('"observation.v3"', 'recent_chat', 'nearby_blocks', 'advancements', 'bot.on("chat"', 'autoReplyToPlayer', 'bot._client.on("advancements"'):
            self.assertIn(required_perception_surface, source)
        for forbidden in (".activateItem(", ".useOn(", "eval(", "exec("):
            self.assertNotIn(forbidden, source)
        self.assertGreaterEqual(source.count("bot.dig("), 2)
        self.assertIn("cursorHitsTarget", source)
        self.assertIn("blockAtCursor", source)
        self.assertIn("@miner-org/mineflayer-baritone", source)
        self.assertIn("ashGotoSucceeded", source)
        self.assertIn("ashArriveOk", source)
        self.assertIn("withinGotoRange", source)
        self.assertIn("blockHasExposedFace", source)
        navigate_source = source.split("async function navigate")[1].split("async function woodToTable")[0]
        self.assertIn("await gotoAsh", navigate_source)
        self.assertIn("ashArriveOk", navigate_source)
        self.assertIn('if (request.op === "goto")', source)
        self.assertIn("config.parkour = false", source)
        self.assertIn("config.allowSprinting = true", source)
        self.assertIn("mineflayer-auto-eat", source)
        self.assertIn("enableAutoEat", source)
        self.assertIn("prismarine-viewer", source)
        self.assertIn("VIEWER_FOV_DEG = 90", source)
        self.assertIn('VIEWER_HOST = "127.0.0.1"', source)
        self.assertIn("ensureBrowserViewer", source)
        self.assertIn("applyViewerListenLoopback", source)
        self.assertIn("applyViewerFov", source)
        self.assertIn("viewer_start_failed", source)
        self.assertIn("createAshPathOverlay", source)
        self.assertIn("pathOverlay.bind(bot)", source)
        self.assertIn("baritone_path_overlay.cjs", source)
        self.assertIn('http.listen(port, "127.0.0.1"', source)
        self.assertIn("console.log = () => {}", source)
        self.assertIn('if (request.op === "wood_to_table")', source)
        self.assertIn('if (request.op === "dig")', source)
        self.assertIn("bot.placeBlock(", source)
        self.assertIn("bot.chat(", source)
        self.assertIn("bot.setControlState(", source)


if __name__ == "__main__":
    unittest.main()
