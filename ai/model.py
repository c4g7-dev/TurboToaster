"""
Models for TurboToaster behavior cloning.

Two architectures are provided:

* `PilotNet`   \u2014 the classic NVIDIA end-to-end CNN (~250k params). Input is a
                3x66x200 YUV tensor in [-1, 1]. Runs in well under 1 ms on a
                3090 at FP16, batch 1.
* `MobileNetV3Pilot` \u2014 a MobileNetV3-small backbone (ImageNet-pretrained) with
                a 2-output regression head. Bigger (~1.5M params) but
                generalises better on small datasets.

Both output (steer, throttle) in [-1, 1]; a tanh is applied at the very end.
"""

from __future__ import annotations

import cv2
import numpy as np
import torch
import torch.nn as nn


# (W, H) \u2014 matches the original PilotNet paper. The cv2.resize call uses
# (W, H) order; the tensor shape is (C, H, W).
PILOTNET_INPUT_WH = (200, 66)


class PilotNet(nn.Module):
    """NVIDIA "End to End Learning for Self-Driving Cars" (arXiv:1604.07316)."""

    def __init__(self) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(3, 24, 5, stride=2), nn.ELU(),
            nn.Conv2d(24, 36, 5, stride=2), nn.ELU(),
            nn.Conv2d(36, 48, 5, stride=2), nn.ELU(),
            nn.Conv2d(48, 64, 3), nn.ELU(),
            nn.Conv2d(64, 64, 3), nn.ELU(),
        )
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 1 * 18, 100), nn.ELU(),
            nn.Linear(100, 50), nn.ELU(),
            nn.Linear(50, 10), nn.ELU(),
            nn.Linear(10, 2),
            nn.Tanh(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.conv(x))


class MobileNetV3Pilot(nn.Module):
    """MobileNetV3-small backbone + 2-output regression head."""

    def __init__(self, pretrained: bool = True) -> None:
        super().__init__()
        from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights
        weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        net = mobilenet_v3_small(weights=weights)
        # Replace final classifier with a small regression head.
        in_features = net.classifier[-1].in_features
        net.classifier[-1] = nn.Sequential(
            nn.Linear(in_features, 64),
            nn.Hardswish(),
            nn.Dropout(0.2),
            nn.Linear(64, 2),
            nn.Tanh(),
        )
        self.net = net

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ---------------------------------------------------------------------------
# Preprocessing \u2014 shared between training and inference so there's no drift.
# ---------------------------------------------------------------------------

# ImageNet stats, used by MobileNetV3
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def preprocess_pilotnet(bgr: np.ndarray) -> np.ndarray:
    """BGR uint8 frame \u2192 float32 CHW YUV tensor in [-1, 1]."""
    img = cv2.resize(bgr, PILOTNET_INPUT_WH, interpolation=cv2.INTER_AREA)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2YUV)
    img = img.astype(np.float32) / 127.5 - 1.0
    return np.transpose(img, (2, 0, 1))  # HWC \u2192 CHW


def preprocess_mobilenet(bgr: np.ndarray, size: int = 160) -> np.ndarray:
    """BGR uint8 frame \u2192 float32 CHW RGB tensor, ImageNet-normalised."""
    img = cv2.resize(bgr, (size, size), interpolation=cv2.INTER_AREA)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    img = (img - _IMAGENET_MEAN) / _IMAGENET_STD
    return np.transpose(img, (2, 0, 1))


def build_model(name: str) -> tuple[nn.Module, "callable[[np.ndarray], np.ndarray]"]:
    """Factory: returns (model, preprocess_fn) for the given name."""
    name = name.lower()
    if name == "pilotnet":
        return PilotNet(), preprocess_pilotnet
    if name in ("mobilenet", "mobilenetv3", "mobilenet_v3_small"):
        return MobileNetV3Pilot(pretrained=True), preprocess_mobilenet
    raise ValueError(f"unknown model: {name!r}")
