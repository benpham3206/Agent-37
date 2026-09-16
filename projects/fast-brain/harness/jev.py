"""Jev (TypeSafe System One) tactical fast brain.

Jev answers judgments only; all geometry, aiming, and timing stay in code.
The loop encodes an ego-relative state, fans out QUESTIONS against one
state, reduces the answers to a bounded tactic, and posts it to the
bridge's `tactical` reflex skill with a TTL. If Jev is slow or absent the
tactic expires and the motor holds — fail closed.
"""
import json, math, os, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from .stream import Stream
from . import situations

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MOVEMENTS = ("advance", "back_off", "strafe_left", "strafe_right", "hold", "disengage")

QUESTIONS = {
    "mode": {"type": "choice",
             "instructions": "Given the goal, strategy and current state, which tactical mode is most appropriate right now?",
             "criteria": {"engage": "Close in and fight the target",
                          "hold": "Keep current spacing; wait for an opening or for the target to commit",
                          "create_distance": "Back away or kite to open space between us and the target",
                          "disengage": "Break off this fight entirely and get away",
                          "recover": "Prioritize survival: block, retreat, eat; the fight is secondary"}},
    "movement": {"type": "choice",
                 "instructions": "Which movement should the bot make this instant, relative to facing the target?",
                 "criteria": {"advance": "Move toward the target",
                              "back_off": "Move away from the target while still facing it",
                              "strafe_left": "Sidestep left around the target",
                              "strafe_right": "Sidestep right around the target",
                              "hold": "Do not move"}},
    "attack": {"type": "noul", "instructions": "The bot should swing its weapon at the target right now (the target is close enough to hit or about to be)."},
    "block": {"type": "noul", "instructions": "The bot should raise its shield right now (an attack or projectile is imminent)."},
    "jump": {"type": "noul", "instructions": "Jumping right now would help (dodging, closing gaps, or getting over an obstacle)."},
    "sprint": {"type": "noul", "instructions": "Sprinting is appropriate for the current movement."},
    "danger": {"type": "score", "instructions": "How dangerous is the bot's situation right now?",
               "criteria": ["No meaningful immediate threat",
                            "Manageable threat with plenty of health and space",
                            "Could take significant damage in the next few seconds",
                            "Immediate survival danger; health or position is critical",
                            "Likely death within seconds unless behavior changes now"]},
    "tactic_working": {"type": "noul", "instructions": "The previous tactic is producing the intended result (progress toward the goal without taking unnecessary damage)."},
    "disengage": {"type": "noul", "instructions": "The bot should stop fighting this target and retreat."},
    "needs_slow_brain": {"type": "noul", "instructions": "This situation is unusual enough that a deliberate planner should reconsider the goal or strategy."},
}

DEFAULT_THRESHOLDS = {"min_confidence": 0.3, "attack": 0.5, "block": 0.6,
                      "jump": 0.6, "sprint": 0.5, "disengage": 0.7,
                      "danger_disengage": 3.0}


def _wrap(a):
    while a > math.pi: a -= 2 * math.pi
    while a < -math.pi: a += 2 * math.pi
    return a


def relative_frame(self_pos, yaw, other_pos):
    """Ego-relative position of other_pos.

    Convention from bridge.mjs lookAngles: the yaw that faces a target is
    atan2(-dx, -dz), so bearing = wrap(desired_yaw - yaw). A target dead
    ahead has forward==distance, right==0, bearing==0; positive `right`
    is the bot's right-hand side (bearing < 0, since yaw grows leftward).
    """
    dx = other_pos.get("x", 0) - self_pos.get("x", 0)
    dy = other_pos.get("y", 0) - self_pos.get("y", 0)
    dz = other_pos.get("z", 0) - self_pos.get("z", 0)
    horiz = math.hypot(dx, dz)
    bearing = _wrap(math.atan2(-dx, -dz) - yaw)
    return {"forward": round(math.cos(bearing) * horiz, 2),
            "right": round(-math.sin(bearing) * horiz, 2),
            "up": round(dy, 2),
            "distance": round(math.sqrt(dx * dx + dy * dy + dz * dz), 2),
            "bearing_deg": round(math.degrees(bearing), 1)}


def _default_intent(target_name):
    return {"goal": f"defeat the {target_name} without dying",
            "strategy": "keep the shield ready, avoid fighting more than one mob at once, retreat when health is low"}


