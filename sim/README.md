# TurboToaster simulator

We do **not** ship our own simulator. Instead we stand on the shoulders of the
**Donkey Car** project's proven Unity sim (`gym-donkeycar`), which is purpose-
built for small-scale RC cars driving on a track, ships with several pre-made
terrains, and — handily — uses the **same dataset format** as our recorder.

`sim/bridge.py` is just a thin shim: it runs the donkey-gym environment and
exposes it over the **exact same TCP wire protocol** the real Pi uses
(`car/stream.py`). That means `server/drive.py`, `server/view_stream.py`,
`ai/infer.py` and `server/recorder.py` all work against the sim with **no code
changes** — just point them at `--host localhost`.

## What you get

- Multiple proven tracks: `generated_track`, `generated_road`, `warehouse`,
  `mountain`, `thunderhill`, `circuit`, `roboracingleague`, `minimonaco`,
  `avc`, `waveshare`.
- Configurable camera position / pitch / FOV (your "god model" deciding where
  the camera sits on the chassis).
- Pen-test knobs the real car can't easily give you:
  - `--latency-ms` — add base latency in each direction (simulate the WAN
    round-trip to the off-site RTX 3090).
  - `--jitter-ms` — random extra latency per packet.
  - `--drop` — probability of dropping an incoming command packet.
  - `--speed-cap` — multiplier on throttle, lock the sim to "slow" or "fast".

## Install

```bash
pip install -r sim/requirements.txt
```

Then download a prebuilt **donkey-sim binary** for your OS from the upstream
releases page and unpack it somewhere:

  https://github.com/tawnkramer/gym-donkeycar/releases

Point the bridge at it via env var (or use `"remote"` if you'll launch the sim
GUI yourself):

```bash
export DONKEY_SIM_PATH=/path/to/DonkeySimLinux/donkey_sim.x86_64
```

## Run

In one terminal:

```bash
python sim/bridge.py --track generated_track \
                     --width 480 --height 270 --fps 30 \
                     --cam-y 0.10 --cam-z 0.15 --cam-pitch -15 --fov 120 \
                     --latency-ms 150 --jitter-ms 30 --drop 0.01 \
                     --speed-cap 0.6
```

In another terminal — drive it manually (with video):

```bash
python server/drive.py --host localhost
```

Or run the trained AI against it (identical command to driving the real car):

```bash
python ai/infer.py --host localhost --checkpoint ai/checkpoints/best.pt --show
```

Or record a sim dataset that you can train on later:

```bash
python server/drive.py --host localhost --record datasets
```

## Pen-test scenarios worth running

| Goal | Flags |
| --- | --- |
| Baseline (LAN) | `--latency-ms 0` |
| Off-site WAN feel | `--latency-ms 120 --jitter-ms 40` |
| Lossy uplink | `--latency-ms 80 --drop 0.05` |
| Slow-speed safety check | `--speed-cap 0.3` |
| Stress: chase performance | `--latency-ms 200 --jitter-ms 80 --drop 0.02 --speed-cap 1.0` |
| Camera too low (god-model) | `--cam-y 0.04 --cam-pitch -25` |
| Wide-angle vs. narrow | `--fov 90` vs. `--fov 140` |

Because the bridge enforces the same `ts` / `seq` / 300 ms-stale rules the Pi
does, anything that goes wrong here (control fights, runaway after a packet
storm, etc.) is a **real** finding for the on-car build.
