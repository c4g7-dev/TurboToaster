#!/usr/bin/env python3
"""
TurboToaster AI inference client \u2014 the "fast loop".

Connects to the Pi's port 5000 exactly like `server/drive.py` does, but
instead of reading keys, it runs a trained behavior-cloning model on each
incoming frame and sends (steer, throttle) back.

The model runs at FP16 on CUDA by default. It's small enough that batch=1
inference takes well under 1 ms on a 3090, so the bottleneck is the WAN
link, not the GPU.

Usage:
    python ai/infer.py --host aicar.local \\
                       --checkpoint ai/checkpoints/best.pt

Add `--perceive` to also run YOLOv8n in a background thread (see
`ai/perceive.py`); detections are only logged, not yet fed into the
controller.
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import torch

from model import build_model


DEFAULT_HOST = "aicar.local"
DEFAULT_PORT = 5000
CMD_HZ = 30          # max command send rate
MAX_THROTTLE = 0.35  # extra safety clamp on top of the Pi's own clamp


# ---------------------------------------------------------------------------
# Socket helpers (same framing as car/stream.py)
# ---------------------------------------------------------------------------

def _recv_frame(conn: socket.socket, buf: bytearray) -> np.ndarray | None:
    while len(buf) < 4:
        chunk = conn.recv(4096)
        if not chunk:
            return None
        buf.extend(chunk)
    length = struct.unpack(">I", buf[:4])[0]
    while len(buf) < 4 + length:
        chunk = conn.recv(65536)
        if not chunk:
            return None
        buf.extend(chunk)
    payload = bytes(buf[4 : 4 + length])
    del buf[: 4 + length]
    arr = np.frombuffer(payload, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


_CMD_SEQ = 0

def _send_command(conn: socket.socket, steer: float, throttle: float) -> bool:
    global _CMD_SEQ
    _CMD_SEQ += 1
    data = json.dumps({
        "steer": round(float(steer), 3),
        "throttle": round(float(throttle), 3),
        "ts": time.time(),
        "seq": _CMD_SEQ,
    }).encode()
    try:
        conn.sendall(struct.pack(">I", len(data)) + data)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Inference wrapper
# ---------------------------------------------------------------------------

class PilotRunner:
    def __init__(self, checkpoint: str, device: str = "cuda", fp16: bool = True):
        ckpt = torch.load(checkpoint, map_location=device)
        model_name = ckpt.get("model", "pilotnet")
        model, preprocess = build_model(model_name)
        model.load_state_dict(ckpt["state_dict"])
        model.eval().to(device)
        if fp16 and device.startswith("cuda"):
            model = model.half()
        self.model = model
        self.preprocess = preprocess
        self.device = device
        self.fp16 = fp16 and device.startswith("cuda")
        print(f"Loaded {model_name} ({ckpt.get('epoch', '?')} ep, "
              f"val={ckpt.get('val_loss', float('nan')):.4f}) "
              f"on {device}  fp16={self.fp16}")

    @torch.inference_mode()
    def __call__(self, bgr: np.ndarray) -> tuple[float, float]:
        x = self.preprocess(bgr)
        t = torch.from_numpy(x).unsqueeze(0).to(self.device, non_blocking=True)
        if self.fp16:
            t = t.half()
        out = self.model(t).float().squeeze(0).cpu().numpy()
        steer, throttle = float(out[0]), float(out[1])
        # clamp
        steer = max(-1.0, min(1.0, steer))
        throttle = max(-1.0, min(MAX_THROTTLE, throttle))
        return steer, throttle


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="TurboToaster AI inference client")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--no-fp16", action="store_true")
    p.add_argument("--show", action="store_true",
                   help="Open a preview window with the live frame + prediction HUD.")
    p.add_argument("--perceive", action="store_true",
                   help="Run YOLOv8n in a background thread on every Nth frame.")
    p.add_argument("--perceive-every", type=int, default=6,
                   help="With --perceive, run detector every N frames (default 6).")
    p.add_argument("--max-throttle", type=float, default=MAX_THROTTLE,
                   help="Extra safety cap on predicted throttle.")
    args = p.parse_args()

    global MAX_THROTTLE
    MAX_THROTTLE = args.max_throttle

    runner = PilotRunner(args.checkpoint, device=args.device, fp16=not args.no_fp16)

    perceiver = None
    if args.perceive:
        from perceive import BackgroundPerceiver
        perceiver = BackgroundPerceiver(every=args.perceive_every)
        perceiver.start()

    print(f"Connecting to {args.host}:{args.port} ...")
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.connect((args.host, args.port))
    conn.settimeout(10.0)
    print("Connected \u2014 running AI. Ctrl-C to stop.")

    buf = bytearray()
    cmd_interval = 1.0 / CMD_HZ
    last_cmd_t = 0.0
    frames = 0
    t_start = time.monotonic()
    steer = throttle = 0.0

    try:
        while True:
            frame = _recv_frame(conn, buf)
            if frame is None:
                print("Stream ended.")
                break

            steer, throttle = runner(frame)
            frames += 1

            if perceiver is not None:
                perceiver.submit(frame, frames)

            now = time.monotonic()
            if now - last_cmd_t >= cmd_interval:
                if not _send_command(conn, steer, throttle):
                    print("Connection lost.")
                    break
                last_cmd_t = now

            if args.show:
                hud = frame.copy()
                cv2.putText(hud, f"steer {steer:+.2f}  thr {throttle:+.2f}",
                            (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (0, 255, 0), 2)
                det = perceiver.latest() if perceiver else None
                if det:
                    cv2.putText(hud, det, (10, 48),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (0, 200, 255), 1)
                cv2.imshow("TurboToaster \u2014 AI", hud)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break

            if frames % 120 == 0:
                fps = frames / max(time.monotonic() - t_start, 1e-6)
                print(f"  {fps:5.1f} fps  steer={steer:+.2f}  throttle={throttle:+.2f}")

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        _send_command(conn, 0.0, 0.0)
        try:
            conn.close()
        except OSError:
            pass
        if perceiver is not None:
            perceiver.stop()
        if args.show:
            cv2.destroyAllWindows()
        print("Disconnected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
