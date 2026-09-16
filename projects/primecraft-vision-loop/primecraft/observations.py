from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Observation:
    id: str
    raw: Mapping[str, Any]
    image: str
    state: Mapping[str, Any]
    events: tuple[Mapping[str, Any], ...]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "Observation":
        if isinstance(payload.get("observation"), Mapping):
            payload = payload["observation"]
        image = next((payload.get(k) for k in ("image", "image_base64", "screenshot", "image_path") if payload.get(k)), None)
        if not isinstance(image, str):
            raise ValueError("observation_image_unavailable")
        state = payload.get("state", payload.get("player", {}))
        events = payload.get("recent_events", payload.get("events", []))
        return cls(str(payload.get("observation_id", payload.get("id", "unknown"))), payload, state if isinstance(state, Mapping) else {}, tuple(events) if isinstance(events, list) else ())
