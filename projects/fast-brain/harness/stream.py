import json, threading, time
from collections import deque
from urllib.request import Request, urlopen

class World:
    def __init__(self):
        self.data = {}
        self.events = deque(maxlen=200)
        self.situations = {}
        self.lock = threading.Lock()

    def update_keyframe(self, value):
        with self.lock:
            self.data = value.get("keyframe", value)

    def add(self, event):
        with self.lock:
            self.events.append(event)
            self._apply(event)

    def recent(self, n=20):
        with self.lock: return list(self.events)[-n:]

    def _apply(self, e):
        self.data.setdefault("entities", [])
        kind, field = e.get("kind"), e.get("field")
        if kind == "keyframe":
            self.data = e
        elif kind == "entity" and field in ("motion", "spawn"):
            pos = e.get("to") if field == "spawn" else e.get("pos")
            found = next((x for x in self.data["entities"] if x.get("id") == e.get("id")), None)
            if found: found.update({"position": pos or found.get("position"), "velocity": e.get("vel", found.get("velocity"))})
            else: self.data["entities"].append({"id": e.get("id"), "name": e.get("name"), "category": e.get("category"), "position": pos})
        elif kind == "entity" and field == "despawn":
            self.data["entities"] = [x for x in self.data["entities"] if x.get("id") != e.get("id")]

class Stream:
    def __init__(self, base_url="http://127.0.0.1:8876", ring_size=200):
        self.base = base_url.rstrip("/"); self.world = World(); self.world.events = deque(maxlen=ring_size)
        self._stop = threading.Event(); self._thread = None

    def get(self, path):
        with urlopen(self.base + path, timeout=5) as r: return json.loads(r.read().decode())

    def start(self):
        self.world.update_keyframe(self.get("/v1/keyframe"))
        self._thread = threading.Thread(target=self._read, daemon=True); self._thread.start(); return self

    def _read(self):
        while not self._stop.is_set():
            try:
                req = Request(self.base + "/v1/events", headers={"Accept": "text/event-stream"})
                with urlopen(req, timeout=30) as r:
                    for raw in r:
                        if self._stop.is_set(): return
                        line = raw.decode("utf-8", "replace").strip()
                        if line.startswith("data:"):
                            try: self.world.add(json.loads(line[5:].strip()))
                            except (ValueError, TypeError): pass
            except Exception:
                if not self._stop.wait(.25): continue

    def stop(self):
        self._stop.set()

    def observe(self):
        return self.get("/v1/observation").get("observation", {})

    def recent(self, n=20):
        with self.world.lock: return list(self.world.events)[-n:]
