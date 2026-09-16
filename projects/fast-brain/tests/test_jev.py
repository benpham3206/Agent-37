import json, math, os, tempfile, unittest
from collections import deque

from harness.jev import (JevActor, JevClient, QUESTIONS, decide, encode_state,
                         mock_transport, relative_frame)
from harness.stream import World


def answers(mode="engage", conf=0.9, movement="advance", attack=0.8, block=0.1,
            jump=0.1, sprint=0.6, danger=1.0, disengage=0.05,
            tactic_working=0.7, needs_slow_brain=0.05):
    return {
        "mode": {"type": "choice", "choice": mode, "confidence": conf,
                 "probabilities": {mode: conf}},
        "movement": {"type": "choice", "choice": movement, "confidence": conf,
                     "probabilities": {movement: conf}},
        "attack": {"type": "noul", "noul": attack},
        "block": {"type": "noul", "noul": block},
        "jump": {"type": "noul", "noul": jump},
        "sprint": {"type": "noul", "noul": sprint},
        "danger": {"type": "score", "score": danger},
        "tactic_working": {"type": "noul", "noul": tactic_working},
        "disengage": {"type": "noul", "noul": disengage},
        "needs_slow_brain": {"type": "noul", "noul": needs_slow_brain},
    }


def make_world():
    w = World()
    w.data = {
        "self": {"position": {"x": 0, "y": 64, "z": 0},
                 "velocity": {"x": 0, "y": 0, "z": 0},
                 "yaw": 0.0, "pitch": 0.0, "health": 20, "food": 18,
                 "on_ground": True, "in_water": False,
                 "held_item": "iron_sword",
                 "inventory": [{"name": "iron_sword", "count": 1},
                               {"name": "shield", "count": 1}]},
        "entities": [
            {"id": 7, "name": "zombie", "category": "mob",
             "position": {"x": 0, "y": 64, "z": -4},
             "velocity": {"x": 0, "y": 0, "z": 0}, "distance": 4.0},
            {"id": 9, "name": "skeleton", "category": "mob",
             "position": {"x": 10, "y": 64, "z": 0},
             "velocity": {"x": 0, "y": 0, "z": 0}, "distance": 10.0},
        ],
        "time_of_day": 6000,
    }
    w.events = deque(maxlen=200)
    return w


class TestRelativeFrame(unittest.TestCase):
    # Convention from bridge.mjs lookAngles: yaw = atan2(-dx, -dz); yaw 0
    # faces -Z and increasing yaw turns left, so right-hand is +X at yaw 0
    # and a right-side target has a negative bearing.
    def test_facing_target(self):
        f = relative_frame({"x": 0, "y": 64, "z": 0}, 0.0, {"x": 0, "y": 64, "z": -4})
        self.assertAlmostEqual(f["forward"], 4.0)
        self.assertAlmostEqual(f["right"], 0.0)
        self.assertAlmostEqual(f["bearing_deg"], 0.0)
        self.assertAlmostEqual(f["distance"], 4.0)

    def test_target_90_right(self):
        f = relative_frame({"x": 0, "y": 64, "z": 0}, 0.0, {"x": 4, "y": 64, "z": 0})
        self.assertAlmostEqual(f["forward"], 0.0, places=6)
        self.assertGreater(f["right"], 3.9)
        self.assertAlmostEqual(f["bearing_deg"], -90.0)


class TestEncodeState(unittest.TestCase):
    def test_state_fields(self):
        w = make_world()
        w.events.append({"kind": "damage", "amount": 2, "t_ms": 0})  # too old
        import time
        w.events.append({"kind": "damage", "amount": 3,
                         "t_ms": int(time.time() * 1000)})
        prev = {"tactic": {"movement": "advance"}, "distance_after": 6.0,
                "health_after": 20, "hit_connected": False, "latency_ms": 100}
        s = encode_state(w, 7, intent=None, previous=prev)
        t = s["target"]
        self.assertEqual(t["id"], 7)
        self.assertEqual(t["type"], "zombie")
        self.assertAlmostEqual(t["relative"]["forward"], 4.0)
        self.assertTrue(t["approaching"])  # 4.0 < previous 6.0
        self.assertEqual([x["type"] for x in s["other_threats"]], ["skeleton"])
        self.assertIn("situations", s)
        self.assertEqual(s["recent_events"]["damage_taken_last_2s"], 3)
        self.assertEqual(s["previous"]["tactic"], {"movement": "advance"})
        self.assertTrue(s["self"]["has_shield"])
        self.assertEqual(s["goal"], "defeat the zombie without dying")
        json.dumps(s)  # serializable


class TestDecide(unittest.TestCase):
    def test_engage_advance_attack(self):
        tactic, meta = decide(answers())
        self.assertEqual(tactic["movement"], "advance")
        self.assertTrue(tactic["attack"])
        self.assertFalse(meta["held"])

    def test_low_confidence_holds_previous(self):
        prev = {"movement": "strafe_left", "attack": False, "sprint": False,
                "jump": False, "block": False}
        tactic, meta = decide(answers(conf=0.1), prev)
        self.assertTrue(meta["held"])
        self.assertEqual(tactic, prev)

    def test_disengage_noul(self):
        tactic, meta = decide(answers(disengage=0.9))
        self.assertEqual(tactic["movement"], "disengage")
        self.assertEqual(meta["reason"], "disengage")
        self.assertFalse(tactic["attack"])

    def test_danger_score_disengage(self):
        tactic, _ = decide(answers(danger=3.4))
        self.assertEqual(tactic["movement"], "disengage")

    def test_recover_blocks_and_backs_off(self):
        tactic, _ = decide(answers(mode="recover"))
        self.assertEqual(tactic["movement"], "back_off")
        self.assertTrue(tactic["block"])

    def test_create_distance_overrides_advance(self):
        tactic, _ = decide(answers(mode="create_distance", movement="advance"))
        self.assertEqual(tactic["movement"], "back_off")


