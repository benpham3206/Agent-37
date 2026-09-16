from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.request
from pathlib import Path
from typing import Any, Mapping


class ModelError(RuntimeError):
    pass


class OpenAICompatible:
    def __init__(self) -> None:
        self.url = os.environ.get("PRIMECRAFT_MODEL_URL", "https://api.openai.com/v1/chat/completions")
        self.key = os.environ.get("PRIMECRAFT_MODEL_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.model = os.environ.get("PRIMECRAFT_MODEL", "gpt-4o-mini")

    def decide(self, prompt: str, image: str, state: Mapping[str, Any]) -> dict[str, Any]:
        if not self.key:
            raise ModelError("model_api_key_missing")
        image_url = image if image.startswith(("data:", "http://", "https://")) else self._file_image(image)
        content = [{"type": "text", "text": prompt + "\nStructured state:\n" + json.dumps(state, default=str)}]
        content.append({"type": "image_url", "image_url": {"url": image_url}})
        schema = {"type":"object","properties":{"kind":{"type":"string","enum":["look","move_to","mine","place","craft","interact","attack","use","stop"]},"yaw_deg":{"type":"number"},"pitch_deg":{"type":"number"},"x":{"type":"number"},"y":{"type":"number"},"z":{"type":"number"},"max_seconds":{"type":"integer","minimum":1,"maximum":120},"target":{"type":"string"},"item":{"type":"string"}},"required":["kind"]}
        body = {"model": self.model, "messages": [{"role": "user", "content": content}], "tools": [{"type": "function", "function": {"name": "act", "description": "Choose one bounded Minecraft action", "parameters": schema}}], "tool_choice": "auto"}
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode())
        try:
            args = result["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
            return json.loads(args)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ModelError("model_did_not_return_action") from exc

    @staticmethod
    def _file_image(path: str) -> str:
        data = base64.b64encode(Path(path).read_bytes()).decode()
        return "data:" + (mimetypes.guess_type(path)[0] or "image/png") + ";base64," + data
