"""Tiny JSONL memory store for observations, attempts, and lessons."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4


class Memory:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def remember(self, kind: str, value: Any, *, tags: Iterable[str] = ()) -> dict[str, Any]:
        record = {"id": str(uuid4()), "timestamp": datetime.now(timezone.utc).isoformat(), "kind": kind, "value": value, "tags": list(tags)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def recall(self, query: str = "", *, kind: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        if limit < 1:
            raise ValueError("limit must be positive")
        query = query.casefold()
        found: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if kind and record.get("kind") != kind:
                continue
            if query and query not in json.dumps(record, ensure_ascii=False).casefold():
                continue
            found.append(record)
        return found[-limit:]