class TestClient(unittest.TestCase):
    def test_body_and_answers(self):
        seen = {}
        def fake(body):
            seen.update(body)
            return mock_transport(body)
        c = JevClient(transport=fake)
        out = c.ask({"state_id": 1}, QUESTIONS)
        self.assertEqual(seen["model"], "jev-latest")
        self.assertEqual(seen["state"], {"state_id": 1})
        types = {q["type"] for q in seen["questions"].values()}
        self.assertEqual(types, {"choice", "score", "noul"})
        self.assertIn("mode", out)

    def test_missing_key_raises(self):
        os.environ.pop("TYPESAFE_API_KEY", None)
        with self.assertRaises(RuntimeError):
            JevClient()


class FakeActor(JevActor):
    """JevActor with an in-memory fake bridge; no HTTP, no stream."""
    def __init__(self, **kw):
        self.posted, self.deleted = [], 0
        self.skill_started = 0
        super().__init__(**kw)
        w = make_world()
        self.stream = type("FakeStream", (), {})()
        self.stream.world = w
        self.stream._thread = True  # pretend started
        self.stream.base = "fake://"

    def _get(self, path):
        return {"active": True}

    def _post(self, path, payload, method="POST"):
        if method == "DELETE":
            self.deleted += 1
            return {"cancelled": True}
        if path == "/v1/skill":
            self.skill_started += 1
            return {"started": True}
        if path == "/v1/tactic":
            if getattr(self, "force_stale", False):
                self.force_stale = False
                return {"error": "stale_tactic", "latest_seq": 40}
            self.posted.append(payload)
            return {"accepted": True, "seq": payload["seq"], "deadline_ms": 0}
        return {}


class TestActorLoop(unittest.TestCase):
    def _actor(self, transport=None):
        with tempfile.TemporaryDirectory() as d:
            pass
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl")
        tmp.close()
        client = JevClient(transport=transport or mock_transport)
        a = FakeActor(client=client, target_id=7, hz=40.0, log_path=tmp.name)
        a.stream.start = lambda: a.stream  # no-op
        self.addCleanup(lambda: os.path.exists(tmp.name) and os.unlink(tmp.name))
        return a

    def test_posts_increasing_seq_and_deletes_on_exit(self):
        a = self._actor()
        a.run(seconds=0.4)
        seqs = [p["seq"] for p in a.posted]
        self.assertEqual(seqs, sorted(seqs))
        self.assertGreaterEqual(len(seqs), 2)
        self.assertEqual(a.deleted, 1)

    def test_stale_latency_skips_post(self):
        def slow(body):
            time_sleep = __import__("time").sleep
            time_sleep(0.06)  # > 1.5 * (1000/40) = 37.5ms
            return mock_transport(body)
        a = self._actor(transport=slow)
        a.run(seconds=0.3)
        self.assertEqual(len(a.posted), 0)

    def test_stale_tactic_resync(self):
        a = self._actor()
        a.force_stale = True
        a.run(seconds=0.3)
        self.assertTrue(any(p["seq"] == 41 for p in a.posted))

    def test_escalate_called(self):
        def high(body):
            r = mock_transport(body)
            r["answers"]["needs_slow_brain"]["noul"] = 0.9
            return r
        calls = []
        a = self._actor(transport=high)
        a.escalate = lambda s, m: calls.append(m)
        a.run(seconds=0.3)
        self.assertTrue(calls)


class TestRemembered(unittest.TestCase):
    def test_waypoint_formatting(self):
        w = make_world()
        remembered = [{"label": "cave_entrance", "position": {"x": 0, "y": 64, "z": -10}}]
        st = encode_state(w, 7, remembered=remembered)
        r = st["remembered"][0]
        self.assertEqual(r["label"], "cave_entrance")
        self.assertEqual(r["last_seen"], "waypoint")
        self.assertEqual(r["distance"], "10.0 (medium)")
        self.assertIn("(ahead)", r["bearing"])
        self.assertEqual(r["status"], "waypoint")

    def test_gone_entity_out_of_view(self):
        w = make_world()
        a = JevActor.__new__(JevActor)
        a.remembered, a.seen = [], {}
        now = 1_000_000_000
        a._remembered_list(w, now)  # both entities seen now
        w.data["entities"] = w.data["entities"][:1]  # skeleton leaves view
        rem = a._remembered_list(w, now + 3000)
        self.assertEqual(len(rem), 1)
        self.assertEqual(rem[0]["label"], "skeleton#9")
        self.assertEqual(rem[0]["status"], "out of view")
        self.assertEqual(rem[0]["last_seen_ms"], now)

    def test_measurement_context_in_state(self):
        st = encode_state(make_world(), 7)
        mc = st["measurement_context"]
        self.assertIn("block", mc["distance_unit"])
        self.assertEqual(mc["relative_bearing_degrees"]["-90"], "directly right")


class TestEnvFileKey(unittest.TestCase):
    def test_env_file_fallback(self):
        from harness.jev import _env_file_key
        import pathlib
        proj = pathlib.Path(__file__).resolve().parents[1]
        env = proj / ".env"
        existed = env.exists()
        old = env.read_text() if existed else None
        env.write_text("TYPESAFE_API_KEY=test-key-123\n")
        try:
            self.assertEqual(_env_file_key("TYPESAFE_API_KEY"), "test-key-123")
        finally:
            if existed: env.write_text(old)
            else: env.unlink()


if __name__ == "__main__":
    unittest.main()
