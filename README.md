# TurboToaster

3D-printed RC car with AI self-driving. A Raspberry Pi 5 on the car streams camera
video over WiFi; a remote PC with an **RTX 3090** — living at a separate physical
location — handles inference and sends drive commands back. Because that inference
PC is off-site, its round-trip latency stacks on top of the inherent video-frame
latency, which will stay interesting to tune as driving speed goes up.

To keep a low-latency escape hatch, a second **LAN-local manual-control** channel
is also provided. Any machine on the same WiFi as the car (laptop, phone-tethered
box, another Pi) can attach to it with a small pre-shared auth keyword and grab
the wheel. While the LAN override is active the Pi ignores the remote AI's
commands, so the two don't fight.

## Architecture

```
 Pi 5 (on car)                       Remote PC (RTX 3090, off-site)
 ──────────────────                   ──────────────────────────────
 camera ─▶ car/stream.py  ─TCP 5000─▶ ai/infer.py     (fast loop, ~30 Hz)
                                      server/drive.py (manual + recorder)
 control.py              ◀──────────  {steer, throttle, ts, seq} JSON
 PCA9685 → servo + ESC                ai/perceive.py  (slow loop, YOLOv8n)
        ▲                             ai/train.py     (offline, from datasets/)
        │  TCP 5001 (auth'd, low-latency, LAN-only)
        │
 server/manual_control.py  ──  laptop/phone on the same WiFi
```

Communication: length-prefixed TCP.
- Pi → PC: JPEG frames on port **5000** (default **480×270 @ 30 fps**).
- PC → Pi: JSON `{"steer": float, "throttle": float, "ts": unix_seconds, "seq": int}`
  on port **5000** (AI) or port **5001** (LAN manual-override, after an
  `{"auth": "<keyword>"}` handshake).
- The Pi drops AI commands whose `ts` is older than 300 ms (wall-clock), and
  ignores out-of-order / duplicate `seq` values, so a WAN hiccup can't cause
  the car to act on stale predictions once the link recovers. Clocks on both
  ends should be NTP-synced.
- The Pi streams with a **newest-frame-wins** sender: if the network falls
  behind, old frames are overwritten in a single-slot queue rather than
  queued up, which keeps glass-to-wheel latency bounded by the *current*
  link speed rather than by backlog.

Manual-override priority: whenever a LAN manual command arrives it is applied
immediately and any remote AI commands are ignored for a short grace period
(~0.5 s) so the remote AI can't "fight" the local driver.

## Repository layout

```
car/
  stream.py           Main process: streams camera, accepts AI + LAN commands
  control.py          PCA9685 servo/ESC wrapper
  test_hardware.py    First-run hardware test (I2C + servo sweep)
  requirements.txt

server/
  view_stream.py      View the Pi's camera stream (no control)
  drive.py            AI / keyboard drive client (port 5000, with video)
  manual_control.py   LAN-local manual-override client (port 5001, no video)
  recorder.py         Dataset recorder (frames + commands, Donkey-compatible)
  requirements.txt

ai/
  model.py            PilotNet + MobileNetV3 behavior-cloning models
  dataset.py          Loader for recorded sessions and Donkey tubs
  train.py            Training loop
  infer.py            Fast loop: runs a trained model, drives the car
  perceive.py         Slow loop: optional YOLOv8n sidecar
  requirements.txt
  README.md

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

# 2. Start streaming. Pick any shared keyword — the LAN manual-override
#    listener is enabled only when a key is configured.
export TURBOTOASTER_CONTROL_KEY='pick-a-shared-keyword'
python3 car/stream.py
```

### On the remote AI PC (RTX 3090, off-site)

```bash
pip install -r server/requirements.txt

# View stream only
python3 server/view_stream.py --host aicar.local

# Manual drive with video (WASD / arrow keys) — this is the AI-channel client
python3 server/drive.py --host aicar.local

# Same, but also record a training dataset under ./datasets/
python3 server/drive.py --host aicar.local --record datasets

# Train a behavior-cloning model on collected data, then drive autonomously
pip install -r ai/requirements.txt
python3 ai/train.py --data datasets/session_* --model pilotnet --epochs 30
python3 ai/infer.py --host aicar.local --checkpoint ai/checkpoints/best.pt --show
```

### On any LAN-local machine (low-latency manual override)

```bash
pip install -r server/requirements.txt

export TURBOTOASTER_CONTROL_KEY='pick-a-shared-keyword'   # same as the Pi
python3 server/manual_control.py --host aicar.local
# or pass the key explicitly:
python3 server/manual_control.py --host 192.168.1.42 --key pick-a-shared-keyword
```

**Drive keys:** W/S = throttle, A/D = steer, Space = emergency stop,
R = release override (hand back to the AI), Q = quit.

## AI self-driving

The `ai/` directory contains a self-contained behavior-cloning stack:

1. **Collect** driving data with `server/drive.py --record datasets` — each
   manual drive becomes a `datasets/session_<timestamp>/` tub with
   `images/` + `log.csv` (and Donkey-compatible `record_*.json` sidecars).
2. **Train** a small CNN on one or more sessions / Donkey tubs with
   `ai/train.py` (PilotNet ~250k params or MobileNetV3-small ~1.5M params).
3. **Drive** autonomously with `ai/infer.py`, which connects to the Pi just
   like `drive.py` does, runs the trained model at FP16 on CUDA, and sends
   stamped `{steer, throttle, ts, seq}` commands back.
4. **Optional perception sidecar** (`--perceive`) runs YOLOv8n in a
   background thread on every Nth frame for object detection; detections
   are currently only reported, not yet fed into the controller.

Full walk-through: [ai/README.md](ai/README.md).

## Hardware

- Raspberry Pi 5 (4 GB) — 64-bit OS, 5 GHz WiFi
- Raspberry Pi Camera Module 3 Wide (12 MP, 120°)
- PCA9685 16-channel PWM driver (I2C)
- Steering servo + ESC (already on the car)
- 10 000 mAh USB-C PD power bank

Full wiring details: [docs/hardware.md](docs/hardware.md).
