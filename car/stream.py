#!/usr/bin/env python3
"""
TurboToaster — Pi streaming server.

Listens for a connection from the server PC, then continuously:
  - Streams camera frames (length-prefixed JPEG over TCP)
  - Receives drive commands ({steer, throttle} JSON) from the PC

Wire protocol (both directions):
    [4 bytes big-endian: payload length] [payload bytes]
  Pi → PC  payload: raw JPEG bytes
  PC → Pi  payload: UTF-8 JSON  e.g. {"steer": 0.0, "throttle": 0.0}

Usage:
    python3 stream.py [--host 0.0.0.0] [--port 5000]
    python3 stream.py --width 640 --height 480 --fps 30
"""

import argparse
import json
import logging
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
JPEG_QUALITY = 80


# ---------------------------------------------------------------------------
# Command receiver (runs in a separate thread)
# ---------------------------------------------------------------------------

def _command_receiver(conn: socket.socket, car: CarControl) -> None:
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
                    car.set_steering(float(cmd.get("steer", 0.0)))
                    car.set_throttle(float(cmd.get("throttle", 0.0)))
                except (json.JSONDecodeError, ValueError, KeyError) as exc:
                    log.warning("Bad command: %s", exc)
        except OSError:
            break
    car.stop()
    log.debug("Command receiver exiting")


# ---------------------------------------------------------------------------
# Client handler
# ---------------------------------------------------------------------------

def _handle_client(
    conn: socket.socket,
    addr: tuple,
    car: CarControl,
    width: int,
    height: int,
    fps: int,
) -> None:
    log.info("Client connected: %s:%d", addr[0], addr[1])

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
        target=_command_receiver, args=(conn, car), daemon=True
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
        car.stop()
        conn.close()
        log.info("Client disconnected: %s:%d  (%d frames sent)", addr[0], addr[1], frames_sent)


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
    args = parser.parse_args()

    car = CarControl()

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
            # Only one client at a time — handle in current thread so that
            # we can accept the next connection once this one closes.
            _handle_client(conn, addr, car, args.width, args.height, args.fps)


if __name__ == "__main__":
    main()
