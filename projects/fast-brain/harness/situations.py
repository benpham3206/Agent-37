import math

def _self(world): return world.data.get("self", {})
def _pos(s): return s.get("position", s.get("pos", {}))

def predicates(world):
    s, events = _self(world), list(world.events)
    vel = s.get("velocity", {}); y = vel.get("y", 0)
    falling = not s.get("on_ground", True) and y < -0.05
    if events:
        e = events[-1]
        if e.get("kind") == "self" and e.get("field") == "correction":
            falling = falling or (e.get("vel", {}).get("y", 0) < -0.05)
    entities = world.data.get("entities", [])
    hostile = any((x.get("category") == "mob" or x.get("name") in {"zombie","skeleton","creeper","spider"}) and x.get("distance", 999) < 8 for x in entities)
    projectile = any(e.get("kind") == "projectile" and (e.get("will_hit") or e.get("tti_ticks", 999) <= 7) for e in events[-20:])
    return {"falling": falling, "incoming_projectile": projectile, "hostile_near": hostile,
            "low_health": s.get("health", 20) < 8, "hungry": s.get("food", s.get("hunger", 20)) < 8,
            "on_fire": bool(s.get("on_fire", False)), "in_lava_adjacent": any(e.get("kind") == "block" and e.get("to") == "lava" for e in events[-20:]),
            "night": 13000 <= world.data.get("time_of_day", 0) or world.data.get("time_of_day", 0) < 1000}

class SituationDetector:
    def __init__(self, writer=None): self.active = {}; self.writer = writer
    def update(self, world):
        now = predicates(world); changes=[]
        for name, value in now.items():
            if self.active.get(name, False) != value:
                self.active[name] = value; e={"kind":"situation","name":name,"active":value,"t_ms":int(time_ms()),"tick":world.recent(1)[0].get("tick") if world.recent(1) else None}; changes.append(e)
                if self.writer: self.writer(e)
        return changes
def time_ms():
    import time; return time.time()*1000