def encode_state(world, target_id, intent=None, previous=None):
    """Compact ego-relative state for one Jev fan-out."""
    data = world.data if hasattr(world, "data") else world
    events = list(world.events) if hasattr(world, "events") else []
    s = data.get("self", {})
    spos = s.get("position", {})
    yaw = s.get("yaw", 0) or 0
    entities = data.get("entities", [])
    target = next((e for e in entities if e.get("id") == target_id), None)
    tname = (target or {}).get("name", "target")
    it = intent or _default_intent(tname)
    now_ms = int(time.time() * 1000)
    rel = relative_frame(spos, yaw, target["position"]) if target and target.get("position") else None
    dist = rel["distance"] if rel else None
    prev_dist = previous.get("distance_after") if previous else None
    tvel = (target or {}).get("velocity") or {}
    v_toward = 0.0
    if target and target.get("position") and dist:
        toward = {"x": (spos.get("x", 0) - target["position"]["x"]) / dist,
                  "y": (spos.get("y", 0) - target["position"]["y"]) / dist,
                  "z": (spos.get("z", 0) - target["position"]["z"]) / dist}
        v_toward = sum(tvel.get(k, 0) * toward[k] for k in ("x", "y", "z"))
    threats = []
    for e in entities:
        if e.get("id") == target_id: continue
        if e.get("category") != "mob" and e.get("name") not in ("zombie", "skeleton", "creeper", "spider"): continue
        epos = e.get("position")
        if not epos: continue
        f = relative_frame(spos, yaw, epos)
        if f["distance"] <= 12:
            threats.append({"type": e.get("name"), "distance": f["distance"], "bearing_deg": f["bearing_deg"]})
    threats = sorted(threats, key=lambda t: t["distance"])[:5]
    try:
        sits = [k for k, v in situations.predicates(world).items() if v]
    except Exception:
        sits = []
    recent = [e for e in events if now_ms - (e.get("t_ms") or 0) <= 2000]
    inv = s.get("inventory") or data.get("inventory") or []
    state = {
        "state_id": int(now_ms),
        "t_ms": now_ms,
        "goal": it.get("goal"), "strategy": it.get("strategy"),
        "self": {"health": s.get("health"), "food": s.get("food", s.get("hunger")),
                 "on_ground": s.get("on_ground"), "in_water": s.get("in_water"),
                 "held_item": s.get("held_item"),
                 "has_shield": any("shield" in str(i.get("name", "")) for i in inv),
                 "y_velocity": round((s.get("velocity") or {}).get("y", 0), 2)},
        "target": {"id": target_id, "type": tname,
                   "distance": dist,
                   "relative": rel and {"forward": rel["forward"], "right": rel["right"], "up": rel["up"]},
                   "bearing_deg": rel and rel["bearing_deg"],
                   "approaching": bool(prev_dist is not None and dist is not None and dist < prev_dist),
                   "velocity_toward_self": round(v_toward, 2),
                   "line_of_sight": None},
        "other_threats": threats,
        "situations": sits,
        "recent_events": {
            "damage_taken_last_2s": round(sum(e.get("amount", 0) for e in recent if e.get("kind") == "damage"), 2),
            "hits_dealt_last_2s": sum(1 for e in recent if e.get("kind") == "swing" and e.get("target") == target_id),
            "projectiles_incoming": sum(1 for e in recent if e.get("kind") == "projectile" and e.get("will_hit")),
            "block_transitions": [e.get("to") for e in recent if e.get("kind") == "block" and e.get("to")][-3:],
        },
        "previous": {"tactic": previous.get("tactic") if previous else None,
                     "distance_before": previous.get("distance_before") if previous else None,
                     "distance_after": previous.get("distance_after") if previous else None,
                     "health_before": previous.get("health_before") if previous else None,
                     "health_after": previous.get("health_after") if previous else None,
                     "hit_connected": bool(previous.get("hit_connected")) if previous else False,
                     "latency_ms": previous.get("latency_ms") if previous else None},
    }
    return state


def decide(answers, previous_tactic=None, thresholds=None):
    """answers -> (tactic, meta). Pure; all geometry stays in code."""
    th = dict(DEFAULT_THRESHOLDS, **(thresholds or {}))
    mode = answers["mode"]
    conf = mode.get("confidence", 0)
    meta = {"mode": mode.get("choice"), "confidence": conf,
            "danger": answers["danger"].get("score"),
            "tactic_working": answers["tactic_working"].get("noul"),
            "needs_slow_brain": answers["needs_slow_brain"].get("noul"),
            "held": False, "reason": None,
            "probabilities": {"mode": mode.get("probabilities"),
                              "movement": answers["movement"].get("probabilities")}}
    if (answers["disengage"].get("noul", 0) >= th["disengage"]
            or answers["danger"].get("score", 0) >= th["danger_disengage"]
            or mode.get("choice") == "disengage"):
        meta["reason"] = "disengage"
        return {"movement": "disengage", "attack": False, "sprint": True,
                "jump": True, "block": False}, meta
    if conf < th["min_confidence"] and previous_tactic:
        meta["held"] = True
        meta["reason"] = "low_confidence_hold"
        return dict(previous_tactic), meta
    movement = answers["movement"].get("choice", "hold")
    if movement not in MOVEMENTS: movement = "hold"
    block = answers["block"].get("noul", 0) >= th["block"]
    if mode.get("choice") == "recover":
        movement, block = "back_off", True
    if mode.get("choice") == "create_distance" and movement == "advance":
        movement = "back_off"
    tactic = {"movement": movement,
              "attack": bool(answers["attack"].get("noul", 0) >= th["attack"] and mode.get("choice") in ("engage", "hold")),
              "sprint": bool(answers["sprint"].get("noul", 0) >= th["sprint"]),
              "jump": bool(answers["jump"].get("noul", 0) >= th["jump"]),
              "block": block}
    return tactic, meta


