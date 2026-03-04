# 🏎️ AI Self-Driving RC Car — School Project Overview

> **Goal:** Upgrade an existing 3D-printed RC car (with servos & ESC) into an
> AI-controlled autonomous vehicle. The car carries only a cheap **Raspberry Pi 5 +
> camera**. All AI processing runs on your **home PC (RTX 3080 Ti)** over WiFi,
> or optionally on a **cloud GPU** service.

---

## 📐 System Architecture — Remote-Brain Design

The car is "dumb" on purpose — it just streams camera frames and executes commands.
Your powerful home PC (or cloud server) does all the AI thinking.

```
  ON THE CAR (~€150)                         YOUR HOME PC (RTX 3080 Ti)
 ┌──────────────────────────┐               ┌──────────────────────────────┐
 │  3D-Printed RC Chassis   │               │   Windows/Linux PC           │
 │  (ESC + Servo already    │               │   RTX 3080 Ti (12GB VRAM)    │
 │   installed)             │               │                              │
 │                          │   WiFi/LAN    │  ┌──────────────────────┐    │
 │  ┌────────┐  ┌────────┐ │   5GHz WiFi   │  │  AI MODEL (GPU)      │    │
 │  │ Camera │─▶│ Rasp.  │─┼──────────────▶│  │  PyTorch / OpenCV    │    │
 │  │ (CSI)  │  │ Pi 5   │ │  JPEG stream  │  │  ResNet / Linear     │    │
 │  └────────┘  │ 4GB    │◀┼──────────────◀│  │  ~100+ FPS inference │    │
 │              │        │ │  {steer,throt} │  └──────────┬───────────┘    │
 │  ┌────────┐  │  I2C   │ │               │             │                │
 │  │PCA9685 │◀─│  bus   │ │               │  Also used for:              │
 │  │  PWM   │  └────────┘ │               │  • Training (minutes!)       │
 │  └───┬────┘       │     │               │  • Data collection UI        │
 │      │        USB-C     │               │  • Live monitoring           │
 │  ┌───▼───┐   power      │               │                              │
 │  │Servo  │              │               └──────────────────────────────┘
 │  │+ ESC  │              │
 │  └───────┘              │               ALTERNATIVE: Cloud GPU
 └──────────────────────────┘               (Colab Free, Vast.ai, RunPod)
```

---

## ✅ What You Already Have

| Component           | Status |
|---------------------|--------|
| 3D-printed chassis  | ✅      |
| DC motor / brushless motor | ✅      |
| ESC (Electronic Speed Controller) | ✅      |
| Steering servo      | ✅      |
| Wheels & drivetrain | ✅      |
| Battery pack (for motor) | ✅      |
| **Home PC with RTX 3080 Ti** | ✅      |

---

## 🛒 Exact Parts to Buy — Reichelt Elektronik Shopping List

Everything below goes **on top of** your existing 3D-printed car.
Search each **Reichelt Article#** at [reichelt.de](https://www.reichelt.de) to find the exact product.

### Core Components (Required)

