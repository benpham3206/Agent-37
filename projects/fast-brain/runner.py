"""fast-brain runner: pixels -> ROCKET-2 -> keys against the Node bridge.

Run with: .venv\\Scripts\\python.exe runner.py [--calibrate] [--bridge URL]
"""
from __future__ import annotations

import argparse
import io
import json
import math
import sys
import threading
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vendor.rocket_model import CrossViewRocket  # noqa: E402
from vendor.action_mapping import CameraHierarchicalMapping  # noqa: E402
from vendor.actions import ActionTransformer  # noqa: E402

BASE = Path(__file__).resolve().parent
MODEL_DIR = BASE / "models" / "rocket2-1x"
LOGS = BASE / "logs"

SEGMENT_MAPPING = {"Hunt": 0, "Use": 3, "Mine": 2, "Interact": 3, "Craft": 4, "Switch": 5, "Approach": 6, "None": -1}

PREV_KEYS = ["attack", "use", "inventory", "forward", "back", "left", "right",
             "sneak", "sprint", "jump", "drop"] + [f"hotbar.{i}" for i in range(1, 10)]


def zero_prev_action():
    prev = {k: np.array(0) for k in PREV_KEYS}
    prev["camera"] = np.array([0.0, 0.0], dtype=np.float32)
    return prev


# Camera sign conventions, measured by --calibrate on 2026-09-12.
# Env camera order is [camera_x (mouse dx), camera_y (mouse dy)] per
# CameraHierarchicalMapping.CAMERA_IDX_TO_FACTORED (index 0 = camera_x).
# prismarine-physics: yaw=0 looks -Z (north), increasing yaw turns LEFT
# (lookX = -sin(yaw)), and pitch positive = up (lookY = sin(pitch)).
# VPT: +dx = turn right, +dy = look down. Hence both signs are negative.
YAW_SIGN = -1.0    # env dx (+turn right) -> mineflayer yaw_delta negative
PITCH_SIGN = -1.0  # env dy (+look down)  -> mineflayer pitch_delta negative


def env_to_bridge_action(env):
    action = {
        "forward": bool(env["forward"]), "back": bool(env["back"]),
        "left": bool(env["left"]), "right": bool(env["right"]),
        "jump": bool(env["jump"]), "sprint": bool(env["sprint"]),
        "sneak": bool(env["sneak"]), "attack": bool(env["attack"]),
        "use": bool(env["use"]),
        "hotbar": None,
        "yaw_delta": YAW_SIGN * math.radians(float(env["camera"][0])),
        "pitch_delta": PITCH_SIGN * math.radians(float(env["camera"][1])),
    }
    for i in range(1, 10):
        if env.get(f"hotbar.{i}"):
            action["hotbar"] = i - 1
            break
    return action


def http_json(url, method="GET", body=None, timeout=5):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.status, json.loads(res.read() or b"{}")


def fetch_frame(bridge):
    req = urllib.request.Request(f"{bridge}/v1/frame")
    with urllib.request.urlopen(req, timeout=5) as res:
        jpeg = res.read()
        frame_id = int(res.headers.get("x-frame-id", "0"))
        captured = int(res.headers.get("x-captured-at-ms", "0"))
    bgr = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return frame_id, captured, rgb


