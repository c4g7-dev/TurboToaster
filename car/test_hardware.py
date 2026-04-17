#!/usr/bin/env python3
"""
Hardware connectivity test — run this before anything else.

Checks:
  1. I2C bus: PCA9685 present at address 0x40
  2. Steering servo: sweep left → centre → right
  3. ESC: send neutral signal (arms most ESCs with a beep)

IMPORTANT: Lift the car off the ground before running the servo/ESC test.
"""

import subprocess
import sys
import time


def check_i2c() -> bool:
    print("\n── I2C bus scan ──")
    result = subprocess.run(
        ["i2cdetect", "-y", "1"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if "40" in result.stdout:
        print("✓  PCA9685 found at 0x40")
        return True
    print("✗  PCA9685 NOT found — check SDA/SCL wiring and that I2C is enabled")
    print("   Run: sudo raspi-config → Interface Options → I2C → Enable")
    return False


def test_steering(kit) -> None:
    print("\n── Steering servo (CH0) ──")
    print("   centre → left → centre → right → centre")
    kit.servo[0].angle = 90
    time.sleep(0.7)
    kit.servo[0].angle = 60
    time.sleep(0.7)
    kit.servo[0].angle = 90
    time.sleep(0.7)
    kit.servo[0].angle = 120
    time.sleep(0.7)
    kit.servo[0].angle = 90
    time.sleep(0.5)
    print("   Did the front wheels turn? If not, check CH0 connector and V+ power.")


def test_esc(kit) -> None:
    print("\n── ESC (CH1) ──")
    print("   Sending neutral signal (1500 µs) for 2 s — you should hear an ESC beep.")
    kit.continuous_servo[1].throttle = 0.0
    time.sleep(2)
    print("   ✓  Neutral sent.")

    ans = input("\n   Send a short forward pulse (1 s at ~15% throttle)? [y/N] ").strip().lower()
    if ans == "y":
        print("   Running... (1 s)")
        kit.continuous_servo[1].throttle = 0.15
        time.sleep(1)
        kit.continuous_servo[1].throttle = 0.0
        print("   Done. Did the motor spin?")
    else:
        print("   Skipped.")


def main() -> None:
    print("═══════════════════════════════════════")
    print("  TurboToaster — Hardware Test")
    print("═══════════════════════════════════════")

    if not check_i2c():
        sys.exit(1)

    print("\nNext: servo and ESC test.")
    print("LIFT THE CAR OFF THE GROUND before continuing.")
    input("Press Enter when ready... ")

    try:
        from adafruit_servokit import ServoKit  # type: ignore
        kit = ServoKit(channels=16)
    except Exception as exc:
        print(f"\n✗  ServoKit init failed: {exc}")
        print("   Install with: pip3 install adafruit-circuitpython-servokit")
        sys.exit(1)

    test_steering(kit)
    test_esc(kit)

    print("\n═══════════════════════════════════════")
    print("  Hardware test complete.")
    print()
    print("  Next steps:")
    print("    Pi:  python3 stream.py")
    print("    PC:  python3 server/view_stream.py --host aicar.local")
    print("═══════════════════════════════════════\n")


if __name__ == "__main__":
    main()
