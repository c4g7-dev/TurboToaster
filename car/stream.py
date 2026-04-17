#!/usr/bin/env python3
"""
TurboToaster — Pi streaming server.

Listens for a connection from the (remote) AI server PC, then continuously:
  - Streams camera frames (length-prefixed JPEG over TCP)
  - Receives drive commands ({steer, throttle} JSON) from the PC

Optionally, a second TCP port (default 5001) accepts authenticated
**local-network manual-override** connections. This lets someone on the
same LAN as the car grab the wheel with very low latency, bypassing the
remote AI PC (which may live off-site / across the internet and therefore
adds round-trip delay on top of the inherent video-frame latency).

Wire protocol (both directions, both ports):
    [4 bytes big-endian: payload length] [payload bytes]
  Pi → PC  payload: raw JPEG bytes (video port only)
  PC → Pi  payload: UTF-8 JSON

AI channel commands (port 5000):
    {"steer": 0.0, "throttle": 0.0}

Manual-override channel (port 5001), first message must be a handshake:
    {"auth": "<shared-keyword>"}
The Pi replies with {"ok": true} on success, then accepts the same
{"steer", "throttle"} JSON commands. While a manual-override client is
active (and for a short grace period after each manual command) any
commands arriving on the AI channel are ignored.

Usage:
    python3 stream.py [--host 0.0.0.0] [--port 5000]
    python3 stream.py --width 640 --height 480 --fps 30
    python3 stream.py --control-key hunter2           # enable LAN override
    TURBOTOASTER_CONTROL_KEY=hunter2 python3 stream.py
"""

import argparse
import json
import logging
import os
import socket
import struct
import threading
import time

import cv2
import numpy as np
from picamera2 import Picamera2  # type: ignore

from control import CarControl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5000
DEFAULT_CONTROL_PORT = 5001
MANUAL_HOLD_SEC = 0.5  # after each manual cmd, ignore AI cmds for this long
JPEG_QUALITY = 80


# ---------------------------------------------------------------------------
# Command broker — arbitrates between AI (remote) and manual (LAN) sources.
# Manual commands take priority; for a short grace period after each manual
# command, AI commands are ignored so the two sources don't fight.
# ---------------------------------------------------------------------------

class CommandBroker:
    def __init__(self, car: CarControl, manual_hold_sec: float = MANUAL_HOLD_SEC):
        self._car = car
        self._hold_sec = manual_hold_sec
        self._manual_hold_until = 0.0
        self._lock = threading.Lock()

    def apply_ai(self, steer: float, throttle: float) -> None:
        with self._lock:
            if time.monotonic() < self._manual_hold_until:
                return  # manual override active — ignore AI
            self._car.set_steering(steer)
            self._car.set_throttle(throttle)

    def apply_manual(self, steer: float, throttle: float) -> None:
        with self._lock:
            self._manual_hold_until = time.monotonic() + self._hold_sec
            self._car.set_steering(steer)
            self._car.set_throttle(throttle)

    def release_manual(self) -> None:
        with self._lock:
            self._manual_hold_until = 0.0

    def stop(self) -> None:
        self._car.stop()


# ---------------------------------------------------------------------------
# Command receiver (AI channel — runs in a separate thread)
# ---------------------------------------------------------------------------

def _command_receiver(conn: socket.socket, broker: CommandBroker) -> None:
    """Read length-prefixed JSON commands and forward them to the car."""
    buf = bytearray()
    while True:
        try:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
            # consume all complete messages in the buffer
            while len(buf) >= 4:
                length = struct.unpack(">I", buf[:4])[0]
                if len(buf) < 4 + length:
                    break
                payload = buf[4 : 4 + length]
                del buf[: 4 + length]
                try:
                    cmd = json.loads(payload)
                    broker.apply_ai(
                        float(cmd.get("steer", 0.0)),
                        float(cmd.get("throttle", 0.0)),
                    )
                except (json.JSONDecodeError, ValueError, KeyError) as exc:
                    log.warning("Bad command: %s", exc)
        except OSError:
            break
    broker.stop()
    log.debug("Command receiver exiting")


# ---------------------------------------------------------------------------
# LAN manual-override listener — separate port, pre-shared auth key.
# ---------------------------------------------------------------------------

def _send_framed(conn: socket.socket, obj: dict) -> None:
    data = json.dumps(obj).encode()
    try:
        conn.sendall(struct.pack(">I", len(data)) + data)
    except OSError:
        pass


def _recv_framed(conn: socket.socket, buf: bytearray, max_len: int = 65536):
    """Receive exactly one length-prefixed JSON message. Returns dict or None."""
    while len(buf) < 4:
        chunk = conn.recv(4096)
        if not chunk:
            return None
        buf.extend(chunk)
    length = struct.unpack(">I", buf[:4])[0]
    if length <= 0 or length > max_len:
        return None
    while len(buf) < 4 + length:
        chunk = conn.recv(4096)
        if not chunk:
            return None
        buf.extend(chunk)
    payload = bytes(buf[4 : 4 + length])
    del buf[: 4 + length]
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {}


