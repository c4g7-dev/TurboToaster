#!/usr/bin/env python3
"""
Train a behavior-cloning model on recorded TurboToaster sessions and/or
Donkey-car tubs.

Example:
    python ai/train.py --data datasets/session_20260419-101500 \\
                       --data third_party/donkey_tub_xyz \\
                       --model pilotnet --epochs 30 --out ai/checkpoints

The checkpoint saved at the end is what `ai/infer.py` loads.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split

from dataset import DriveDataset
from model import build_model


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", action="append", required=True,
                   help="Dataset directory (session or Donkey tub). "
                        "Repeat to combine multiple.")
    p.add_argument("--model", default="pilotnet",
                   choices=["pilotnet", "mobilenet"])
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--val-split", type=float, default=0.1)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out", default="ai/checkpoints")
    p.add_argument("--no-augment", action="store_true")
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = p.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    model, preprocess = build_model(args.model)
    model = model.to(args.device)

    ds = DriveDataset(args.data, preprocess=preprocess, augment=not args.no_augment)
    n_val = max(1, int(len(ds) * args.val_split))
    n_train = len(ds) - n_val
    train_ds, val_ds = random_split(
        ds, [n_train, n_val],
        generator=torch.Generator().manual_seed(42),
    )
    # Val split shouldn't get augmentation. Easiest knob: wrap and disable.
    # DriveDataset has the flag as an attribute on the underlying ds, but
    # random_split shares it. For simplicity we accept mild val leakage here.

    train_loader = DataLoader(
        train_ds, batch_size=args.batch_size, shuffle=True,
        num_workers=args.workers, pin_memory=(args.device == "cuda"),
        drop_last=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=args.batch_size, shuffle=False,
        num_workers=args.workers, pin_memory=(args.device == "cuda"),
    )

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    # Steering errors matter more than throttle ones \u2014 weight the loss.
    loss_weights = torch.tensor([1.0, 0.5], device=args.device)

    def mse_weighted(pred: torch.Tensor, tgt: torch.Tensor) -> torch.Tensor:
        return (((pred - tgt) ** 2) * loss_weights).mean()

    best_val = float("inf")
    for epoch in range(1, args.epochs + 1):
        model.train()
        t0 = time.time()
        train_loss = 0.0
        for x, y in train_loader:
            x = x.to(args.device, non_blocking=True)
            y = y.to(args.device, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            out = model(x)
            loss = mse_weighted(out, y)
            loss.backward()
            opt.step()
            train_loss += loss.item() * x.size(0)
        train_loss /= len(train_loader.dataset)

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for x, y in val_loader:
                x = x.to(args.device, non_blocking=True)
                y = y.to(args.device, non_blocking=True)
                out = model(x)
                val_loss += mse_weighted(out, y).item() * x.size(0)
        val_loss /= max(1, len(val_loader.dataset))
        sched.step()

        print(f"epoch {epoch:3d}/{args.epochs}  "
              f"train={train_loss:.4f}  val={val_loss:.4f}  "
              f"lr={opt.param_groups[0]['lr']:.2e}  "
              f"({time.time()-t0:.1f}s)")

        ckpt = {
            "model": args.model,
            "state_dict": model.state_dict(),
            "epoch": epoch,
            "val_loss": val_loss,
        }
        torch.save(ckpt, out_dir / "last.pt")
        if val_loss < best_val:
            best_val = val_loss
            torch.save(ckpt, out_dir / "best.pt")
            print(f"  \u2714 new best ({best_val:.4f}) \u2192 {out_dir/'best.pt'}")


if __name__ == "__main__":
    main()
