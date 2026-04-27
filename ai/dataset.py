"""
Dataset loaders for TurboToaster behavior cloning.

Supports two on-disk formats, transparently:

1. **TurboToaster session**  (produced by `server/recorder.py`):
       <root>/images/frame_*.jpg
       <root>/log.csv    \u2014 ts,seq,steer,throttle,filename

2. **Donkey Car v1 tub**:
       <root>/record_*.json   \u2014 {"cam/image_array": "...", "user/angle": ..., "user/throttle": ...}
       <root>/<image>.jpg     (or the filename referenced by each record)

Pass any mix of session/tub directories to `DriveDataset`; it will stitch them
together and apply the supplied preprocessing function.
"""

from __future__ import annotations

import csv
import glob
import json
import os
from pathlib import Path
from typing import Callable, Sequence

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset


class DriveDataset(Dataset):
    def __init__(
        self,
        roots: Sequence[str | os.PathLike],
        preprocess: Callable[[np.ndarray], np.ndarray],
        augment: bool = False,
    ):
        self.preprocess = preprocess
        self.augment = augment
        self.samples: list[tuple[Path, float, float]] = []
        for r in roots:
            root = Path(r)
            if not root.exists():
                raise FileNotFoundError(root)
            before = len(self.samples)
            self._load_session(root) or self._load_donkey(root)
            print(f"  {root}: +{len(self.samples) - before} samples")
        if not self.samples:
            raise RuntimeError("No training samples found.")
        print(f"Total: {len(self.samples)} samples")

    # ---- loaders --------------------------------------------------------

    def _load_session(self, root: Path) -> bool:
        csv_path = root / "log.csv"
        if not csv_path.exists():
            return False
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                img = root / "images" / row["filename"]
                if img.exists():
                    self.samples.append(
                        (img, float(row["steer"]), float(row["throttle"]))
                    )
        return True

    def _load_donkey(self, root: Path) -> bool:
        records = sorted(glob.glob(str(root / "record_*.json")))
        if not records:
            return False
        for rp in records:
            with open(rp) as f:
                rec = json.load(f)
            fname = rec.get("cam/image_array")
            if not fname:
                continue
            img = root / fname
            if not img.is_absolute() and not img.exists():
                img = root / "images" / fname
            if not img.exists():
                continue
            self.samples.append(
                (img,
                 float(rec.get("user/angle", 0.0)),
                 float(rec.get("user/throttle", 0.0))),
            )
        return True

    # ---- dataset API ----------------------------------------------------

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        img_path, steer, throttle = self.samples[idx]
        bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if bgr is None:
            raise RuntimeError(f"failed to read {img_path}")

        if self.augment:
            # Horizontal flip: also flip steering sign. Cheap and effective on
            # small RC datasets, which are usually left/right biased.
            if np.random.rand() < 0.5:
                bgr = cv2.flip(bgr, 1)
                steer = -steer
            # Mild brightness jitter
            if np.random.rand() < 0.5:
                factor = 0.6 + np.random.rand() * 0.8
                bgr = np.clip(bgr.astype(np.float32) * factor, 0, 255).astype(np.uint8)

        x = torch.from_numpy(self.preprocess(bgr)).float()
        y = torch.tensor([steer, throttle], dtype=torch.float32)
        return x, y