class Runner:
    def __init__(self, bridge, device="cuda"):
        self.bridge = bridge.rstrip("/")
        self.device = device
        self.seq = 0
        self.goal = None  # {"interaction": str, "bbox": [x0,y0,x1,y1], "obj_id": int, "image": 224, "mask": 224}
        self.state = None
        self.prev_env_action = zero_prev_action()
        self.last_frame_id = -1
        self.step_times = []
        self.e2e = []
        self.lock = threading.Lock()
        self.policy = None
        self.mapper = CameraHierarchicalMapping(n_camera_bins=11)
        self.transformer = ActionTransformer(camera_maxval=10, camera_binsize=2,
                                             camera_quantization_scheme="mu_law", camera_mu=10)
        self.stop_flag = False

    def load_policy(self):
        print(f"[runner] loading ROCKET-2 from {MODEL_DIR}")
        t0 = time.time()
        self.policy = CrossViewRocket.from_pretrained(str(MODEL_DIR)).to(self.device).eval()
        print(f"[runner] policy loaded in {time.time()-t0:.1f}s on {self.device}")

    def set_goal(self, interaction, bbox):
        frame_id, captured, rgb = fetch_frame(self.bridge)
        img224 = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_LINEAR)
        h, w = rgb.shape[:2]
        x0, y0, x1, y1 = [float(v) for v in bbox]
        mask = np.zeros((h, w), np.uint8)
        mask[int(y0):int(y1) + 1, int(x0):int(x1) + 1] = 1
        mask224 = cv2.resize(mask, (224, 224), interpolation=cv2.INTER_NEAREST)
        with self.lock:
            self.goal = {"interaction": interaction, "bbox": [x0, y0, x1, y1],
                         "obj_id": SEGMENT_MAPPING.get(interaction, -1),
                         "image": img224, "mask": mask224, "frame_id": frame_id}
            self.state = self.policy.initial_state()
            self.prev_env_action = zero_prev_action()
        print(f"[runner] goal set: {interaction} bbox={bbox} frame={frame_id}")
        return {"ok": True, "frame_id": frame_id}

    def decode_action(self, action):
        factored = self.mapper.to_factored({
            "buttons": action["buttons"].cpu().numpy().reshape(1, 1),
            "camera": action["camera"].cpu().numpy().reshape(1, 1),
        })
        env = self.transformer.policy2env(factored)
        env = {k: (v[0] if isinstance(v, np.ndarray) and v.ndim >= 1 else v) for k, v in env.items()}
        return env

    def step_once(self):
        with self.lock:
            goal = self.goal
        if goal is None:
            return None
        t_recv = time.time() * 1000
        frame_id, captured, rgb = fetch_frame(self.bridge)
        if frame_id == self.last_frame_id:
            return "same_frame"
        self.last_frame_id = frame_id
        img224 = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_LINEAR)
        obs = {
            "image": img224,
            "env_prev_action": self.prev_env_action,
            "cross_view": {
                "cross_view_image": goal["image"],
                "cross_view_obj_id": torch.tensor(goal["obj_id"]),
                "cross_view_obj_mask": torch.tensor(goal["mask"], dtype=torch.uint8),
            },
        }
        t0 = time.time() * 1000
        with self.lock:
            action, self.state = self.policy.get_action(obs, self.state, input_shape="*")
        t_infer = time.time() * 1000
        env = self.decode_action(action)
        self.prev_env_action = {k: np.array(env[k]) if k != "camera" else np.asarray(env["camera"], dtype=np.float32)
                                for k in PREV_KEYS + ["camera"]}
        self.seq += 1
        ttl = max(150, int(3 * max(10.0, np.mean(self.step_times[-50:]) if self.step_times else 100)))
        try:
            http_json(f"{self.bridge}/v1/action", "POST",
                      {"seq": self.seq, "ttl_ms": ttl, "action": env_to_bridge_action(env)})
        except urllib.error.HTTPError as e:
            if e.code != 409:
                raise
            return "rejected"
        t_ack = time.time() * 1000
        self.step_times.append(t_infer - t0)
        self.e2e.append(t_ack - captured if captured else 0)
        return {"frame_id": frame_id, "infer_ms": t_infer - t0, "e2e_ms": t_ack - captured,
                "env": {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in env.items()}}

    def run(self, logpath):
        last_report = time.time()
        n = 0
        with open(logpath, "a", encoding="utf-8") as log:
            while not self.stop_flag:
                try:
                    result = self.step_once()
                except Exception as e:
                    print(f"[runner] step error: {e}")
                    time.sleep(0.2)
                    continue
                if result is None:
                    time.sleep(0.1)
                    continue
                if result == "same_frame":
                    time.sleep(0.005)
                    continue
                if result == "rejected":
                    time.sleep(0.1)
                    continue
                n += 1
                log.write(json.dumps({"n": n, "t": time.time(), **result}) + "\n")
                log.flush()
                # respawn check every ~1s
                if n % 20 == 0:
                    try:
                        _, obs_wrap = http_json(f"{self.bridge}/v1/observation")
                        if obs_wrap.get("observation", {}).get("respawned"):
                            with self.lock:
                                self.state = self.policy.initial_state()
                                self.prev_env_action = zero_prev_action()
                            print("[runner] respawned -> recurrent state reset")
                    except Exception:
                        pass
                if n % 100 == 0 or time.time() - last_report > 30:
                    last_report = time.time()
                    if self.step_times:
                        st = np.array(self.step_times[-200:])
                        ee = np.array(self.e2e[-200:])
                        print(f"[runner] n={n} infer p50={np.percentile(st,50):.0f}ms p95={np.percentile(st,95):.0f}ms "
                              f"e2e p50={np.percentile(ee,50):.0f}ms p95={np.percentile(ee,95):.0f}ms "
                              f"gpu_mem={torch.cuda.max_memory_allocated()/1e9:.2f}GB")
        print("[runner] stopped")

    # ---- HTTP API on 8877 ----
    def make_handler(self):
        runner = self

        class Handler(BaseHTTPRequestHandler):
            def _send(self, status, value):
                body = json.dumps(value, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else str(o)).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("cache-control", "no-store")
                self.send_header("access-control-allow-origin", "*")
                self.send_header("access-control-allow-methods", "GET,POST,DELETE,OPTIONS")
                self.send_header("access-control-allow-headers", "content-type")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self):
                self._send(204, {})

            def do_GET(self):
                if self.path == "/goal":
                    g = runner.goal
                    self._send(200, {"goal": None if g is None else {"interaction": g["interaction"], "bbox": g["bbox"], "frame_id": g["frame_id"]}})
                elif self.path == "/status":
                    st = np.array(runner.step_times[-200:]) if runner.step_times else np.array([0])
                    self._send(200, {"running": not runner.stop_flag, "has_goal": runner.goal is not None,
                                     "steps": len(runner.step_times),
                                     "infer_ms_p50": float(np.percentile(st, 50)),
                                     "gpu_mem_gb": torch.cuda.max_memory_allocated() / 1e9})
                else:
                    self._send(404, {"error": "not_found"})

            def do_POST(self):
                if self.path == "/goal":
                    length = int(self.headers.get("content-length", 0))
                    try:
                        body = json.loads(self.rfile.read(length) or b"{}")
                        result = runner.set_goal(str(body["interaction"]), body["bbox"])
                        self._send(200, result)
                    except Exception as e:
                        self._send(400, {"error": str(e)})
                else:
                    self._send(404, {"error": "not_found"})

            def do_DELETE(self):
                if self.path == "/goal":
                    with runner.lock:
                        runner.goal = None
                    self._send(200, {"cleared": True})
                else:
                    self._send(404, {"error": "not_found"})

            def log_message(self, *args):
                pass

        return Handler


