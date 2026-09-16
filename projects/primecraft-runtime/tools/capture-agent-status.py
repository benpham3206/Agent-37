#!/usr/bin/env python3
"""Capture what a Primecraft Prime-Agent session says it is doing.

Tails session JSONL and writes an evidence log. The model should not spend
turns writing status chat; this script records assistant text, thinking titles,
and presence tool calls instead.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterator


THINK_TITLE = re.compile(r"\*\*([^*]{3,120})\*\*")
PRESENCE_ACTION = re.compile(
    r"presence_action\s*\(\s*(\{.*?\}|\([^)]*\))",
    re.DOTALL,
)
PRESENCE_CHAT = re.compile(
    r"send_presence_chat\s*\(\s*(['\"])(.*?)\1\s*\)",
    re.DOTALL,
)
KIND_IN_DICT = re.compile(r"['\"]kind['\"]\s*:\s*['\"](\w+)['\"]")
BLOCK_IN_DICT = re.compile(r"['\"]block['\"]\s*:\s*['\"]([^'\"]+)['\"]")
ITEM_IN_DICT = re.compile(r"['\"]item['\"]\s*:\s*['\"]([^'\"]+)['\"]")
DIRECTION_IN_DICT = re.compile(r"['\"]direction['\"]\s*:\s*['\"]([^'\"]+)['\"]")

DEFAULT_SESSION_DIRS = (
    Path(r"D:\Codex\2026-08-26\prime-agent\sessions"),
    Path.home() / ".prime" / "agent" / "sessions",
)
DEFAULT_EVIDENCE = Path(r"D:\Codex\2026-08-26\plea\work\evidence\primecraft-live\agent-status")


def _latest_session(session_dirs: list[Path]) -> Path | None:
    candidates: list[Path] = []
    for directory in session_dirs:
        if not directory.is_dir():
            continue
        candidates.extend(directory.glob("*.jsonl"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _iter_new_lines(path: Path, offset: int) -> tuple[list[str], int]:
    with path.open("r", encoding="utf-8") as handle:
        handle.seek(offset)
        chunk = handle.read()
        new_offset = handle.tell()
    if not chunk:
        return [], new_offset
    if offset > 0 and not chunk.startswith("\n") and "\n" in chunk:
        # Mid-line seek: drop the partial first line.
        chunk = chunk.split("\n", 1)[1]
    lines = [line for line in chunk.splitlines() if line.strip()]
    return lines, new_offset


def _tool_code(arguments: object) -> str:
    if not isinstance(arguments, dict):
        return ""
    code = arguments.get("code")
    return code if isinstance(code, str) else ""


def _summarize_action_snippet(snippet: str) -> str | None:
    kind_match = KIND_IN_DICT.search(snippet)
    if not kind_match:
        return None
    kind = kind_match.group(1)
    detail = None
    for pattern in (BLOCK_IN_DICT, ITEM_IN_DICT, DIRECTION_IN_DICT):
        match = pattern.search(snippet)
        if match:
            detail = match.group(1)
            break
    return f"action:{kind}" + (f" {detail}" if detail else "")


def extract_status_events(event: dict[str, Any]) -> list[dict[str, Any]]:
    message = event.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []

    events: list[dict[str, Any]] = []
    timestamp = event.get("timestamp") or message.get("timestamp")
    event_id = event.get("id")

    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type == "thinking":
            thinking = part.get("thinking")
            if not isinstance(thinking, str):
                continue
            for title in THINK_TITLE.findall(thinking):
                cleaned = " ".join(title.split())
                if cleaned.lower().startswith("planning") and "navigat" not in cleaned.lower():
                    # Skip pure planning noise; keep action-ish titles.
                    if not any(
                        word in cleaned.lower()
                        for word in ("navigat", "dig", "craft", "place", "move", "look", "chat", "wood", "stone", "action")
                    ):
                        continue
                events.append(
                    {
                        "source": "thinking_title",
                        "text": cleaned,
                        "event_id": event_id,
                        "timestamp": timestamp,
                    }
                )
        elif part_type == "text":
            text = part.get("text")
            if not isinstance(text, str):
                continue
            cleaned = " ".join(text.split())
            if len(cleaned) < 8:
                continue
            events.append(
                {
                    "source": "assistant_text",
                    "text": cleaned[:240],
                    "event_id": event_id,
                    "timestamp": timestamp,
                }
            )
        elif part_type == "toolCall" and part.get("name") == "ipython":
            code = _tool_code(part.get("arguments"))
            if not code:
                continue
            for match in PRESENCE_CHAT.finditer(code):
                events.append(
                    {
                        "source": "presence_chat",
                        "text": match.group(2)[:240],
                        "event_id": event_id,
                        "timestamp": timestamp,
                    }
                )
            for match in PRESENCE_ACTION.finditer(code):
                summary = _summarize_action_snippet(match.group(1))
                if summary:
                    events.append(
                        {
                            "source": "presence_action",
                            "text": summary,
                            "event_id": event_id,
                            "timestamp": timestamp,
                        }
                    )
            # Fallback when action dict spans lines oddly.
            if "presence_action" in code and not any(item["source"] == "presence_action" for item in events[-5:]):
                summary = _summarize_action_snippet(code)
                if summary:
                    events.append(
                        {
                            "source": "presence_action",
                            "text": summary,
                            "event_id": event_id,
                            "timestamp": timestamp,
                        }
                    )
    return events


def _write_latest(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        f"ts: {payload.get('timestamp')}",
        f"source: {payload.get('source')}",
        f"text: {payload.get('text')}",
        f"session: {payload.get('session')}",
        f"event_id: {payload.get('event_id')}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def follow_session(
    *,
    session_path: Path | None,
    session_dirs: list[Path],
    out_dir: Path,
    poll_s: float,
    once: bool,
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "status.jsonl"
    latest_path = out_dir / "latest-status.txt"
    meta_path = out_dir / "capture-meta.json"

    offset = 0
    seen: set[str] = set()
    emitted = 0
    current = session_path

    def _write_meta() -> None:
        meta_path.write_text(
            json.dumps(
                {
                    "session_path": str(current) if current else None,
                    "out_dir": str(out_dir),
                    "started": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    _write_meta()

    while True:
        newest = _latest_session(session_dirs)
        if newest is not None and (current is None or newest.resolve() != current.resolve()):
            # Prefer a newer session file (e.g. after Primecraft relaunches).
            if current is None or newest.stat().st_mtime >= current.stat().st_mtime:
                current = newest.resolve()
                offset = 0
                _write_meta()
                print(f"following:{current}", flush=True)

        if current is None or not current.is_file():
            if once:
                print("session_missing", file=sys.stderr)
                return 2
            time.sleep(poll_s)
            continue

        lines, offset = _iter_new_lines(current, offset)
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            for status in extract_status_events(event):
                dedupe_key = f"{status.get('event_id')}|{status['source']}|{status['text']}"
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                payload = {
                    **status,
                    "session": current.name,
                    "captured_at_ms": int(time.time() * 1000),
                }
                with jsonl_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
                _write_latest(latest_path, payload)
                emitted += 1
                print(f"[{payload['source']}] {payload['text']}", flush=True)

        if once:
            print(f"emitted={emitted}", flush=True)
            return 0
        time.sleep(poll_s)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, help="Session JSONL to follow")
    parser.add_argument(
        "--session-dir",
        action="append",
        type=Path,
        default=[],
        help="Directory to search for the newest session JSONL (repeatable)",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--poll-s", type=float, default=0.5)
    parser.add_argument("--once", action="store_true", help="Process current bytes and exit")
    args = parser.parse_args(argv)

    session_dirs = args.session_dir or list(DEFAULT_SESSION_DIRS)
    session_path = args.session.resolve() if args.session else None
    if session_path is None and args.once:
        newest = _latest_session(session_dirs)
        if newest is None:
            print("no_session_found", file=sys.stderr)
            return 2
        session_path = newest.resolve()
    return follow_session(
        session_path=session_path,
        session_dirs=session_dirs,
        out_dir=args.out_dir.resolve(),
        poll_s=max(0.1, float(args.poll_s)),
        once=bool(args.once),
    )


if __name__ == "__main__":
    raise SystemExit(main())