def mock_transport(body):
    """Deterministic offline Jev stand-in: engage/advance far, attack close."""
    state = body.get("state") or {}
    dist = ((state.get("target") or {}).get("distance")) or 99
    close = dist <= 3.5
    def choice(name, pick, rest):
        probs = {o: (0.9 if o == pick else 0.1 / max(1, len(rest))) for o in [pick, *rest]}
        return {"type": "choice", "choice": pick, "probabilities": probs, "confidence": 0.9}
    return {"model": body.get("model"), "usage": {"mock": True}, "answers": {
        "mode": choice("mode", "engage", ["hold", "create_distance", "disengage", "recover"]),
        "movement": choice("movement", "hold" if close else "advance", ["advance", "back_off", "strafe_left", "strafe_right"]),
        "attack": {"type": "noul", "noul": 0.9 if close else 0.1},
        "block": {"type": "noul", "noul": 0.1},
        "jump": {"type": "noul", "noul": 0.1},
        "sprint": {"type": "noul", "noul": 0.6 if not close else 0.2},
        "danger": {"type": "score", "score": 1.0, "legend": {}, "confidence": 0.9},
        "tactic_working": {"type": "noul", "noul": 0.7},
        "disengage": {"type": "noul", "noul": 0.05},
        "needs_slow_brain": {"type": "noul", "noul": 0.05}}}


class JevClient:
    def __init__(self, api_key=None, model=None, endpoint=ENDPOINT, timeout_s=0.45, transport=None):
        self.api_key = api_key if api_key is not None else os.getenv("TYPESAFE_API_KEY")
        self.model = model or os.getenv("TYPESAFE_MODEL", "jev-latest")
        self.endpoint = endpoint
        self.timeout_s = timeout_s
        self.transport = transport
        if self.transport is None and not self.api_key:
            raise RuntimeError("TYPESAFE_API_KEY missing")

    def ask(self, state, questions):
        body = {"state": state, "model": self.model, "questions": questions}
        if self.transport:
            return self.transport(body)["answers"]
        req = Request(self.endpoint, data=json.dumps(body).encode(),
                      headers={"Content-Type": "application/json",
                               "Authorization": f"Bearer {self.api_key}"}, method="POST")
        with urlopen(req, timeout=self.timeout_s) as r:
            return json.loads(r.read().decode())["answers"]