def calibrate(bridge):
    """Empirically verify camera sign conventions against the live bot."""
    print("[calibrate] reading observation")
    _, wrap = http_json(f"{bridge}/v1/observation")
    self0 = wrap["observation"]["self"]
    yaw0, pitch0 = self0["yaw"], self0["pitch"]
    # +yaw_delta on the bridge should increase bot.entity.yaw directly.
    http_json(f"{bridge}/v1/action", "POST",
              {"seq": 900000, "ttl_ms": 150, "action": {"yaw_delta": 0.2}})
    time.sleep(0.4)
    _, wrap = http_json(f"{bridge}/v1/observation")
    yaw1 = wrap["observation"]["self"]["yaw"]
    d_yaw = yaw1 - yaw0
    print(f"[calibrate] yaw_delta=+0.2 -> bot yaw moved {d_yaw:+.3f} rad (expect +0.2, pass-through)")
    # meaning: increasing mineflayer yaw turns LEFT (physics source: lookX=-sin(yaw)).
    # A Minecraft player pressing +dx turns RIGHT => yaw_delta must be negative.
    print(f"[calibrate] convention: env dx>0 (right) -> mineflayer yaw_delta {YAW_SIGN:+.0f}*dx  "
          f"(mineflayer yaw+ = left; env + = right)")
    http_json(f"{bridge}/v1/action", "POST",
              {"seq": 900001, "ttl_ms": 150, "action": {"pitch_delta": -0.2}})
    time.sleep(0.4)
    _, wrap = http_json(f"{bridge}/v1/observation")
    pitch1 = wrap["observation"]["self"]["pitch"]
    print(f"[calibrate] pitch_delta=-0.2 -> bot pitch moved {pitch1 - pitch0:+.3f} rad "
          f"(negative = looking down confirms env dy>0=down maps to pitch_delta<0)")
    return {"d_yaw_measured": d_yaw, "d_pitch_measured": pitch1 - pitch0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bridge", default="http://127.0.0.1:8876")
    ap.add_argument("--port", type=int, default=8877)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--calibrate-only", action="store_true")
    args = ap.parse_args()

    LOGS.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")

    if args.calibrate or args.calibrate_only:
        try:
            result = calibrate(args.bridge)
            print(f"[calibrate] result: {result}")
        except Exception as e:
            print(f"[calibrate] FAILED: {e}")
        if args.calibrate_only:
            return

    runner = Runner(args.bridge, args.device)
    runner.load_policy()

    api = ThreadingHTTPServer(("127.0.0.1", args.port), runner.make_handler())
    threading.Thread(target=api.serve_forever, daemon=True).start()
    print(f"[runner] API on http://127.0.0.1:{args.port}  (/goal GET/POST/DELETE, /status)")

    try:
        runner.run(LOGS / f"latency-{ts}.jsonl")
    except KeyboardInterrupt:
        runner.stop_flag = True


if __name__ == "__main__":
    main()
