# Wiring & Hardware

## Wiring Diagram

```
                 Raspberry Pi 5
             ┌──────────────────────┐
  Camera ───▶│ CSI (22-pin)         │
             │                      │
             │ Pin 1  (3.3 V) ──────┼──▶ PCA9685 VCC   (logic only)
             │ Pin 3  (SDA)   ──────┼──▶ PCA9685 SDA
             │ Pin 5  (SCL)   ──────┼──▶ PCA9685 SCL
             │ Pin 6  (GND)   ──────┼──▶ PCA9685 GND
             │                      │
             │ USB-C ◀──────────────┼──── Power bank (5 V / 3 A+)
             └──────────────────────┘

                 PCA9685 Board
             ┌──────────────────────┐
             │ V+  ◀────────────────────── ESC BEC output (5–6 V)
             │ GND ◀────────────────────── ESC / battery GND
             │                      │
             │ CH0 ─────────────────────▶ Steering servo (signal wire)
             │ CH1 ─────────────────────▶ ESC (signal wire)
             └──────────────────────┘
```

> **Two separate power rails on the PCA9685:**
> - **VCC** (3.3 V from Pi): powers the logic chip only
> - **V+** (5–7 V from ESC BEC or separate battery): powers the servos
>
> Most ESCs have a built-in BEC that outputs 5–6 V — connect that to V+.
> Never power servos from the Pi's 5 V pin; it cannot supply the current.

## Pin Reference (Pi 5 GPIO header)

| Pi pin | Signal | PCA9685 |
|--------|--------|---------|
| 1      | 3.3 V  | VCC     |
| 3      | SDA    | SDA     |
| 5      | SCL    | SCL     |
| 6      | GND    | GND     |

## Parts

| Component | Role |
|-----------|------|
| Raspberry Pi 5 (4 GB) | Car computer — camera capture, I2C control |
| Raspberry Pi Camera Module 3 Wide | 12 MP, 120° FOV, autofocus |
| Camera CSI ribbon cable (22-pin, 30 cm) | Pi 5 uses a smaller 22-pin CSI connector |
| PCA9685 16-channel PWM driver | I2C servo/ESC controller |
| 10 000 mAh USB-C PD power bank | Powers the Pi on the car |
| Jumper wires (F-F, M-F) | GPIO ↔ PCA9685 |

### Software versions

| Software | Version |
|----------|---------|
| Raspberry Pi OS | Bookworm, 64-bit (full) |
| Python | 3.11 |
| picamera2 | ≥ 0.3 |
| adafruit-circuitpython-servokit | ≥ 1.3 |
| OpenCV (server PC) | ≥ 4.8 |
