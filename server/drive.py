#!/usr/bin/env python3
"""
TurboToaster — manual drive client.

Connects to the Pi, displays the live camera stream, and sends steering
and throttle commands via keyboard.

Wire protocol — identical to stream.py:
    [4-byte big-endian length] [payload]
  Pi → PC: JPEG frame bytes
  PC → Pi: UTF-8 JSON  {"steer": <float>, "throttle": <float>}

Usage:
    python3 drive.py --host aicar.local
    python3 drive.py --host 192.168.1.42

Keys:
    W / Up arrow    Increase throttle
    S / Down arrow  Decrease throttle (brake / reverse)
    A / Left arrow  Steer left
    D / Right arrow Steer right
    Space           Emergency stop (zero steer + throttle)
    Q / Esc         Quit
"""

import argparse
import json
import socket
import struct
import time

import cv2
import numpy as np

DEFAULT_HOST   = "aicar.local"
DEFAULT_PORT   = 5000
CMD_HZ         = 20          # command send rate
STEER_STEP     = 0.10        # steer increment per keypress
THROTTLE_STEP  = 0.10        # throttle increment per keypress


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------

def _recv_frame(conn: socket.socket, buf: bytearray) -> np.ndarray | None:
    """Receive one length-prefixed JPEG frame and decode it."""
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


def _send_command(conn: socket.socket, steer: float, throttle: float) -> bool:
    data = json.dumps(
        {"steer": round(steer, 3), "throttle": round(throttle, 3)}
    ).encode()
    try:
        conn.sendall(struct.pack(">I", len(data)) + data)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# HUD overlay
# ---------------------------------------------------------------------------

def _draw_hud(frame: np.ndarray, steer: float, throttle: float, fps: float) -> np.ndarray:
    h, w = frame.shape[:2]
    out = frame.copy()

    # FPS (top-left)
    cv2.putText(out, f"{fps:.1f} FPS", (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    # Steering bar (bottom centre)
    bar_y = h - 12
    cx    = w // 2
    tip_x = cx + int(steer * 80)
    cv2.line(out, (cx, bar_y), (tip_x, bar_y - 18), (0, 255, 255), 3)
    cv2.putText(out, f"steer {steer:+.2f}", (10, h - 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # Throttle bar (right edge)
    bar_max = 120
    bar_h   = int(abs(throttle) * bar_max)
    color   = (0, 200, 0) if throttle >= 0 else (0, 60, 200)
    by      = h - 20
    cv2.rectangle(out, (w - 28, by - bar_h), (w - 10, by), color, -1)
    cv2.putText(out, f"thr {throttle:+.2f}", (w - 90, by + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

    # Controls hint (top-right)
    hint = "WASD/arrows  Space=stop  Q=quit"
    cv2.putText(out, hint, (w - 350, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="TurboToaster manual drive client")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Pi hostname or IP")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    print(f"Connecting to {args.host}:{args.port} ...")
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.connect((args.host, args.port))
    conn.settimeout(5.0)
    print("Connected — use WASD/arrows to drive, Space to stop, Q to quit.")

    steer    = 0.0
    throttle = 0.0
    buf      = bytearray()

    cmd_interval = 1.0 / CMD_HZ
    last_cmd_t   = 0.0
    prev_t       = time.monotonic()
    fps          = 0.0

    try:
        while True:
            frame = _recv_frame(conn, buf)
            if frame is None:
                print("Stream ended.")
                break

            now = time.monotonic()
            fps = 0.9 * fps + 0.1 / max(now - prev_t, 1e-6)
            prev_t = now

            display = _draw_hud(frame, steer, throttle, fps)
            cv2.imshow("TurboToaster — Drive", display)

            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):            # Q / Esc — quit
                break
            elif key == ord(" "):                # Space — e-stop
                steer    = 0.0
                throttle = 0.0
            elif key in (ord("w"), 82):          # W / Up
                throttle = min(1.0, throttle + THROTTLE_STEP)
            elif key in (ord("s"), 84):          # S / Down
                throttle = max(-1.0, throttle - THROTTLE_STEP)
            elif key in (ord("a"), 81):          # A / Left
                steer = max(-1.0, steer - STEER_STEP)
            elif key in (ord("d"), 83):          # D / Right
                steer = min(1.0,  steer + STEER_STEP)

            if now - last_cmd_t >= cmd_interval:
                if not _send_command(conn, steer, throttle):
                    print("Connection lost.")
                    break
                last_cmd_t = now

    finally:
        _send_command(conn, 0.0, 0.0)
        conn.close()
        cv2.destroyAllWindows()
        print("Disconnected.")


if __name__ == "__main__":
    main()
