#!/usr/bin/env python3
"""
TurboToaster sim bridge.

Wraps the proven `gym-donkeycar` Unity simulator (the same one the Donkey Car
project uses for behavior-cloning RC cars) and exposes it over the *exact*
same TCP wire protocol that `car/stream.py` speaks on the real Pi:

    Pi/sim -> PC : [4B len][JPEG bytes]
    PC -> Pi/sim : [4B len]{"steer": ..., "throttle": ..., "ts": ..., "seq": ...}

That means `server/drive.py`, `server/view_stream.py`, `ai/infer.py` and the
recorder all work against the sim with **no code changes** — just point them at
`--host localhost`.

The bridge adds three pen-test knobs the real car can't easily provide:

  --latency-ms N      Add N ms of one-way latency in *each* direction (frames
                      out, commands in).  Use this to simulate the off-site
                      RTX 3090 PC's WAN round-trip.
  --jitter-ms N       Random extra latency 0..N ms per packet.
  --drop P            Probability (0..1) of dropping a single command packet.
  --speed-cap X       Multiply throttle by X (0..1) before feeding the sim,
                      so you can lock the sim to "slow truck" or "scary fast".
  --track NAME        Which built-in track / terrain to load.

Install + run (see sim/README.md for the full walk-through):

    pip install -r sim/requirements.txt
    # download + run the donkey-sim binary from
    # https://github.com/tawnkramer/gym-donkeycar/releases
    export DONKEY_SIM_PATH=/path/to/donkey_sim.x86_64
    python sim/bridge.py --track generated_track --latency-ms 150
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import socket
import struct
import threading
import time
from collections import deque

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sim")

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5000
JPEG_QUALITY = 75

# Built-in tracks shipped with the donkey-sim binary. These are the proven
# scenes from the Donkey Car project — generated road, warehouse, mountain,
# etc. — so we don't have to model any terrain ourselves.
TRACKS = {
    "generated_road":   "donkey-generated-roads-v0",
    "warehouse":        "donkey-warehouse-v0",
    "avc":              "donkey-avc-sparkfun-v0",
    "generated_track":  "donkey-generated-track-v0",
    "mountain":         "donkey-mountain-track-v0",
    "circuit":          "donkey-circuit-launch-track-v0",
    "roboracingleague": "donkey-roboracingleague-track-v0",
    "waveshare":        "donkey-waveshare-v0",
    "minimonaco":       "donkey-minimonaco-track-v0",
    "thunderhill":      "donkey-thunderhill-track-v0",
}


# ---------------------------------------------------------------------------
# Network shaper — schedules sends/applies after a configurable delay.
# Keeps the wire-format identical, just adds delay + drops on top.
# ---------------------------------------------------------------------------

class NetShaper:
    """Tiny per-direction delay/jitter/drop emulator."""

    def __init__(self, latency_ms: float, jitter_ms: float, drop_p: float):
        self.base = latency_ms / 1000.0
        self.jitter = jitter_ms / 1000.0
        self.drop = drop_p

    def schedule(self) -> tuple[bool, float]:
        """Returns (deliver?, deliver_at_monotonic)."""
        if self.drop > 0 and random.random() < self.drop:
            return False, 0.0
        extra = random.random() * self.jitter if self.jitter > 0 else 0.0
        return True, time.monotonic() + self.base + extra


# ---------------------------------------------------------------------------
# Protocol helpers (matching car/stream.py byte-for-byte).
# ---------------------------------------------------------------------------

def _send_framed(conn: socket.socket, payload: bytes) -> None:
    conn.sendall(struct.pack(">I", len(payload)) + payload)


def _recv_exact(conn: socket.socket, n: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


# ---------------------------------------------------------------------------
# Command receiver — reads JSON commands and queues them with delay/drop.
# Applied state is a single most-recent-command slot, so the sim never
# replays stale commands once the link recovers (matches CommandBroker).
# ---------------------------------------------------------------------------

class CommandSlot:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._steer = 0.0
        self._throttle = 0.0
        self._last_seq = -1
        self._last_ts = 0.0
        self._stale_sec = 0.3

    def set(self, steer: float, throttle: float, ts: float | None, seq: int | None) -> None:
        with self._lock:
            if ts is not None and (time.time() - float(ts)) > self._stale_sec:
                return
            if seq is not None:
                if seq <= self._last_seq:
                    return
                self._last_seq = int(seq)
            self._steer = float(steer)
            self._throttle = float(throttle)
            self._last_ts = time.monotonic()

    def get(self) -> tuple[float, float]:
        with self._lock:
            return self._steer, self._throttle

    def is_fresh(self, max_age: float = 0.5) -> bool:
        with self._lock:
            return (time.monotonic() - self._last_ts) < max_age


def _command_receiver(
    conn: socket.socket, slot: CommandSlot, shaper: NetShaper, speed_cap: float
) -> None:
    """Read incoming commands; apply them after the configured delay."""
    pending: deque[tuple[float, dict]] = deque()
    buf = bytearray()
    conn.setblocking(False)

    while True:
        # 1) drain socket into buf
        try:
            chunk = conn.recv(4096)
            if chunk == b"":
                break
            if chunk:
                buf.extend(chunk)
        except BlockingIOError:
            pass
        except OSError:
            break

        # 2) parse complete frames
        while len(buf) >= 4:
            length = struct.unpack(">I", buf[:4])[0]
            if len(buf) < 4 + length:
                break
            payload = bytes(buf[4 : 4 + length])
            del buf[: 4 + length]
            try:
                cmd = json.loads(payload)
            except json.JSONDecodeError:
                continue
            deliver, when = shaper.schedule()
            if deliver:
                pending.append((when, cmd))

        # 3) apply any due commands
        now = time.monotonic()
        while pending and pending[0][0] <= now:
            _, cmd = pending.popleft()
            try:
                steer = float(cmd.get("steer", 0.0))
                throttle = float(cmd.get("throttle", 0.0)) * speed_cap
                slot.set(steer, throttle, cmd.get("ts"), cmd.get("seq"))
            except (TypeError, ValueError):
                continue

        time.sleep(0.002)


# ---------------------------------------------------------------------------
# Sim driver — runs gym-donkeycar, sends JPEGs back.
# ---------------------------------------------------------------------------

def _run_sim(
    conn: socket.socket,
    addr: tuple,
    args: argparse.Namespace,
) -> None:
    import gym  # noqa: WPS433 — lazy import so this module loads w/o gym
    import gym_donkeycar  # noqa: F401  (registers the envs)

    env_id = TRACKS[args.track]
    conf = {
        "exe_path": os.environ.get("DONKEY_SIM_PATH", "remote"),
        "host": args.sim_host,
        "port": args.sim_port,
        "body_style": "donkey",
        "body_rgb": (128, 128, 128),
        "car_name": "TurboToaster",
        "font_size": 100,
        "racer_name": "TurboToaster",
        "country": "DE",
        "bio": "pentest",
        "guid": "tt-sim",
        "max_cte": 8.0,
        "cam_resolution": (args.height, args.width, 3),
        "cam_config": {
            "img_w": args.width,
            "img_h": args.height,
            "img_d": 3,
            "img_enc": "JPG",
            "fov": args.fov,
            "fish_eye_x": 0.0,
            "fish_eye_y": 0.0,
            "offset_x": args.cam_x,
            "offset_y": args.cam_y,
            "offset_z": args.cam_z,
            "rot_x": args.cam_pitch,
            "rot_y": 0.0,
            "rot_z": 0.0,
        },
    }

    log.info("Launching sim env=%s  cam=(%dx%d, fov=%d, pos=%.2f/%.2f/%.2f, pitch=%.1f)",
             env_id, args.width, args.height, args.fov,
             args.cam_x, args.cam_y, args.cam_z, args.cam_pitch)
    env = gym.make(env_id, conf=conf)

    out_shaper = NetShaper(args.latency_ms, args.jitter_ms, 0.0)  # frames don't drop
    in_shaper = NetShaper(args.latency_ms, args.jitter_ms, args.drop)
    slot = CommandSlot()

    recv_thr = threading.Thread(
        target=_command_receiver,
        args=(conn, slot, in_shaper, args.speed_cap),
        daemon=True,
    )
    recv_thr.start()

    obs = env.reset()
    pending_frames: deque[tuple[float, bytes]] = deque()

    frame_dt = 1.0 / args.fps
    next_frame = time.monotonic()
    frames_sent = 0
    t_start = time.monotonic()

    try:
        while True:
            # 1) step the sim with the latest known command
            steer, throttle = slot.get()
            if not slot.is_fresh():
                throttle = 0.0  # safety: no fresh command -> coast/stop
            obs, _r, done, _info = env.step(np.array([steer, throttle]))
            if done:
                obs = env.reset()

            # 2) encode & schedule the frame
            bgr = cv2.cvtColor(obs, cv2.COLOR_RGB2BGR)
            ok, jpg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if ok:
                deliver, when = out_shaper.schedule()
                if deliver:
                    pending_frames.append((when, jpg.tobytes()))

            # 3) deliver any due frames (newest-frame-wins to mirror the Pi)
            now = time.monotonic()
            latest: bytes | None = None
            while pending_frames and pending_frames[0][0] <= now:
                _, latest = pending_frames.popleft()
            if latest is not None:
                try:
                    _send_framed(conn, latest)
                    frames_sent += 1
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
                if frames_sent % 100 == 0:
                    elapsed = now - t_start
                    log.info("sim streaming %.1f fps", frames_sent / elapsed)

            # 4) pace
            next_frame += frame_dt
            sleep = next_frame - time.monotonic()
            if sleep > 0:
                time.sleep(sleep)
            else:
                next_frame = time.monotonic()
    finally:
        try:
            env.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            conn.close()
        except OSError:
            pass
        log.info("Sim client disconnected: %s:%d (%d frames)", addr[0], addr[1], frames_sent)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="TurboToaster <-> gym-donkeycar bridge")
    # listen socket (mimics car/stream.py)
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    # sim
    p.add_argument("--track", choices=sorted(TRACKS.keys()), default="generated_track")
    p.add_argument("--sim-host", default="127.0.0.1",
                   help="Host the donkey-sim binary listens on (default: localhost)")
    p.add_argument("--sim-port", type=int, default=9091)
    p.add_argument("--width", type=int, default=480)
    p.add_argument("--height", type=int, default=270)
    p.add_argument("--fps", type=int, default=30)
    # camera placement (you said the 'god model' decides where the camera sits)
    p.add_argument("--cam-x", type=float, default=0.0, help="lateral offset (m)")
    p.add_argument("--cam-y", type=float, default=0.10, help="height above chassis (m)")
    p.add_argument("--cam-z", type=float, default=0.15, help="forward offset (m)")
    p.add_argument("--cam-pitch", type=float, default=-15.0, help="pitch deg (down=neg)")
    p.add_argument("--fov", type=float, default=120.0, help="horizontal FOV deg")
    # pen-test knobs
    p.add_argument("--latency-ms", type=float, default=0.0,
                   help="One-way base latency added in EACH direction (ms)")
    p.add_argument("--jitter-ms", type=float, default=0.0,
                   help="Random extra latency 0..N ms per packet (each direction)")
    p.add_argument("--drop", type=float, default=0.0,
                   help="Probability of dropping an incoming command (0..1)")
    p.add_argument("--speed-cap", type=float, default=1.0,
                   help="Multiply throttle by this before feeding the sim")
    args = p.parse_args()

    if not 0.0 <= args.drop <= 1.0:
        p.error("--drop must be in [0, 1]")
    if args.speed_cap < 0:
        p.error("--speed-cap must be >= 0")

    log.info("Pen-test knobs: latency=%.1fms jitter=%.1fms drop=%.2f speed_cap=%.2f",
             args.latency_ms, args.jitter_ms, args.drop, args.speed_cap)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((args.host, args.port))
        srv.listen(1)
        log.info("Bridge listening on %s:%d  (track=%s) — waiting for client...",
                 args.host, args.port, args.track)
        while True:
            conn, addr = srv.accept()
            log.info("Client connected: %s:%d", addr[0], addr[1])
            _run_sim(conn, addr, args)


if __name__ == "__main__":
    main()
