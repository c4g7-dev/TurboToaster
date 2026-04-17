#!/usr/bin/env python3
"""
PCA9685-based steering servo and ESC controller.

Wiring (Pi 5 GPIO header → PCA9685):
    Pin 1  (3.3 V)  → VCC      (logic power only)
    Pin 3  (SDA)    → SDA
    Pin 5  (SCL)    → SCL
    Pin 6  (GND)    → GND
    ESC BEC output  → V+       (servo/motor power — NOT from Pi!)

Channels:
    CH0 → Steering servo signal wire
    CH1 → ESC signal wire
"""

import logging

log = logging.getLogger(__name__)

STEERING_CHANNEL = 0
ESC_CHANNEL = 1

# Steering — adjust these once with test_hardware.py
STEER_CENTER = 90   # degrees: wheels pointing straight
STEER_RANGE  = 30   # ±degrees for full left/right

# Throttle — start conservative; raise THROTTLE_MAX_FWD once confirmed working
THROTTLE_MAX_FWD = 0.35   # maps to ~1.7 ms pulse (conservative forward limit)
THROTTLE_MAX_REV = -0.20  # small reverse for braking correction


class CarControl:
    """Thin wrapper around ServoKit for the car's steering servo and ESC."""

    def __init__(self):
        try:
            from adafruit_servokit import ServoKit  # type: ignore
            self._kit = ServoKit(channels=16)
            self._available = True
            log.info("PCA9685 initialised")
            self.stop()
        except Exception as exc:
            log.warning("PCA9685 not available (%s) — running in simulation mode", exc)
            self._available = False

    # ------------------------------------------------------------------
    def set_steering(self, value: float) -> None:
        """
        Set steering angle.
        value: -1.0 = full left, 0.0 = centre, +1.0 = full right
        """
        if not self._available:
            return
        value = max(-1.0, min(1.0, value))
        angle = STEER_CENTER + value * STEER_RANGE
        self._kit.servo[STEERING_CHANNEL].angle = angle

    def set_throttle(self, value: float) -> None:
        """
        Set motor throttle.
        value: 0.0 = stop, +1.0 = full forward, negative = reverse/brake
        Clamped to THROTTLE_MAX_FWD / THROTTLE_MAX_REV for safety.
        """
        if not self._available:
            return
        if value >= 0:
            throttle = min(float(value), THROTTLE_MAX_FWD)
        else:
            throttle = max(float(value), THROTTLE_MAX_REV)
        self._kit.continuous_servo[ESC_CHANNEL].throttle = throttle

    def stop(self) -> None:
        """Centre steering and cut throttle. Always safe to call."""
        self.set_steering(0.0)
        self.set_throttle(0.0)
