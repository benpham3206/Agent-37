from __future__ import annotations

import json
import os
import time
import uuid
import urllib.error
import urllib.request
from typing import Any, Mapping


class MinecraftError(RuntimeError):
    pass


class Minecraft:
    def __init__(self, url: str | None = None, timeout: float = 10):
        self.url = (url or os.environ.get("PRIMECRAFT_ADAPTER_URL", "http://127.0.0.1:18765")).rstrip("/")
        self.timeout = timeout
        self.episode_id = os.environ.get("PRIMECRAFT_EPISODE_ID")
        self.controller_id = os.environ.get("PRIMECRAFT_CONTROLLER_ID", "primecraft-actor")
        self.epoch = 0
        self.sequence = 0

    def request(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url + path, data=data, headers={"Accept": "application/json", "Content-Type": "application/json"}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode())
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise MinecraftError(f"adapter_request_failed:{path}") from exc
        if not isinstance(result, dict):
            raise MinecraftError("adapter_invalid_response")
        if result.get("error_code"):
            raise MinecraftError(str(result["error_code"]))
        return result

    def health(self) -> dict[str, Any]:
        return self.request("GET", "/healthz")

    def observe(self) -> dict[str, Any]:
        return self.request("GET", "/v1/observation")

    def action(self, action: Mapping[str, Any]) -> dict[str, Any]:
        if os.environ.get("PRIMECRAFT_CLAIM_CONTROLLER", "0") == "1":
            if not self.episode_id:
                self.episode_id = str(self.health().get("episode_id") or ("primecraft-" + uuid.uuid4().hex[:12]))
            if not self.epoch:
                claim = self.request("POST", "/v1/controller/claim", {"episode_id": self.episode_id, "controller_id": self.controller_id, "host": "127.0.0.1", "port": 25566, "version": "26.1.2", "auth": "offline", "username": "PrimeBot"})
                self.epoch = int(claim.get("epoch", 0))
            self.sequence += 1
            return self.request("POST", "/v1/action", {"episode_id": self.episode_id, "controller_id": self.controller_id, "epoch": self.epoch, "request_seq": self.sequence, "idempotency_key": str(uuid.uuid4()), "action": dict(action)})
        return self.request("POST", "/v1/action", {"action": dict(action)})

    def stop(self, reason: str = "actor_stop") -> dict[str, Any]:
        # /v1/stop disconnects the bot; actor cancellation uses action(kind=stop).
        return self.action({"kind": "stop"})
