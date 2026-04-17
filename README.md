# TurboToaster

3D-printed RC car with AI self-driving. A Raspberry Pi 5 on the car streams camera
video over WiFi; a PC with an RTX 3080 Ti handles inference and sends drive commands
back in real time.

## Architecture

```
Pi 5 (on car)                    PC (RTX 3080 Ti)
─────────────────────            ─────────────────────────
camera → car/stream.py  ──────▶  server/drive.py
car/control.py          ◀──────  keyboard / AI model
PCA9685 → servo + ESC
```

Communication: length-prefixed TCP on port 5000.  
Pi → PC: JPEG frames. PC → Pi: JSON `{"steer": float, "throttle": float}`.

## Repository layout

```
car/
  stream.py           Main process: streams camera, receives commands
  control.py          PCA9685 servo/ESC wrapper
  test_hardware.py    First-run hardware test (I2C + servo sweep)
  requirements.txt

server/
  view_stream.py      View the Pi's camera stream (no control)
  drive.py            Manual drive: stream + keyboard control
  requirements.txt

docs/
  first-test.md       Step-by-step guide for the first connection test
  hardware.md         Wiring diagram and parts list
```

## Quick start

See **[docs/first-test.md](docs/first-test.md)** for the full step-by-step guide.

### On the Pi

```bash
sudo apt install -y python3-picamera2 python3-opencv i2c-tools
pip3 install --break-system-packages -r car/requirements.txt

# 1. Verify hardware (I2C, servo, ESC)
python3 car/test_hardware.py

# 2. Start streaming
python3 car/stream.py
```

### On the PC

```bash
pip install -r server/requirements.txt

# View stream only
python3 server/view_stream.py --host aicar.local

# Manual drive (WASD / arrow keys)
python3 server/drive.py --host aicar.local
```

**Drive keys:** W/S = throttle, A/D = steer, Space = emergency stop, Q = quit.

## Hardware

- Raspberry Pi 5 (4 GB) — 64-bit OS, 5 GHz WiFi
- Raspberry Pi Camera Module 3 Wide (12 MP, 120°)
- PCA9685 16-channel PWM driver (I2C)
- Steering servo + ESC (already on the car)
- 10 000 mAh USB-C PD power bank

Full wiring details: [docs/hardware.md](docs/hardware.md).
