# TurboToaster AI

The brains that run off-board on the RTX 3090 host. Two loops:

- **fast loop** (`infer.py`): runs a small behavior-cloning CNN on every
  incoming frame and sends `{steer, throttle}` back to the Pi. Target: <2 ms
  of GPU time per frame; the WAN link is the real latency budget.
- **slow loop** (`perceive.py`): optional. Runs YOLOv8n on every Nth frame
  in a background thread to report objects in view. Detections are just
  logged for now.

## Install

```bash
# Match your CUDA:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r ai/requirements.txt
```

## 1. Collect data

Drive manually with the dataset recorder on:

```bash
python server/drive.py --host aicar.local --record datasets
```

Each drive produces `datasets/session_YYYYmmdd-HHMMSS/` with `images/` +
`log.csv` (plus Donkey-compatible `record_*.json` sidecars).

You can also drop third-party Donkey-car tubs into any folder \u2014 the loader
reads both formats.

## 2. Train

```bash
python ai/train.py \
    --data datasets/session_20260419-101500 \
    --data datasets/session_20260419-111000 \
    --model pilotnet --epochs 30 \
    --out ai/checkpoints
```

Models:

| `--model`     | params | input       | good for |
|---------------|--------|-------------|----------|
| `pilotnet`    | ~250k  | 3\u00d766\u00d7200 YUV | first pass, proof the pipeline works |
| `mobilenet`   | ~1.5M  | 3\u00d7160\u00d7160 RGB | better generalization on small data |

Checkpoints land at `ai/checkpoints/{last,best}.pt`.

## 3. Drive

```bash
# Make sure car/stream.py is running on the Pi first.
python ai/infer.py \
    --host aicar.local \
    --checkpoint ai/checkpoints/best.pt \
    --show          # opens a HUD preview window
```

Add `--perceive` to also run YOLOv8n in a background thread \u2014 detections
are shown on the HUD and printed.

## Notes on latency

- The Pi now caps encoded JPEG resolution at **480\u00d7270 @ 30 fps** by default
  and uses a newest-frame-wins sender, so congestion never builds a queue.
- Every command carries `ts` and `seq`. The Pi drops any AI command older
  than 300 ms of wall-clock (see `STALE_CMD_SEC` in `car/stream.py`), so a
  momentary WAN stall won't cause the car to act on ancient predictions
  when the link recovers.
- Clocks on the Pi and the AI box must be roughly NTP-synced for the
  staleness guard to work. On LAN this is free; on WAN make sure both hosts
  actually sync to NTP (`timedatectl status` on Linux).