def _handle_control_client(
    conn: socket.socket, addr: tuple, broker: CommandBroker, auth_key: str
) -> None:
    log.info("Manual-override client connecting: %s:%d", addr[0], addr[1])
    conn.settimeout(5.0)
    buf = bytearray()
    try:
        # 1) handshake
        hello = _recv_framed(conn, buf)
        if not hello or hello.get("auth") != auth_key:
            log.warning("Manual-override auth FAILED from %s:%d", addr[0], addr[1])
            _send_framed(conn, {"ok": False, "error": "bad auth"})
            return
        _send_framed(conn, {"ok": True})
        log.info("Manual-override AUTH OK from %s:%d", addr[0], addr[1])

        # 2) command loop
        conn.settimeout(None)
        while True:
            msg = _recv_framed(conn, buf)
            if msg is None:
                break
            if msg.get("release"):
                broker.release_manual()
                continue
            try:
                broker.apply_manual(
                    float(msg.get("steer", 0.0)),
                    float(msg.get("throttle", 0.0)),
                )
            except (ValueError, TypeError) as exc:
                log.warning("Bad manual command: %s", exc)
    except OSError:
        pass
    finally:
        broker.release_manual()
        try:
            conn.close()
        except OSError:
            pass
        log.info("Manual-override client disconnected: %s:%d", addr[0], addr[1])


def _control_listener(host: str, port: int, broker: CommandBroker, auth_key: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen(2)
        log.info("Manual-override listener on %s:%d (auth required)", host, port)
        while True:
            try:
                conn, addr = srv.accept()
            except OSError:
                return
            threading.Thread(
                target=_handle_control_client,
                args=(conn, addr, broker, auth_key),
                daemon=True,
            ).start()


# ---------------------------------------------------------------------------
# Client handler
# ---------------------------------------------------------------------------

def _handle_client(
    conn: socket.socket,
    addr: tuple,
    broker: CommandBroker,
    width: int,
    height: int,
    fps: int,
) -> None:
    log.info("AI client connected: %s:%d", addr[0], addr[1])

    cam = Picamera2()
    config = cam.create_video_configuration(
        main={"size": (width, height), "format": "RGB888"},
        controls={"FrameRate": fps},
    )
    cam.configure(config)
    cam.start()
    time.sleep(0.3)  # let sensor settle

    # start command-receiver thread
    recv_thread = threading.Thread(
        target=_command_receiver, args=(conn, broker), daemon=True
    )
    recv_thread.start()

    frames_sent = 0
    t_start = time.monotonic()

    try:
        while True:
            frame_rgb = cam.capture_array()
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

            ok, buf = cv2.imencode(
                ".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
            )
            if not ok:
                continue

            data = buf.tobytes()
            try:
                conn.sendall(struct.pack(">I", len(data)) + data)
            except (BrokenPipeError, ConnectionResetError, OSError):
                break

            frames_sent += 1
            if frames_sent % 100 == 0:
                elapsed = time.monotonic() - t_start
                log.info("Streaming %.1f FPS", frames_sent / elapsed)

    finally:
        cam.stop()
        broker.stop()
        conn.close()
        log.info("AI client disconnected: %s:%d  (%d frames sent)", addr[0], addr[1], frames_sent)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="TurboToaster Pi stream server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument(
        "--control-port",
        type=int,
        default=DEFAULT_CONTROL_PORT,
        help="TCP port for LAN manual-override clients",
    )
    parser.add_argument(
        "--control-key",
        default=os.environ.get("TURBOTOASTER_CONTROL_KEY"),
        help="Shared secret for LAN manual-override clients "
             "(or set env TURBOTOASTER_CONTROL_KEY). "
             "If unset, the manual-override listener is disabled.",
    )
    args = parser.parse_args()

    car = CarControl()
    broker = CommandBroker(car)

    if args.control_key:
        threading.Thread(
            target=_control_listener,
            args=(args.host, args.control_port, broker, args.control_key),
            daemon=True,
        ).start()
    else:
        log.info(
            "Manual-override listener DISABLED "
            "(set --control-key or TURBOTOASTER_CONTROL_KEY to enable)"
        )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((args.host, args.port))
        srv.listen(1)
        log.info(
            "Listening on %s:%d  [%dx%d @ %d fps] — waiting for PC...",
            args.host, args.port, args.width, args.height, args.fps,
        )

        while True:
            conn, addr = srv.accept()
            # Only one AI/video client at a time — handle in current thread so
            # that we can accept the next connection once this one closes.
            _handle_client(conn, addr, broker, args.width, args.height, args.fps)


if __name__ == "__main__":
    main()
