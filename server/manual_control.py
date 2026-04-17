#!/usr/bin/env python3
"""
TurboToaster — LAN manual-control client.

A tiny companion program meant to run on the *same local network* as the
car. It attaches to the Pi's dedicated manual-override port (default 5001),
authenticates with a pre-shared keyword, and then sends steering/throttle
commands. No video is pulled, which keeps latency as low as possible — the
idea is that the AI inference PC (the RTX 3090 box) lives somewhere else
physically, so we want a LAN-local fallback that can grab the wheel without
waiting on a round-trip across the internet.

While this client is connected and actively sending, the Pi ignores
commands coming in from the AI channel (see `car/stream.py`'s
`CommandBroker`).

Wire protocol — length-prefixed JSON, same framing as `stream.py`:
    [4-byte big-endian length] [UTF-8 JSON]
  First message (handshake): {"auth": "<keyword>"}
  Server reply:               {"ok": true} or {"ok": false, "error": "..."}
  Subsequent messages:        {"steer": <float>, "throttle": <float>}
  Optional release message:   {"release": true}

Usage:
    python3 manual_control.py --host aicar.local --key hunter2
    TURBOTOASTER_CONTROL_KEY=hunter2 python3 manual_control.py --host 192.168.1.42

Keys (same as drive.py):
    W / Up arrow    Increase throttle
    S / Down arrow  Decrease throttle (brake / reverse)
    A / Left arrow  Steer left
    D / Right arrow Steer right
    Space           Emergency stop (zero steer + throttle)
    R               Release override (hand back to AI)
    Q / Esc         Quit
"""

import argparse
import json
import os
import socket
import struct
import sys
import time

import cv2
import numpy as np

DEFAULT_HOST = "aicar.local"
DEFAULT_PORT = 5001
CMD_HZ = 30          # a bit higher than drive.py — no video to pace us
STEER_STEP = 0.10
THROTTLE_STEP = 0.10


# ---------------------------------------------------------------------------
# Framed JSON helpers
# ---------------------------------------------------------------------------

def _send(conn: socket.socket, obj: dict) -> bool:
    data = json.dumps(obj).encode()
    try:
        conn.sendall(struct.pack(">I", len(data)) + data)
        return True
    except OSError:
        return False


def _recv(conn: socket.socket, buf: bytearray, timeout: float = 5.0):
    conn.settimeout(timeout)
    try:
        while len(buf) < 4:
            chunk = conn.recv(4096)
            if not chunk:
                return None
            buf.extend(chunk)
        length = struct.unpack(">I", buf[:4])[0]
        while len(buf) < 4 + length:
            chunk = conn.recv(4096)
            if not chunk:
                return None
            buf.extend(chunk)
        payload = bytes(buf[4 : 4 + length])
        del buf[: 4 + length]
        return json.loads(payload)
    except (OSError, json.JSONDecodeError):
        return None
    finally:
        conn.settimeout(None)


# ---------------------------------------------------------------------------
# Status HUD (no video — just a small window so we can capture keys via cv2)
# ---------------------------------------------------------------------------

def _render_hud(steer: float, throttle: float, connected: bool) -> np.ndarray:
    w, h = 480, 220
    img = np.zeros((h, w, 3), dtype=np.uint8)

    banner = "LAN OVERRIDE" if connected else "DISCONNECTED"
    color = (0, 200, 0) if connected else (0, 0, 200)
    cv2.putText(img, banner, (14, 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

    cv2.putText(img, f"steer    {steer:+.2f}", (14, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(img, f"throttle {throttle:+.2f}", (14, 115),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # steering bar
    cx, y = w // 2, 155
    cv2.line(img, (cx - 120, y), (cx + 120, y), (60, 60, 60), 2)
    cv2.circle(img, (cx + int(steer * 120), y), 6, (0, 255, 255), -1)

    cv2.putText(img, "WASD/arrows  Space=stop  R=release  Q=quit",
                (14, h - 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
    return img


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="TurboToaster LAN manual-control client"
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Pi hostname or IP")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--key",
        default=os.environ.get("TURBOTOASTER_CONTROL_KEY"),
        help="Shared auth keyword (or set env TURBOTOASTER_CONTROL_KEY)",
    )
    args = parser.parse_args()

    if not args.key:
        print("ERROR: no auth key — pass --key or set TURBOTOASTER_CONTROL_KEY",
              file=sys.stderr)
        return 2

    print(f"Connecting to {args.host}:{args.port} (LAN manual-override) ...")
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.connect((args.host, args.port))

    buf = bytearray()
    if not _send(conn, {"auth": args.key}):
        print("Failed to send handshake.", file=sys.stderr)
        return 1
    reply = _recv(conn, buf, timeout=5.0)
    if not reply or not reply.get("ok"):
        err = (reply or {}).get("error", "no response")
        print(f"Auth failed: {err}", file=sys.stderr)
        conn.close()
        return 1
    print("Authenticated — LAN manual-override active.")

    steer = 0.0
    throttle = 0.0
    cmd_interval = 1.0 / CMD_HZ
    last_cmd_t = 0.0
    connected = True

    try:
        while True:
            cv2.imshow("TurboToaster — LAN Manual Control",
                       _render_hud(steer, throttle, connected))
            key = cv2.waitKey(10) & 0xFF

            if key in (ord("q"), 27):            # Q / Esc
                break
            elif key == ord(" "):                # space — e-stop
                steer = 0.0
                throttle = 0.0
            elif key == ord("r"):                # release override
                _send(conn, {"release": True})
                steer = 0.0
                throttle = 0.0
            elif key in (ord("w"), 82):
                throttle = min(1.0, throttle + THROTTLE_STEP)
            elif key in (ord("s"), 84):
                throttle = max(-1.0, throttle - THROTTLE_STEP)
            elif key in (ord("a"), 81):
                steer = max(-1.0, steer - STEER_STEP)
            elif key in (ord("d"), 83):
                steer = min(1.0, steer + STEER_STEP)

            now = time.monotonic()
            if now - last_cmd_t >= cmd_interval:
                if not _send(conn, {"steer": round(steer, 3),
                                    "throttle": round(throttle, 3)}):
                    print("Connection lost.")
                    connected = False
                    break
                last_cmd_t = now

    finally:
        # Always try to zero the car before leaving.
        _send(conn, {"steer": 0.0, "throttle": 0.0})
        _send(conn, {"release": True})
        try:
            conn.close()
        except OSError:
            pass
        cv2.destroyAllWindows()
        print("Disconnected.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
