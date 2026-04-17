# First Connection Test

Before the car drives autonomously, run through these steps to confirm every layer
works: I2C, servo/ESC, WiFi, camera stream, and manual keyboard control.

## Prerequisites

- Raspberry Pi 5 running Raspberry Pi OS 64-bit (full), connected to WiFi
- PCA9685 wired up — see [hardware.md](hardware.md)
- Camera connected via the 22-pin CSI ribbon cable
- I2C enabled on the Pi (`sudo raspi-config` → Interface Options → I2C → Enable)

---

## Step 1 — Find the Pi on your network

From your PC:
```bash
ping aicar.local
```

If you did not set the hostname to `aicar` during first boot, find the IP address
by checking your router's device list, or:
```bash
# Linux/macOS
nmap -sn 192.168.1.0/24 | grep -i raspberry
# Windows (PowerShell)
arp -a | findstr /i "b8-27 dc-a6 e4-5f d8-3a"   # common Pi MAC prefixes
```

SSH in:
```bash
ssh pi@aicar.local      # default user: pi, password: raspberry
```

---

## Step 2 — Install dependencies on the Pi

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-opencv i2c-tools git

pip3 install --break-system-packages \
    adafruit-circuitpython-pca9685 \
    adafruit-circuitpython-servokit

# Clone the repo
git clone https://github.com/c4g7-dev/TurboToaster.git
cd TurboToaster
```

---

## Step 3 — Hardware test (I2C + servo sweep)

**Lift the car off the ground before running this.**

```bash
python3 car/test_hardware.py
```

Expected output:
```
── I2C bus scan ──
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00: ...
40: 40 ...
✓  PCA9685 found at 0x40
── Steering servo (CH0) ──
   centre → left → centre → right → centre
   Did the front wheels turn?
── ESC (CH1) ──
   Sending neutral signal for 2 s — you should hear an ESC beep.
```

- Front wheels should sweep left and right.
- ESC should beep once when it receives the neutral signal (arming beep).

If `0x40` is not found: check SDA → Pin 3, SCL → Pin 5, VCC → Pin 1, GND → Pin 6,
and confirm I2C is enabled.

---

## Step 4 — Start the stream on the Pi

```bash
python3 car/stream.py
```

Output:
```
10:32:11  INFO      Listening on 0.0.0.0:5000  [640x480 @ 30 fps] — waiting for PC...
```

Leave this running and switch to your PC.

---

## Step 5 — View the stream on your PC

Install dependencies once:
```bash
pip install opencv-python numpy
```

Then:
```bash
python3 server/view_stream.py --host aicar.local
# or use the IP address if mDNS isn't working:
python3 server/view_stream.py --host 192.168.1.42
```

A window should open showing the live camera feed.  
Target: **≥ 25 FPS** on a 5 GHz connection.

Press **Q** or **Esc** to close.

---

## Step 6 — Manual drive test

**Keep the car on a stand / wheels off the ground for the first test.**

```bash
python3 server/drive.py --host aicar.local
```

| Key | Action |
|-----|--------|
| W / Up | Increase throttle |
| S / Down | Decrease throttle / reverse |
| A / Left | Steer left |
| D / Right | Steer right |
| Space | Emergency stop |
| Q / Esc | Quit |

Start with just steering (A/D) and confirm the wheels respond. Then test a single
short W press with the car still elevated before putting it on the ground.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ping aicar.local` fails | Pi not on WiFi, or mDNS not resolving | Connect via IP address; check WiFi credentials |
| `0x40` not in I2C scan | Wiring or I2C disabled | Check SDA/SCL/VCC/GND; run `sudo raspi-config` |
| Servo does not move | No V+ power to PCA9685 | Connect ESC BEC output to PCA9685 V+ |
| Stream connects but no image | Camera cable problem | Re-seat CSI ribbon on both ends |
| Low FPS or choppy stream | On 2.4 GHz WiFi | Switch Pi and PC to the 5 GHz band |
| ESC no arming beep | ESC needs full-range calibration | Consult your ESC manual for calibration steps |
