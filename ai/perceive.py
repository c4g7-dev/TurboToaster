"""
Background perceiver \u2014 the "slow loop".

Runs heavier vision models (default: YOLOv8n for object detection) on a
subsample of frames fed in from the fast inference loop. Results are
published as a short human-readable string via `latest()`; a future step
could feed the raw detections back into the fast loop as extra features
(obstacle flag, lane hint, etc.).

The perceiver lives in its own thread and uses a single-slot queue so it
never holds the fast loop up and never processes stale frames.

Usage (inside infer.py):

    from perceive import BackgroundPerceiver
    p = BackgroundPerceiver(every=6)   # run on every 6th frame
    p.start()
    ...
    p.submit(frame, frame_index)
    s = p.latest()                      # \u2192 e.g. "person 0.87, chair 0.54"
    ...
    p.stop()
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np


class BackgroundPerceiver:
    def __init__(self, every: int = 6, conf: float = 0.35,
                 model_name: str = "yolov8n.pt", imgsz: int = 416):
        self._every = max(1, int(every))
        self._conf = conf
        self._model_name = model_name
        self._imgsz = imgsz
        self._slot: Optional[np.ndarray] = None
        self._lock = threading.Condition()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._latest_text: str = ""

    # ---- public API -----------------------------------------------------

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            self._lock.notify_all()

    def submit(self, frame: np.ndarray, frame_idx: int) -> None:
        if frame_idx % self._every != 0:
            return
        with self._lock:
            self._slot = frame  # overwrite; slow loop only ever sees newest
            self._lock.notify()

    def latest(self) -> str:
        return self._latest_text

    # ---- internals ------------------------------------------------------

    def _run(self) -> None:
        try:
            from ultralytics import YOLO  # type: ignore
        except ImportError:
            self._latest_text = "ultralytics not installed"
            return
        model = YOLO(self._model_name)
        print(f"[perceive] loaded {self._model_name}")

        while not self._stop.is_set():
            with self._lock:
                while self._slot is None and not self._stop.is_set():
                    self._lock.wait(timeout=1.0)
                if self._stop.is_set():
                    return
                frame = self._slot
                self._slot = None

            t0 = time.monotonic()
            results = model.predict(
                frame, imgsz=self._imgsz, conf=self._conf, verbose=False,
            )
            dt_ms = (time.monotonic() - t0) * 1000

            parts: list[str] = []
            for r in results:
                names = r.names
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    cls = int(box.cls.item())
                    score = float(box.conf.item())
                    parts.append(f"{names.get(cls, cls)} {score:.2f}")
            self._latest_text = (
                (", ".join(parts) if parts else "(nothing)")
                + f"  [{dt_ms:.0f} ms]"
            )
