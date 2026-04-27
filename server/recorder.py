"""
Dataset recorder \u2014 saves (frame, steer, throttle) tuples during manual drives
so they can be used later to train a behavior-cloning model.

Layout (one directory per session):

    <root>/session_<YYYYmmdd-HHMMSS>/
        images/
            frame_000001.jpg
            frame_000002.jpg
            ...
        log.csv                     # ts,seq,steer,throttle,filename
        meta.json                   # width,height,fps hint,session start ts

Also writes Donkey-style `record_<seq>.json` sidecar files next to each image
so the dataset can be consumed by the Donkey-tub loader in ai/dataset.py.
"""

from __future__ import annotations

import csv
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


class SessionRecorder:
    def __init__(self, root: str | os.PathLike, session_name: str | None = None):
        stamp = session_name or datetime.now().strftime("session_%Y%m%d-%H%M%S")
        self.dir = Path(root) / stamp
        (self.dir / "images").mkdir(parents=True, exist_ok=True)
        self._csv_path = self.dir / "log.csv"
        new_file = not self._csv_path.exists()
        # `newline=""` so csv module handles line endings cross-platform
        self._csv_file = open(self._csv_path, "a", newline="")
        self._csv = csv.writer(self._csv_file)
        if new_file:
            self._csv.writerow(["ts", "seq", "steer", "throttle", "filename"])
        self._seq = 0
        self._lock = threading.Lock()
        self._t0 = time.time()
        with open(self.dir / "meta.json", "w") as f:
            json.dump({"started": self._t0}, f)

    def add(self, frame_bgr: np.ndarray, steer: float, throttle: float) -> None:
        if frame_bgr is None:
            return
        with self._lock:
            self._seq += 1
            seq = self._seq
            ts = time.time()
        fname = f"frame_{seq:06d}.jpg"
        cv2.imwrite(str(self.dir / "images" / fname), frame_bgr,
                    [cv2.IMWRITE_JPEG_QUALITY, 90])
        with self._lock:
            self._csv.writerow([f"{ts:.6f}", seq,
                                f"{steer:.4f}", f"{throttle:.4f}", fname])
            self._csv_file.flush()
        # Donkey-compatible sidecar (optional but cheap)
        with open(self.dir / f"record_{seq}.json", "w") as f:
            json.dump({
                "cam/image_array": fname,
                "user/angle": float(steer),
                "user/throttle": float(throttle),
                "timestamp": ts,
            }, f)

    def close(self) -> None:
        try:
            self._csv_file.flush()
            self._csv_file.close()
        except OSError:
            pass

    def __enter__(self) -> "SessionRecorder":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