class JevActor:
    def __init__(self, stream=None, client=None, target_name="zombie",
                 target_id=None, intent=None, hz=8.0, ttl_ms=600,
                 log_path="harness.jsonl", escalate=None):
        self.stream = stream or Stream(os.getenv("FAST_BRAIN_URL", "http://127.0.0.1:8876"))
        self.client = client
        self.target_name, self.target_id = target_name, target_id
        self.intent = intent
        self.hz, self.ttl_ms = hz, ttl_ms
        self.log_path = log_path
        self.escalate = escalate or self._log_escalation
        self.seq = 0
        self.previous = None
        self.last_tactic = None

    def _get(self, path):
        with urlopen(self.stream.base + path, timeout=5) as r:
            return json.loads(r.read().decode())

    def _post(self, path, payload, method="POST"):
        req = Request(self.stream.base + path, data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"}, method=method)
        try:
            with urlopen(req, timeout=8) as r:
                return json.loads(r.read().decode())
        except HTTPError as e:
            try: return json.loads(e.read().decode()) | {"_status": e.code}
            except Exception: return {"error": f"http_{e.code}", "_status": e.code}

    def _log_escalation(self, state, meta):
        self._log({"kind": "escalation", "state_id": state.get("state_id"), "meta": meta})

    def _log(self, row):
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def _pick_target(self):
        if self.target_id is not None:
            return self.target_id
        ents = self.stream.world.data.get("entities", [])
        matches = [e for e in ents if self.target_name in str(e.get("name", ""))]
        if not matches:
            try:
                for t in self._get("/v1/targets").get("targets", []):
                    if t.get("kind") == "entity" and self.target_name in str(t.get("name", "")):
                        matches.append({"id": t.get("id"), "distance": t.get("distance", 999)})
            except Exception:
                pass
        if not matches:
            return None
        return min(matches, key=lambda e: e.get("distance", 999) if e.get("distance") is not None else 999).get("id")

    def _start_tactical(self):
        res = self._post("/v1/skill", {"name": "tactical", "args": {"entity_id": self.target_id}})
        if res.get("error") == "skill_busy":
            self._post("/v1/skill", {}, method="DELETE")
            res = self._post("/v1/skill", {"name": "tactical", "args": {"entity_id": self.target_id}})
        return res

    def run(self, seconds=60):
        client = self.client or JevClient()
        if self.stream._thread is None:
            self.stream.start()
        self.target_id = self._pick_target()
        if self.target_id is None:
            print(json.dumps({"error": "no_target", "target_name": self.target_name}))
            return
        start_res = self._start_tactical()
        if start_res.get("error") and not start_res.get("started"):
            print(json.dumps({"error": "skill_start_failed", "detail": start_res}))
            return
        period = 1.0 / self.hz
        lat_ms_budget = 1.5 * (1000 / self.hz)
        turns = posted = held = stale_n = 0
        latencies = []
        deadline = time.time() + seconds
        try:
            while time.time() < deadline:
                t0 = time.perf_counter()
                turns += 1
                world = self.stream.world
                s_health = (world.data.get("self") or {}).get("health")
                if s_health is not None and s_health <= 0:
                    break
                dist_now = None
                tgt = next((e for e in world.data.get("entities", []) if e.get("id") == self.target_id), None)
                state = encode_state(world, self.target_id, self.intent, self.previous)
                dist_now = state["target"]["distance"]
                if tgt is None and self.previous is not None:
                    break  # target despawned
                try:
                    answers = client.ask(state, QUESTIONS)
                except Exception as exc:
                    self._log({"kind": "jev", "state_id": state["state_id"], "error": str(exc)})
                    time.sleep(period)
                    continue
                latency = (time.perf_counter() - t0) * 1000
                latencies.append(latency)
                stale = latency > lat_ms_budget
                tactic, meta = decide(answers, self.last_tactic)
                row = {"kind": "jev", "state_id": state["state_id"],
                       "latency_ms": round(latency, 1), "stale": stale,
                       "tactic": tactic, "mode": meta["mode"],
                       "confidence": meta["confidence"], "danger": meta["danger"],
                       "tactic_working": meta["tactic_working"],
                       "needs_slow_brain": meta["needs_slow_brain"],
                       "usage": None}
                if meta.get("needs_slow_brain") is not None and meta["needs_slow_brain"] >= 0.8:
                    self.escalate(state, meta)
                if stale:
                    stale_n += 1
                    self._log(row)
                else:
                    self.seq += 1
                    res = self._post("/v1/tactic", {"seq": self.seq, "ttl_ms": self.ttl_ms,
                                                    **tactic,
                                                    "meta": {"state_id": state["state_id"],
                                                             "mode": meta["mode"],
                                                             "danger": meta["danger"]}})
                    if res.get("error") == "stale_tactic":
                        self.seq = res.get("latest_seq", self.seq)
                        self.seq += 1
                        res = self._post("/v1/tactic", {"seq": self.seq, "ttl_ms": self.ttl_ms,
                                                        **tactic,
                                                        "meta": {"state_id": state["state_id"],
                                                                 "mode": meta["mode"],
                                                                 "danger": meta["danger"]}})
                    if res.get("accepted"):
                        posted += 1
                        if meta.get("held"): held += 1
                        self.last_tactic = tactic
                        self.previous = {"tactic": tactic,
                                         "distance_before": self.previous and self.previous.get("distance_after"),
                                         "distance_after": dist_now,
                                         "health_before": self.previous and self.previous.get("health_after"),
                                         "health_after": s_health,
                                         "hit_connected": state["recent_events"]["hits_dealt_last_2s"] > 0,
                                         "latency_ms": round(latency, 1)}
                    else:
                        row["post_error"] = res
                    self._log(row)
                elapsed = time.perf_counter() - t0
                if elapsed < period:
                    time.sleep(period - elapsed)
        finally:
            self._post("/v1/skill", {}, method="DELETE")
        latencies.sort()
        mean = sum(latencies) / len(latencies) if latencies else None
        p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else None
        tgt_alive = any(e.get("id") == self.target_id for e in self.stream.world.data.get("entities", []))
        print(json.dumps({"turns": turns, "posted": posted, "held": held, "stale": stale_n,
                          "latency_ms": {"mean": round(mean, 1) if mean else None,
                                         "p95": round(p95, 1) if p95 else None},
                          "final_health": s_health, "target_alive": tgt_alive,
                          "log": self.log_path}))