| # | Component | Article# | Direct Product Link | Price | Why |
|---|-----------|----------|---------------------|-------|-----|
| 1 | **Raspberry Pi 5 — 4 GB (single board!)** | `RASP PI 5 B 4GB` | [🔗 Reichelt Product Page](https://www.reichelt.com/de/en/shop/product/raspberry_pi_5_b_4x_2_4_ghz_4_gb_ram_wlan_bt-359842) | €88.50 | The brain on the car. 2.4 GHz quad-core, built-in WiFi 5GHz, Bluetooth 5.0. **Single board only — NOT a bundle/kit!** The 4GB is enough since AI runs remotely. |
| 2 | **Raspberry Pi Camera Module 3 Wide** | `RASP CAM 3 W` | [🔗 Reichelt Product Page](https://www.reichelt.com/de/en/shop/product/raspberry_pi_-_camera_12mp_120_v3-339260) | €37.95 | 12MP Sony IMX708, 120° wide-angle FOV. Autofocus + HDR. Uses MIPI CSI-2 connector. Wide angle sees more track = better AI. |
| 3 | **Raspberry Pi 5 CSI Camera Cable 30cm** | `RASP CAM FPC 30` | [🔗 Reichelt Product Page](https://www.reichelt.com/de/en/shop/product/raspberry_pi_-_ribbon_cable_for_camera_30_cm-360119) | €2.25 | Pi 5 uses smaller 22-pin CSI connector — this is the matching FPC ribbon cable for Pi 5 cameras. 30cm is a good length for an RC car. |
| 4 | **PCA9685 16-Ch Servo Driver (Adafruit)** | `DEBO MOTODRIVER4` | [🔗 Reichelt Product Page](https://www.reichelt.com/de/en/shop/product/developer_boards_-_servo_driver_16_channel_12_bit_pca9685-235525) | €18.80 | I2C-controlled 16-channel 12-bit PWM board. CH0 → steering servo, CH1 → ESC signal. 3.3V logic compatible with Pi 5. |
| 5 | **MicroSD 32GB with Raspberry Pi OS pre-installed** | `RPI5 OS 32GB` | [🔗 Reichelt Product Page](https://www.reichelt.com/de/en/shop/product/raspberry_pi_-_os_trixie_32gb_microsd_card_pre-installed-362344) | €16.70 | A2-class 32GB card with Pi OS Trixie pre-installed — just plug in and boot, no flashing needed! |
| 6 | **USB-C Power Supply for Pi 5 (27W, 5.1V/5A)** | `GOOBAY 74437` | [🔗 Reichelt Product Page](https://www.reichelt.com/de/en/shop/product/plug-in_power_supply_for_raspberry_pi_5_5_1_v_5_0_a_usb_type--413878) | €10.90 | 5.1V / 5A USB-C — for bench testing & development. For the car, use a power bank (see below). |
| 7 | **ANSMANN USB-C Power Bank 10000mAh PD** | `ANS 1700-0148` | [🔗 Reichelt Product Page](https://www.reichelt.com/de/en/shop/product/ansmann_powerbank_10000_mah_pb320pd-321590) | €28.40 | Powers the Pi 5 on the car. USB-C PD output (5-12V). 10000mAh = ~3-4 hours runtime. |
| 8 | **Jumper Wire Set 140 pcs (rigid, multi-color)** | `STECKBOARD DBS` | [🔗 Reichelt Product Page](https://www.reichelt.com/de/en/shop/product/jumper_wire_jumper_set_140_pieces-79056) | €4.70 | 140 breadboard jumper wires in various lengths. For connecting PCA9685 to Pi 5 I2C pins (SDA/SCL/VCC/GND). |

### Optional but Recommended

| # | Component | Article# | Direct Product Link | Price | Why |
|---|-----------|----------|---------------------|-------|-----|
| 9 | **HC-SR04 Ultrasonic Distance Sensor** | `DEBO SEN ULTRA` | [🔗 Reichelt Product Page](https://www.reichelt.com/de/en/shop/product/developer_boards_-_ultrasonic_distance_sensor_hc-sr04-161487) | €3.45 | Front collision detection. Measures distance 2–400cm. Emergency stop if obstacle <20cm. |
| 10 | **0.96" OLED Display (SSD1306, I2C)** | `DEBO OLED2 0.96` | [🔗 Reichelt Product Page](https://www.reichelt.com/de/en/shop/product/developer_boards_-_display_0_96_oled_display_ssd1306-266107) | €6.99 | Shows IP address, WiFi signal, FPS, AI mode on the car. Nice for demos. |
| 11 | **M2.5 Standoff Set (Nylon or Brass)** | `DELOCK 18305` | [🔗 Reichelt Search](https://www.reichelt.com/de/en/shop/search/delock%2018305) | ~€4 | For securely mounting the Pi 5 on your chassis. |
| 12 | **USB Gamepad Logitech F310** | `LOGITECH F310` | [🔗 Reichelt Product Page](https://www.reichelt.com/de/en/shop/product/gamepad-128562) | €27.95 | Plug into your HOME PC for steering the car during data collection. Much smoother than keyboard. Analog sticks = analog steering. |

### Not from Reichelt (3D Print Yourself!)

| Part | Notes |
|------|-------|
| **Camera mount** | 3D-print a bracket angled ~15° down, mounted at the front/top of the car |
| **Raspberry Pi 5 mount plate** | 3D-print a base plate with M2.5 holes matching Pi 5 mounting pattern (58×49mm) |
| **Power bank holder** | 3D-print a cradle or use velcro straps to keep the power bank secure |

---

### 💰 Total Cost Summary

| What | Cost |
|------|------|
| Core components (#1–#8) | **~€208** |
| Optional extras (#9–#12) | ~€42 |
| Shipping (Reichelt, within DE) | ~€6 |
| **Total to get driving** | **~€214** |
| **Total with all extras** | **~€256** |

> Your RTX 3080 Ti at home replaces what would otherwise be a €90–130 Jetson Nano
> on the car. You get faster AI (~300 FPS vs 20 FPS on Jetson) without any extra cost.

---

## 🌐 How the AI Controls the Car — Step by Step

### Live Driving Loop (Real-Time)

```
  1. Camera captures frame (RPi 5)           ~5ms
     │
     2. Compress to JPEG, send over WiFi      ~10ms
     │         (TCP socket to your PC)
     ▼
  3. PC receives frame                        ~1ms
     │
     4. AI Model runs inference (RTX 3080Ti)  ~5ms  (ResNet18 = ~3ms!)
     │   Input: 224×224 RGB image
     │   Output: steering (-1.0 to +1.0)
     │           throttle (0.0 to +1.0)
     │
     5. PC sends commands back over WiFi      ~1ms
     │
     ▼
  6. RPi receives {steer, throttle}           ~1ms
     │
     7. PCA9685 sets PWM on servo + ESC       ~1ms
     │
     ▼
  8. Car turns + accelerates/brakes!

  TOTAL LOOP: ~25-40ms ≈ 25-40 FPS on local WiFi
              (WAY faster than needed for RC car speeds)
```

### Training Pipeline (One-Time)

```
  Step 1: You drive the car manually
          (gamepad/keyboard on your PC)
          │
          ▼
  Step 2: Camera frames + your steering/throttle
          are recorded as training data
          (5,000 – 20,000 image pairs)
          │
          ▼
  Step 3: Train neural network on your RTX 3080 Ti
          (takes 5-15 minutes for a ResNet18 model!)
          │
          ▼
  Step 4: Load trained model → start AI driving loop
          (see above)
```

---

## 💻 AI Processing Options — Your PC vs Cloud

### Option A — Your Home PC (RTX 3080 Ti) ⭐ Best Choice

| Aspect | Details |
|--------|---------|
| **GPU** | RTX 3080 Ti — 12GB VRAM, 10240 CUDA cores |
| **Training speed** | ResNet18 on 10k images: **~5-10 min** |
| **Inference speed** | ResNet18: **~3ms per frame (~300 FPS)** — absurdly fast |
| **Cost** | **€0** — you already own it |
| **Latency to car** | **~10-30ms** round-trip on 5GHz WiFi (same room) |
| **Setup needed** | Install Python, PyTorch with CUDA, OpenCV |

**This is your best option.** Your RTX 3080 Ti is overkill for this project in the
best way possible. Training takes minutes, inference is near-instant.

```bash
# One-time setup on your PC (Windows or Linux)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install opencv-python numpy flask pygame
```

### Option B — Google Colab (Free GPU) — For Training Only

| Aspect | Details |
|--------|---------|
| **GPU** | NVIDIA T4 (free) or A100 (Colab Pro, ~€11/mo) |
| **Good for** | Training models when you're not at home |
| **NOT good for** | Live driving (too much latency to the car) |
| **Cost** | **Free** (limited) or ~€11/mo Pro |
| **How** | Upload training data to Google Drive → train in Colab notebook → download model → run inference on any local PC |

### Option C — Vast.ai / RunPod (Cloud GPU Rental)

| Provider | GPU | Price | Use Case |
|----------|-----|-------|----------|
| **Vast.ai** | RTX 3090 / RTX 4090 | ~€0.15–0.50/hr | Training when you need more power |
| **RunPod** | RTX 3090 / A100 | ~€0.30–0.80/hr | Training + potentially live server |
| **Lambda Cloud** | A10 / A100 | ~€0.50–1.50/hr | Serious training at scale |

> **Recommendation:** Use your RTX 3080 Ti for everything. It's more powerful than
> most cloud free tiers. Use Colab only if you want to train at school without your PC.

### Option D — School PC (No GPU needed for demo!)

Even a **laptop without a GPU** can run inference for a simple linear model at ~10-30 FPS
using just the CPU. Training will be slow, but for demos at school, it works perfectly.

---

## 💻 Codebase Recommendation

### Primary: `sidroopdaska/SelfDrivingRCCar` ⭐ (Best fit for WiFi remote-brain)

> **Repository:** https://github.com/sidroopdaska/SelfDrivingRCCar

| Feature | Details |
|---------|---------|
| Architecture | **RPi streams video → Remote PC runs AI → sends commands** |
| Language | Python 3 |
| DL Framework | OpenCV DNN (easy to swap to PyTorch) |
| On RPi | `stream_video.py` + `stream_sensor_data.py` |
| On PC | `collect_data.py` (training) + `auto_driver.py` (self-driving) |
| Extras | Stop sign detection, traffic light detection, ultrasonic collision avoidance |
| Complexity | Simple — great for school project |

**Why this one?**
- Built exactly for the "RPi streams → PC decides" architecture you're using
- Simple Python scripts, easy to understand and modify
- Includes obstacle/sign detection for impressive demos
- You'll upgrade the simple MLP model to a proper CNN/ResNet for better performance

### Also grab training models from: `caipeide/autorace`

> **Repository:** https://github.com/caipeide/autorace

The training pipeline and model architectures (Linear, ResNet18, RNN) from this repo
are excellent. You can port them to run on your PC while the RPi handles streaming.
The `train.py` and `ai_drive_models.py` files contain ready-to-use PyTorch models.

### Framework alternative: Donkeycar

> **Repository:** https://github.com/autorope/donkeycar

Largest community, supports RPi 5, and has built-in remote driving modes.
More complex to set up but more features out of the box.

---

## 🔧 Wiring Diagram (On the Car)

```
                       RASPBERRY PI 5
                    ┌─────────────────────┐
                    │                     │
     Camera ───────▶│  CSI Port           │
     (CSI cable)    │  (22-pin connector) │
                    │                     │
     WiFi (built-in)│  WiFi 802.11ac ────┼──▶ 5GHz → Your home router
                    │  (dual-band)       │       → Your PC receives frames
                    │                     │
                    │  GPIO Pin 3 (SDA) ──┼──▶ PCA9685 SDA
                    │  GPIO Pin 5 (SCL) ──┼──▶ PCA9685 SCL
                    │  GPIO Pin 1 (3.3V) ─┼──▶ PCA9685 VCC (logic power)
                    │  GPIO Pin 6 (GND) ──┼──▶ PCA9685 GND
                    │                     │
                    │  USB-C ◀────────────┼──── Power Bank (5V / 3A+)
                    └─────────────────────┘

                       PCA9685 BOARD
                    ┌─────────────────────┐
                    │  V+ ◀──────────────────── Servo/ESC battery (5-7V)
                    │  GND ◀─────────────────── Battery GND
                    │                     │
                    │  CH0 ──────────────────▶ Steering Servo signal wire
                    │  CH1 ──────────────────▶ ESC signal wire
                    └─────────────────────┘

  IMPORTANT: The PCA9685 has TWO power inputs:
  • VCC (3.3V from Pi) — for the logic chip
  • V+ (5-7V from battery/BEC) — for actually powering the servos
  • If your ESC has a BEC output (most do), use that for V+
```

---

## 🚀 Project Workflow (Step-by-Step)

### Phase 1 — Hardware Assembly (Week 1–2)

1. **Mount the Raspberry Pi 5** onto the chassis
   - 3D-print a mount plate with M2.5 holes (Pi 5 pattern: 58mm × 49mm)
   - Secure with M2.5 nylon standoffs to avoid short circuits
2. **Connect the PCA9685** to the Pi 5:

   ```
   Pi 5 GPIO Header (relevant pins):
   Pin 1  = 3.3V Power    → PCA9685 VCC
   Pin 3  = GPIO 2 (SDA)  → PCA9685 SDA
   Pin 5  = GPIO 3 (SCL)  → PCA9685 SCL
   Pin 6  = Ground         → PCA9685 GND
   ```

3. **Connect servos to PCA9685:**
   - Channel 0 → Steering servo (3-wire: signal, V+, GND)
   - Channel 1 → ESC signal wire only (ESC has its own power)
4. **Mount and connect the camera** via the 22→15pin CSI ribbon cable
5. **Attach the power bank** (velcro or 3D-printed holder), plug USB-C into Pi 5

### Phase 2 — Software Setup (Week 2–3)

**On the Raspberry Pi 5:**
```bash
# 1. Flash Raspberry Pi OS (64-bit, Bookworm) onto MicroSD with Raspberry Pi Imager
#    → Enable SSH, set WiFi, set hostname to "aicar" during flashing
#    → Download Imager: https://www.raspberrypi.com/software/

# 2. Boot, SSH in, and install dependencies:
ssh pi@aicar.local
sudo apt update && sudo apt install -y python3-pip python3-opencv python3-picamera2 i2c-tools
pip3 install adafruit-circuitpython-pca9685 adafruit-circuitpython-servokit

# 3. Enable I2C:
sudo raspi-config  # → Interface Options → I2C → Enable

# 4. Test I2C connection (should show address 0x40 for PCA9685):
i2cdetect -y 1

# 5. Clone the codebase:
git clone https://github.com/sidroopdaska/SelfDrivingRCCar
cd SelfDrivingRCCar
```

**On your Home PC (RTX 3080 Ti):**
```bash
# 1. Install Python 3.10+ and PyTorch with CUDA:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install opencv-python numpy pygame flask

# 2. Clone the same repo:
git clone https://github.com/sidroopdaska/SelfDrivingRCCar
cd SelfDrivingRCCar

# 3. Also grab the better models from autorace:
git clone https://github.com/caipeide/autorace
```

**Calibrate steering & throttle:**
```python
# Run on the RPi — test your servo range:
from adafruit_servokit import ServoKit
kit = ServoKit(channels=16)

# Steering: find left/center/right angles
kit.servo[0].angle = 90    # Center (adjust until wheels are straight)
kit.servo[0].angle = 60    # Full left (adjust to your servo)
kit.servo[0].angle = 120   # Full right (adjust to your servo)

# ESC: find neutral and forward (CAREFUL — wheels off ground first!)
kit.continuous_servo[1].throttle = 0    # Neutral / stop
kit.continuous_servo[1].throttle = 0.15 # Gentle forward (adjust!)
```

### Phase 3 — Data Collection (Week 3–4)

1. **Build a track** — tape on the floor, cardboard barriers, or printed lane markings
2. **Start streaming on the RPi:**
   ```bash
   python3 rpi/stream_video.py
   ```
3. **On your PC — start recording:**
   ```bash
   python3 server/collect_data.py
   ```
4. **Drive with keyboard or gamepad** — the PC saves (image, steering, throttle) pairs
5. **Collect 10–20 laps** of clean driving (~5,000–20,000 images)
6. **Tip:** Go slow at first, delete bad data (crashes), add variety (different obstacle positions)

### Phase 4 — Model Training (Week 4–5)

**On your RTX 3080 Ti PC:**

```bash
# --- Option 1: Use the included MLP training ---
cd SelfDrivingRCCar/server
python3 mlp_training.py

# --- Option 2: Use the better ResNet18 from autorace (recommended!) ---
cd autorace
python3 manage.py train --model models/resnet18.pth --type resnet18

# Training takes ~5-15 minutes on your RTX 3080 Ti for 10k images.
# That's it. Seriously. The 3080 Ti is a beast for this.
```

**On Google Colab (alternative, if at school):**
```python
# Upload data_set/ to Google Drive, then in Colab:
from google.colab import drive
drive.mount('/content/drive')
# ... load data, define model, train — takes ~15-30 min on free T4
```

### Phase 5 — AI Driving! (Week 5–6)

1. **On the RPi — start camera stream + sensor stream:**
   ```bash
   python3 rpi/stream_video.py &
   python3 rpi/stream_sensor_data.py &    # if using ultrasonic sensor
   ```

2. **On your PC — start the AI autopilot:**
   ```bash
   # Loads trained model, receives video, sends back steering + throttle
   python3 server/auto_driver.py
   ```

3. **Watch your car drive itself!** 🎉

4. **Iterate:** Collect more data where it fails, retrain (5 min), test again.

---

## 🧠 How the AI Works (Simplified)

```
  Camera Image (from RPi 5, sent over WiFi)
         │
         ▼  (received by your RTX 3080 Ti PC)
  ┌──────────────┐
  │ Convolutional │   The network learns to "see":
  │ Neural Net    │   - Lane edges / tape lines
  │ (ResNet18)    │   - Track boundaries
  │               │   - Obstacles / other cars
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Fully        │   The network decides:
  │ Connected    │   - How much to steer
  │ Layers       │   - How fast to go
  └──────┬───────┘
         │
         ▼  (sent back to RPi over WiFi)
  Steering: -1.0 (full left) ◀──────▶ +1.0 (full right)
  Throttle:  0.0 (stop)      ──────▶ +1.0 (full speed)
         │
         ▼
  PCA9685 → Servo turns wheels → ESC powers motor → Car moves!
```

**Imitation learning in 3 sentences:**
1. You drive the car manually — the system records what you see (camera) and what you do (steering/throttle)
2. A neural network trains to copy your behavior: "when I see THIS image, I should steer THIS much"
3. Once trained, the AI drives by watching live camera frames and predicting what a human would do

---

## 📋 Complete Reichelt Order List (Copy-Paste Ready)

Click each link to go directly to the product page → add to cart → done.

| # | Article# | Direct Product Link | What it is | Price |
|---|----------|---------------------|-----------|-------|
| 1 | `RASP PI 5 B 4GB` | [🔗 Pi 5 4GB (single board)](https://www.reichelt.com/de/en/shop/product/raspberry_pi_5_b_4x_2_4_ghz_4_gb_ram_wlan_bt-359842) | Raspberry Pi 5, 4GB RAM — **single board, NOT a bundle** | €88.50 |
| 2 | `RASP CAM 3 W` | [🔗 Camera Module 3 Wide](https://www.reichelt.com/de/en/shop/product/raspberry_pi_-_camera_12mp_120_v3-339260) | Camera Module 3 Wide, 12MP, 120° FOV | €37.95 |
| 3 | `RASP CAM FPC 30` | [🔗 CSI Cable 30cm (Pi 5)](https://www.reichelt.com/de/en/shop/product/raspberry_pi_-_ribbon_cable_for_camera_30_cm-360119) | FPC ribbon cable for Pi 5 camera, 30cm | €2.25 |
| 4 | `DEBO MOTODRIVER4` | [🔗 PCA9685 Servo Driver](https://www.reichelt.com/de/en/shop/product/developer_boards_-_servo_driver_16_channel_12_bit_pca9685-235525) | Adafruit PCA9685 16-ch servo driver breakout | €18.80 |
| 5 | `RPI5 OS 32GB` | [🔗 MicroSD 32GB + Pi OS](https://www.reichelt.com/de/en/shop/product/raspberry_pi_-_os_trixie_32gb_microsd_card_pre-installed-362344) | 32GB MicroSD with Raspberry Pi OS pre-installed | €16.70 |
| 6 | `GOOBAY 74437` | [🔗 Pi 5 USB-C PSU 27W](https://www.reichelt.com/de/en/shop/product/plug-in_power_supply_for_raspberry_pi_5_5_1_v_5_0_a_usb_type--413878) | Goobay 5.1V/5A USB-C power supply (for desk testing) | €10.90 |
| 7 | `ANS 1700-0148` | [🔗 ANSMANN PowerBank PD](https://www.reichelt.com/de/en/shop/product/ansmann_powerbank_10000_mah_pb320pd-321590) | ANSMANN 10000mAh USB-C PD power bank (for the car) | €28.40 |
| 8 | `STECKBOARD DBS` | [🔗 Jumper Wire Set 140pc](https://www.reichelt.com/de/en/shop/product/jumper_wire_jumper_set_140_pieces-79056) | 140-piece breadboard jumper wire set | €4.70 |
| | | | | |
| | | | **Core total** | **~€208** |
| | | | | |
| 9 | `DEBO SEN ULTRA` | [🔗 HC-SR04 Ultrasonic](https://www.reichelt.com/de/en/shop/product/developer_boards_-_ultrasonic_distance_sensor_hc-sr04-161487) | HC-SR04 ultrasonic sensor (optional) | €3.45 |
| 10 | `DEBO OLED2 0.96` | [🔗 0.96" OLED Display](https://www.reichelt.com/de/en/shop/product/developer_boards_-_display_0_96_oled_display_ssd1306-266107) | 0.96" OLED I2C display, SSD1306 (optional) | €6.99 |
| 11 | `DELOCK 18305` | [🔗 Search Standoffs](https://www.reichelt.com/de/en/shop/search/delock%2018305) | M2.5 standoff assortment (optional) | ~€4 |
| 12 | `LOGITECH F310` | [🔗 Logitech F310 Gamepad](https://www.reichelt.com/de/en/shop/product/gamepad-128562) | USB gamepad for data collection (optional) | €27.95 |
| | | | | |
| | | | **Grand total (all)** | **~€250** |
| | | | + Shipping | ~€6 |

>> **Note:** Reichelt article numbers occasionally change. If a search doesn't find
> the exact product, search the key terms (e.g., "Raspberry Pi 5 4GB", "PCA9685",
> "Pi Camera 3 Wide").

---

### 🛒 Alternative Shops (if Reichelt is sold out)

Reichelt is often sold out on popular items. Here are **direct product links** on two other great German shops so you can order immediately:

#### BerryBase.de — Official Raspberry Pi Reseller (Berlin)

| # | Component | BerryBase Direct Link | Price |
|---|-----------|----------------------|-------|
| 1 | Raspberry Pi 5 4GB | [🔗 BerryBase Search: Pi 5](https://www.berrybase.de/search?search=raspberry+pi+5+4gb) | ~€85–90 |
| 2 | Camera Module 3 Wide 12MP | [🔗 BerryBase Product](https://www.berrybase.de/raspberry-pi-camera-module-3-wide-12mp) | €39.90 |
| 3 | Camera Cable 300mm (Std→Mini, Pi 5) | [🔗 BerryBase Product](https://www.berrybase.de/raspberry-pi-camera-cable-standard-mini-300mm) | €2.30 |
| 4 | PCA9685 16-Ch Servo Driver (BerryBase) | [🔗 BerryBase Product](https://www.berrybase.de/berrybase-16-kanal-pwm-servo-treiber-board-pca9685-i2c-12bit-1-6khz-3-3-5v) | **€6.50** ⭐ |
| 9 | HC-SR04 Ultraschall Sensor | [🔗 BerryBase Product](https://www.berrybase.de/hc-sr04-ultraschall-sensor) | **€1.49** ⭐ |
| 10 | 0.96" OLED Display (I2C, gelb/blau) | [🔗 BerryBase Product](https://www.berrybase.de/0.96-128x64-oled-display-modul-zweifarbig-gelb-blau-spi-i2c-interface-vertikale-stiftleiste) | €7.80 |

> ⭐ = **significantly cheaper than Reichelt!** The BerryBase PCA9685 is €6.50 vs €18.80, and the HC-SR04 is €1.49 vs €3.45.
> BerryBase ships from Berlin, delivery 1–3 days within DE. Shipping ~€4.95.

#### Botland.de — Large Electronics Shop (ships from Poland, 1–3 days to DE)

| # | Component | Botland Search Link | Notes |
|---|-----------|---------------------|-------|
| — | Raspberry Pi 5 | [🔗 Botland: Raspberry Pi 5](https://botland.de/1654-raspberry-pi-5) | Check availability — often in stock when others aren't |
| — | All Pi accessories | [🔗 Botland: Raspberry Pi](https://botland.de/399-raspberry-pi) | Camera, cables, HATs |
| — | Sensors & modules | [🔗 Botland: Sensoren](https://botland.de/6-sensoren) | HC-SR04, PCA9685, OLED |
| — | Robotics parts | [🔗 Botland: Roboter](https://botland.de/7-roboter-und-mechanik) | Motors, servo drivers |

> Botland has 4.9★ rating (50,000+ reviews), fast shipping, and good prices. German website with phone support (+49 69 95 019 621).

#### Amazon.de — Fallback

| # | Component | Amazon Search Link |
|---|-----------|-------------------|
| 1 | Raspberry Pi 5 4GB | [🔗 Amazon Search](https://www.amazon.de/s?k=Raspberry+Pi+5+4GB) |
| 2 | Camera Module 3 Wide | [🔗 Amazon Search](https://www.amazon.de/s?k=Raspberry+Pi+Camera+Module+3+Wide) |
| 4 | PCA9685 Servo Driver | [🔗 Amazon Search](https://www.amazon.de/s?k=PCA9685+servo+driver) |
| 7 | USB-C Powerbank 10000mAh | [🔗 Amazon Search](https://www.amazon.de/s?k=USB-C+PD+Powerbank+10000mAh) |
| 12 | Logitech F310 Gamepad | [🔗 Amazon Search](https://www.amazon.de/s?k=Logitech+F310) |

> Amazon has Prime delivery but prices can be higher. Best for the Logitech F310 (not available at BerryBase).

#### 💡 Smart Buying Strategy

1. **Check BerryBase first** for Pi, Camera, PCA9685, and HC-SR04 (cheapest prices!)
2. **Check Reichelt** for the power supply, power bank, MicroSD, and jumper wires
3. **Check Botland** if both are sold out — they often have stock when German shops don't
4. **Amazon** as last resort, or for the Logitech F310 gamepad

---

## ☁️ Cloud Services Cheat Sheet

Your RTX 3080 Ti handles everything, but here are alternatives for convenience:

| Service | What For | Cost | When to Use |
|---------|----------|------|-------------|
| **Your RTX 3080 Ti** | Training + live inference | **€0** | Always your first choice |
| **Google Colab** | Training in a browser | Free (T4 GPU) | At school, no GPU available |
| **Vast.ai** | Renting a cloud GPU | €0.15–0.50/hr | If you need more VRAM or parallel training |
| **RunPod** | Cloud GPU with SSH | €0.30–0.80/hr | If you want a persistent cloud environment |
| **Hugging Face Spaces** | Host a demo/dashboard | Free | Show off your model online |

**Colab quick-start for training at school:**
```
1. Go to colab.research.google.com
2. Create new notebook
3. Runtime → Change runtime type → T4 GPU
4. Upload your data to Google Drive
5. Mount Drive: from google.colab import drive; drive.mount('/content/drive')
6. Copy training code from autorace repo → train → download model
7. Take model file home → run inference on your PC
```

---

## ⚖️ Why This Setup Beats On-Car AI

| Metric | RPi 5 + Your PC (WiFi) | Jetson Nano (On-Car) | RPi + Coral TPU |
|--------|----------------------|---------------------|----------------|
| **On-car cost** | **~€210** | ~€250+ | ~€200+ |
| **AI speed** | **~300 FPS** (3080 Ti) | ~20 FPS (TensorRT) | ~30 FPS |
| **Training time** | **~5 min** (3080 Ti) | ~60 min (same GPU PC needed anyway) | Need separate PC anyway |
| **Model flexibility** | **Any size model** | Limited by 4GB RAM | Only TFLite models |
| **Upgradability** | Swap to bigger models anytime | Stuck with Nano limits | Limited |
| **Complexity** | Medium (WiFi setup) | Medium (JetPack setup) | Medium |
| **Latency** | ~25-40ms (local WiFi) | ~5ms (on-device) | ~10ms (on-device) |

> The only downside is WiFi latency (~25-40ms), but for an RC car at school
> speeds, this is completely fine. Even real self-driving car prototypes often use
> wireless communication with backend servers.

---

## 🔗 Key Resources & Links

| Resource | Link |
|----------|------|
| **SelfDrivingRCCar (Primary Codebase)** | https://github.com/sidroopdaska/SelfDrivingRCCar |
| **Autorace (Model architectures)** | https://github.com/caipeide/autorace |
| **Donkeycar Framework** | https://github.com/autorope/donkeycar |
| **Donkeycar Docs** | https://docs.donkeycar.com |
| **Raspberry Pi 5 Docs** | https://www.raspberrypi.com/documentation/ |
| **Pi Camera 3 Docs** | https://www.raspberrypi.com/documentation/accessories/camera.html |
| **PCA9685 Wiring Guide** | https://learn.adafruit.com/16-channel-pwm-servo-driver/python-circuitpython |
| **PyTorch + CUDA Install** | https://pytorch.org/get-started/locally/ |
| **Google Colab** | https://colab.research.google.com |
| **Vast.ai (Cheap Cloud GPU)** | https://vast.ai |
| **Reichelt Elektronik** | https://www.reichelt.de |
| **BerryBase (RPi Shop DE)** | https://www.berrybase.de |
| **NVIDIA End-to-End Driving Paper** | https://arxiv.org/abs/1604.07316 |

---

## 💡 Tips for Success

1. **Start simple** — get camera streaming + servo control working before AI
2. **Use 5GHz WiFi** — the Pi 5 supports dual-band; always choose 5GHz for low latency
3. **Wheels off ground first** — always test ESC/servo with the car elevated
4. **Quality data > Quantity** — 10 clean laps beats 50 sloppy ones
5. **Your 3080 Ti is overkill** — training takes minutes, inference takes milliseconds. Use it!
6. **JPEG quality 70** — good balance of image quality vs. transfer speed over WiFi
7. **Ping test first** — `ping aicar.local` should be <10ms on a good 5GHz connection
8. **Separate power** — motor battery and Pi 5 power bank must be separate (no brownouts)
9. **3D-print mounts** — a solid camera mount = stable images = better AI
10. **Iterate fast** — drive → train (5 min) → test → repeat. You can do 10 iterations in one afternoon

---

*Document created for school project planning — March 2026*
