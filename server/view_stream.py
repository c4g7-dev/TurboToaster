#!/usr/bin/env python3
"""
TurboToaster — stream viewer (view only, no control).

Use this first to confirm the Pi is reachable and the camera is working
before attaching any steering/throttle controls.

Usage:
    python3 view_stream.py --host aicar.local
    python3 view_stream.py --host 192.168.1.42 --port 5000

Press Q or Esc to quit.
"""

import argparse
import socket
import struct
import time

import cv2
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description="TurboToaster stream viewer")
    parser.add_argument("--host", default="aicar.local", help="Pi hostname or IP")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    print(f"Connecting to {args.host}:{args.port} ...")
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.connect((args.host, args.port))
    conn.settimeout(5.0)
    print("Connected — press Q or Esc to quit.")

    buf = bytearray()
    frames = 0
    t_start = time.monotonic()

    try:
        while True:
            # read 4-byte length header
            while len(buf) < 4:
                chunk = conn.recv(4096)
                if not chunk:
                    raise ConnectionError("stream ended")
                buf.extend(chunk)

            length = struct.unpack(">I", buf[:4])[0]

            # read JPEG payload
            while len(buf) < 4 + length:
                chunk = conn.recv(65536)
                if not chunk:
                    raise ConnectionError("stream ended")
                buf.extend(chunk)

            payload = bytes(buf[4 : 4 + length])
            del buf[: 4 + length]

            arr = np.frombuffer(payload, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                continue

            frames += 1
            elapsed = time.monotonic() - t_start
            fps = frames / elapsed if elapsed > 0 else 0.0

            cv2.putText(
                frame,
                f"{fps:.1f} FPS",
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 0),
                2,
            )
            cv2.imshow("TurboToaster — Live View", frame)

            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break

    except (ConnectionError, ConnectionResetError, TimeoutError) as exc:
        print(f"\nConnection ended: {exc}")
    finally:
        conn.close()
        cv2.destroyAllWindows()
        elapsed = time.monotonic() - t_start
        if elapsed > 0:
            print(f"Received {frames} frames in {elapsed:.1f} s ({frames/elapsed:.1f} FPS avg)")


if __name__ == "__main__":
    main()
