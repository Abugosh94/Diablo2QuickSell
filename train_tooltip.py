"""Train a fresh YOLOv8n tooltip detector on synthetic full-screen composites.

Pipeline:
  1. gen_composites.build() pastes the hand-cropped tooltips onto dark
     game-like canvases and labels the pasted box (plus ~12% pure
     background negatives). Everything is written to %TEMP% (non-synced).
  2. Trains a fresh yolov8n on those composites - on the GPU if this
     python has CUDA torch (see setup_gpu_venv.cmd), otherwise on CPU.
  3. Copies best.pt -> tooltip_best_v6.pt.

Why composites: training directly on the tight crops taught the model
"tooltip = whole frame", so on real full screenshots it predicted huge
near-full-screen boxes with high confidence (conf 0.98, IoU ~0.05).
Composites teach it to localize the tooltip inside a full screen, which
is exactly what the F9 quick-list capture needs.

Usage:    python train_tooltip.py
          (or with the GPU venv:  tooltip_gpu_venv\\Scripts\\python train_tooltip.py)
"""
import os
import shutil
import sys

from ultralytics import YOLO

import gen_composites

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_NAME = "tooltip_v6"
FINAL_MODEL = os.path.join(BASE, "tooltip_best_v6.pt")
# Base model for transfer learning. YOLO26n is the latest Ultralytics nano
# model (auto-downloads on first use); yolov8n.pt was the previous base.
# Short name on purpose: ultralytics only auto-downloads by short name.
BASE_MODEL = "yolo26n.pt"


def _pick_device():
    """Use the GPU if this environment has CUDA torch, else CPU."""
    try:
        import torch
        if torch.cuda.is_available():
            print(f"Training on GPU: {torch.cuda.get_device_name(0)}")
            return 0
    except Exception:
        pass
    print("Training on CPU (no CUDA torch available - see setup_gpu_venv.cmd)")
    return "cpu"


def main():
    data_yaml = gen_composites.build()

    # clean leftovers of previous attempts so the run dir is predictable
    runs_dir = os.path.join(BASE, "runs", "detect")
    if os.path.isdir(runs_dir):
        for d in os.listdir(runs_dir):
            if d.startswith(OUT_NAME):
                shutil.rmtree(os.path.join(runs_dir, d))

    model = YOLO(BASE_MODEL)  # fresh COCO-pretrained base (YOLO26n)
    device = _pick_device()
    model.train(
        data=data_yaml,
        epochs=50,
        imgsz=640,
        batch=16,
        device=device,
        workers=8 if device == 0 else 4,
        project=runs_dir,
        name=OUT_NAME,
        seed=0,
        patience=25,
        # composites already provide full-screen context -> no mosaic needed
        mosaic=0.0,
        scale=0.4,        # robustness to different game window sizes
        translate=0.1,
        fliplr=0.0,       # mirrored text would look wrong
        flipud=0.0,
        degrees=0.0,      # tooltips are never rotated in game
        shear=0.0,
        perspective=0.0,
        hsv_h=0.01,
        hsv_s=0.4,
        hsv_v=0.4,
        erasing=0.0,
        mixup=0.0,
        copy_paste=0.0,
        plots=True,
        verbose=True,
    )

    best = os.path.join(runs_dir, OUT_NAME, "weights", "best.pt")
    if os.path.exists(best):
        shutil.copy2(best, FINAL_MODEL)
        print(f"\nSaved final model -> {FINAL_MODEL}")
    else:
        sys.exit("Training finished but best.pt was not found")


if __name__ == "__main__":
    main()
